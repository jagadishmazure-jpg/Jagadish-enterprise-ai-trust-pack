"""Deterministic demos for every module. The CLI prints them; the trust portal and docs reuse them.

All times are fixed (AS_OF) so output is identical on every run.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import data_use, incidents, isolation, provenance, residency, retention, security_tests, subprocessors

AS_OF = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
DEMO_KEY = b"demo-only-key-not-a-secret-000000"  # fixed so output is reproducible; production reads env


def residency_summary() -> list[dict]:
    out = []
    for name in ("fernhollow-bank-eu", "marlowe-freight-us", "broken-example"):
        cfg = residency.load_config(name)
        out.append({"config": name, "tenant": cfg["tenant"], "boundary": f"{cfg['boundary']['scope']}:"
                    f"{cfg['boundary']['value']}", "findings": [str(f) for f in residency.check_config(cfg)]})
    return out


def data_use_summary() -> dict:
    t0 = AS_OF - timedelta(days=10)
    gw = data_use.TrainingGateway(consents=[data_use.Consent("fernhollow-bank", "feedback", t0)], key=DEMO_KEY)
    rows = []
    for tenant in ("fernhollow-bank", "marlowe-freight"):
        for dtype in ("prompts", "outputs", "files_embeddings", "telemetry", "feedback"):
            d = gw.route({"tenant": tenant, "data_type": dtype, "user_id": "u-17", "text": "sample"},
                         "training_corpus", AS_OF)
            rows.append({"tenant": tenant, "data_type": dtype, "allowed": d.allowed, "reason": d.reason})
    req = gw.prepare_provider_request({"model": "chat-main", "store": True})
    return {"rows": rows, "provider_request": req, "audit_entries": len(gw.audit.entries),
            "audit_intact": gw.audit.verify(gw.audit.entries) is None}


def retention_summary() -> dict:
    stores = retention.default_stores()
    old, new = AS_OF - timedelta(days=40), AS_OF - timedelta(hours=1)
    for s in stores:
        for subj in ("subj-ana", "subj-ben"):
            for when in (old, new):
                dtype = {"prompt_log": "prompts", "vector_index": "embeddings", "cache": "caches",
                         "traces": "traces"}[s.name]
                s.put(subj, "fernhollow-bank", dtype, f"{subj} content at {when.date()}", when)
    swept = retention.sweep(stores, retention.load_schedule(), AS_OF)
    req = retention.DeletionRequest("del-0001", "fernhollow-bank", "subj-ana", AS_OF - timedelta(days=2))
    cert = retention.process_deletion(req, stores, AS_OF)
    return {"swept": swept, "certificate": cert, "verify_errors": retention.verify_certificate(cert),
            "ben_left": sum(s.count_subject("fernhollow-bank", "subj-ben") for s in stores)}


def isolation_summary() -> dict:
    store = isolation.TenantStore(DEMO_KEY)
    tenants = ["fernhollow-bank", "marlowe-freight", "pellucid-insure"]
    layout = [store.onboard(t) for t in tenants]
    results = isolation.cross_tenant_canary_suite(store, tenants)
    sa = isolation.SupportAccess({"fernhollow-bank": {"admin-fh"}})
    g = sa.request("eng-ravi", "fernhollow-bank", {"read_logs_redacted"}, "SUP-4411", "slow answers", AS_OF)
    before = sa.check("eng-ravi", "fernhollow-bank", "read_logs_redacted", AS_OF + timedelta(minutes=5))
    sa.approve(g.grant_id, "admin-fh", AS_OF + timedelta(minutes=10))
    during = sa.check("eng-ravi", "fernhollow-bank", "read_logs_redacted", AS_OF + timedelta(minutes=30))
    wrong = sa.check("eng-ravi", "fernhollow-bank", "read_documents", AS_OF + timedelta(minutes=31))
    after = sa.check("eng-ravi", "fernhollow-bank", "read_logs_redacted", AS_OF + timedelta(hours=3))
    return {"layout": layout, "pairs": len(results), "leaks": sum(len(r["leaks"]) for r in results),
            "jit": {"before_approval": before, "during": during, "wrong_action": wrong, "after_expiry": after,
                    "expires_at": g.expires_at.isoformat(), "log_entries": len(sa.log.entries),
                    "log_intact": sa.log.verify(sa.log.entries) is None}}


def incidents_summary() -> list[dict]:
    return [incidents.simulate(s) for s in incidents.load_scenarios()]


def security_summary() -> dict:
    return security_tests.aggregate()


def provenance_summary() -> dict:
    m = provenance.load()
    return {"release": m["release"], "date": m["date"], "components": m["components"],
            "errors": provenance.verify(m)}


def subprocessor_summary() -> dict:
    hist = sorted(subprocessors.registry.HISTORY.glob("*.yaml"))
    old, new = subprocessors.load_registry(hist[-1]), subprocessors.load_registry()
    changes = subprocessors.diff(old, new)
    return {"registry": new, "changes": changes, "errors": subprocessors.validate(new),
            "boundary": subprocessors.check_boundary(new, "EU")}
