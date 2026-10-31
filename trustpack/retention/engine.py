"""Retention sweeps and verified deletion.

delete request -> plant canaries -> purge every store -> verify with canaries -> hash-chained certificate.

Canaries make the proof testable: a canary written for the subject must be gone after the purge
(proves the purge reaches that store) and a control canary for another subject must survive
(proves the verifier is really looking, and that the purge did not over-delete).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ..common import PKG, HashChain, canonical, load_yaml, sha256_hex
from .stores import Store

SCHEDULE = PKG / "retention" / "schedule.yaml"
CONTROL_SUBJECT = "__control__"


def load_schedule(path=SCHEDULE) -> dict:
    return load_yaml(path)


def sweep(stores: list[Store], schedule: dict, now: datetime) -> dict[str, int]:
    """Delete everything past its retention. Returns deleted counts per data type."""
    by_name = {s.name: s for s in stores}
    out = {}
    for dtype, rule in schedule["schedule"].items():
        if rule["days"] is None or rule["store"] not in by_name:
            continue
        out[dtype] = by_name[rule["store"]].expire(dtype, now - timedelta(days=rule["days"]))
    return out


@dataclass(frozen=True)
class DeletionRequest:
    request_id: str
    tenant: str
    subject: str
    received_at: datetime


def canary_token(request_id: str, store: str, kind: str) -> str:
    return f"CANARY-{kind}-{sha256_hex(f'{request_id}|{store}|{kind}')[:16]}"


def process_deletion(req: DeletionRequest, stores: list[Store], now: datetime, schedule: dict | None = None) -> dict:
    schedule = schedule or load_schedule()
    chain = HashChain()
    chain.append({"step": "received", "request_id": req.request_id, "tenant": req.tenant,
                  "subject_ref": sha256_hex(f"{req.tenant}|{req.subject}")[:16], "at": req.received_at.isoformat()})
    for s in stores:
        s.put(req.subject, req.tenant, "canary", canary_token(req.request_id, s.name, "subject"), now)
        s.put(CONTROL_SUBJECT, req.tenant, "canary", canary_token(req.request_id, s.name, "control"), now)
    ok = True
    for s in stores:
        n = s.purge_subject(req.tenant, req.subject)
        left = s.count_subject(req.tenant, req.subject)
        subj_gone = not s.contains_text(canary_token(req.request_id, s.name, "subject"))
        control_ok = s.contains_text(canary_token(req.request_id, s.name, "control"))
        passed = left == 0 and subj_gone and control_ok
        ok &= passed
        chain.append({"step": "purge", "store": s.name, "deleted": n - 1 if subj_gone else n, "remaining": left,
                      "subject_canary_gone": subj_gone, "control_canary_present": control_ok, "passed": passed})
        s.purge_subject(req.tenant, CONTROL_SUBJECT)
    backup_days = schedule["schedule"]["backups"]["days"]
    sla = schedule["deletion_sla_days"]
    within_sla = (now - req.received_at) <= timedelta(days=sla)
    ok &= within_sla
    chain.append({"step": "backups", "note": "immutable backups are not rewritten",
                  "aged_out_by": (now + timedelta(days=backup_days)).date().isoformat()})
    status = "VERIFIED" if ok else "FAILED"
    chain.append({"step": "issued", "status": status, "within_sla_days": sla, "within_sla": within_sla,
                  "at": now.isoformat()})
    return {"certificate": "deletion", "label": "Template, not certified", "request_id": req.request_id,
            "status": status, "entries": chain.entries, "head": chain.head}


def verify_certificate(cert: dict) -> list[str]:
    errs = []
    bad = HashChain.verify(cert["entries"])
    if bad is not None:
        errs.append(f"hash chain broken at entry {bad}")
    elif cert["head"] != cert["entries"][-1]["hash"]:
        errs.append("head hash does not match last entry")
    purges = [e["body"] for e in cert["entries"] if e["body"].get("step") == "purge"]
    if cert["status"] == "VERIFIED" and not all(p["passed"] for p in purges):
        errs.append("status VERIFIED but a purge step failed")
    return errs


def certificate_digest(cert: dict) -> str:
    return sha256_hex(canonical(cert))
