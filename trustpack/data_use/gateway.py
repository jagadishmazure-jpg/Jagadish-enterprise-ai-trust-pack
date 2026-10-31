"""The training gateway: the single place a record can move toward a training corpus.

Fail-closed rules:
  * unknown data type or destination -> deny
  * destination "training_corpus" -> allowed only for data types marked opt_in, and only when the
    tenant's opt-in for that type is live at the decision time (granted, not revoked, not expired)
  * opt-in records leave with the user id replaced by a keyed HMAC pseudonym
  * every decision is written to a hash-chained audit log
"""
from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from datetime import datetime

from ..common import PKG, HashChain, load_yaml

POLICY_PATH = PKG / "data_use" / "policy.yaml"
KEY_ENV = "TRUSTPACK_PSEUDONYM_KEY"


def load_policy(path=POLICY_PATH) -> dict:
    return load_yaml(path)


def pseudonymise(value: str, key: bytes) -> str:
    """Keyed HMAC-SHA256 pseudonym. Rotate by changing the key; old pseudonyms stop linking."""
    if not key:
        raise ValueError("pseudonym key must not be empty")
    return "psn_" + hmac.new(key, value.encode(), hashlib.sha256).hexdigest()[:24]


@dataclass(frozen=True)
class Consent:
    tenant: str
    data_type: str
    granted_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    def live(self, at: datetime) -> bool:
        if at < self.granted_at:
            return False
        if self.revoked_at and at >= self.revoked_at:
            return False
        return not (self.expires_at and at >= self.expires_at)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    record: dict | None = None


class TrainingGateway:
    def __init__(self, policy: dict | None = None, consents: list[Consent] | None = None,
                 key: bytes | None = None):
        self.policy = policy or load_policy()
        self.consents = list(consents or [])
        env_key = os.environ.get(KEY_ENV, "").encode()
        self.key = key if key is not None else env_key
        self.audit = HashChain()

    def _consented(self, tenant: str, data_type: str, at: datetime) -> bool:
        return any(c.tenant == tenant and c.data_type == data_type and c.live(at) for c in self.consents)

    def route(self, record: dict, destination: str, at: datetime) -> Decision:
        dtype = record.get("data_type")
        tenant = record.get("tenant", "?")
        rule = self.policy["data_types"].get(dtype)
        dest = self.policy["destinations"].get(destination)
        if rule is None:
            d = Decision(False, f"unknown data type '{dtype}' (fail closed)")
        elif dest is None or dest == "denied":
            d = Decision(False, f"destination '{destination}' is not allowed")
        elif dest == "allowed":
            d = Decision(True, f"{destination} is allowed for {dtype}", record)
        elif rule["training"] == "never":
            d = Decision(False, f"{dtype} is never used for training")
        elif not self._consented(tenant, dtype, at):
            d = Decision(False, f"no live opt-in from {tenant} for {dtype}")
        elif not self.key:
            d = Decision(False, f"{KEY_ENV} not set; refusing to release un-pseudonymised data")
        else:
            out = {k: v for k, v in record.items() if k != "user_id"}
            if "user_id" in record:
                out["user_ref"] = pseudonymise(record["user_id"], self.key)
            d = Decision(True, f"opt-in live for {tenant}/{dtype}", out)
        self.audit.append({"tenant": tenant, "data_type": dtype, "destination": destination,
                           "allowed": d.allowed, "reason": d.reason, "at": at.isoformat()})
        return d

    def prepare_provider_request(self, request: dict) -> dict:
        """Force the provider-side settings from policy (e.g. store=false) onto an outbound call."""
        out = dict(request)
        for k, v in self.policy["provider_request"]["required"].items():
            out[k] = v
        return out

    def check_provider_request(self, request: dict) -> list[str]:
        req = self.policy["provider_request"]["required"]
        return [f"{k} must be {v!r}, got {request.get(k)!r}" for k, v in req.items() if request.get(k) != v]
