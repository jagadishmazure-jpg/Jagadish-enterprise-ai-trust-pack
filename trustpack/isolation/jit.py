"""Just-in-time vendor support access: requested with a ticket, approved by the customer, expires, logged.

No standing access. Each grant is scoped to one tenant and a list of actions, lasts at most
MAX_GRANT, and every check (allowed or denied) is written to a hash-chained access log the
customer can review.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ..common import HashChain

MAX_GRANT = timedelta(hours=4)
ACTIONS = {"read_config", "read_logs_redacted", "restart_worker", "read_documents"}


class AccessDenied(PermissionError):
    pass


@dataclass
class Grant:
    grant_id: str
    engineer: str
    tenant: str
    actions: frozenset
    ticket: str
    reason: str
    requested_at: datetime
    duration: timedelta
    approved_by: str | None = None
    approved_at: datetime | None = None
    revoked_at: datetime | None = None

    @property
    def expires_at(self) -> datetime | None:
        return self.approved_at + self.duration if self.approved_at else None


class SupportAccess:
    def __init__(self, customer_admins: dict[str, set[str]]):
        self.customer_admins = customer_admins  # tenant -> admin user ids
        self.grants: dict[str, Grant] = {}
        self.log = HashChain()

    def request(self, engineer: str, tenant: str, actions: set[str], ticket: str, reason: str,
                at: datetime, duration: timedelta = timedelta(hours=2)) -> Grant:
        if not ticket or not reason:
            raise ValueError("ticket and reason are required")
        if duration > MAX_GRANT or duration <= timedelta(0):
            raise ValueError(f"duration must be within (0, {MAX_GRANT}]")
        unknown = set(actions) - ACTIONS
        if unknown:
            raise ValueError(f"unknown actions {sorted(unknown)}")
        g = Grant(f"jit-{len(self.grants) + 1:04d}", engineer, tenant, frozenset(actions), ticket, reason, at, duration)
        self.grants[g.grant_id] = g
        self.log.append({"event": "requested", "grant": g.grant_id, "engineer": engineer, "tenant": tenant,
                         "ticket": ticket, "actions": sorted(actions), "at": at.isoformat()})
        return g

    def approve(self, grant_id: str, approver: str, at: datetime) -> Grant:
        g = self.grants[grant_id]
        if approver not in self.customer_admins.get(g.tenant, set()):
            self.log.append({"event": "approve_rejected", "grant": grant_id, "by": approver, "at": at.isoformat()})
            raise AccessDenied(f"{approver} is not an admin of {g.tenant}")
        if approver == g.engineer:
            raise AccessDenied("self-approval is not allowed")
        g.approved_by, g.approved_at = approver, at
        self.log.append({"event": "approved", "grant": grant_id, "by": approver, "at": at.isoformat(),
                         "expires_at": g.expires_at.isoformat()})
        return g

    def revoke(self, grant_id: str, at: datetime) -> None:
        self.grants[grant_id].revoked_at = at
        self.log.append({"event": "revoked", "grant": grant_id, "at": at.isoformat()})

    def check(self, engineer: str, tenant: str, action: str, at: datetime) -> bool:
        reason = "no grant"
        for g in self.grants.values():
            if g.engineer != engineer or g.tenant != tenant:
                continue
            if g.approved_at is None:
                reason = "not approved"
            elif g.revoked_at and at >= g.revoked_at:
                reason = "revoked"
            elif at >= g.expires_at or at < g.approved_at:
                reason = "expired"
            elif action not in g.actions:
                reason = f"action '{action}' not in grant"
            else:
                self.log.append({"event": "access", "grant": g.grant_id, "engineer": engineer, "tenant": tenant,
                                 "action": action, "allowed": True, "at": at.isoformat()})
                return True
        self.log.append({"event": "access", "engineer": engineer, "tenant": tenant, "action": action,
                         "allowed": False, "reason": reason, "at": at.isoformat()})
        return False

    def review(self, tenant: str) -> list[dict]:
        """Every log event for one tenant, for the customer's access review."""
        out = []
        for e in self.log.entries:
            b = e["body"]
            g = self.grants.get(b.get("grant", ""))
            if b.get("tenant") == tenant or (g is not None and g.tenant == tenant):
                out.append(b)
        return out
