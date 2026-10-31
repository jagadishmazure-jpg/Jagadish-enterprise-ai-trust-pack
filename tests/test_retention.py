from datetime import timedelta

import pytest

from trustpack.retention import (
    Cache,
    DeletionRequest,
    PromptLog,
    TraceStore,
    VectorIndex,
    canary_token,
    default_stores,
    load_schedule,
    process_deletion,
    sweep,
    verify_certificate,
)

T = "fernhollow-bank"
DTYPE = {"prompt_log": "prompts", "vector_index": "embeddings", "cache": "caches", "traces": "traces"}


def seeded(as_of, subjects=("ana", "ben")):
    stores = default_stores()
    for s in stores:
        for subj in subjects:
            s.put(subj, T, DTYPE[s.name], f"{subj} said hello", as_of - timedelta(hours=2))
    return stores


def req(as_of, subject="ana", days_ago=1):
    return DeletionRequest("del-test", T, subject, as_of - timedelta(days=days_ago))


def test_schedule_covers_buyer_data_types():
    s = load_schedule()["schedule"]
    for k in ("prompts", "outputs", "backups", "audit_logs", "embeddings"):
        assert k in s
    assert s["prompts"]["days"] == 30 and s["backups"]["days"] == 35 and s["audit_logs"]["days"] == 365
    assert s["embeddings"]["days"] is None


def test_sla_is_thirty_days():
    assert load_schedule()["deletion_sla_days"] == 30


def test_sweep_respects_each_window(as_of):
    stores = default_stores()
    pl, vi, ca, tr = stores
    pl.put("a", T, "prompts", "old", as_of - timedelta(days=31))
    pl.put("a", T, "prompts", "fresh", as_of - timedelta(days=29))
    ca.put("a", T, "caches", "old", as_of - timedelta(days=2))
    tr.put("a", T, "traces", "old", as_of - timedelta(days=15))
    vi.put("a", T, "embeddings", "kept", as_of - timedelta(days=900))
    out = sweep(stores, load_schedule(), as_of)
    assert out["prompts"] == 1 and out["caches"] == 1 and out["traces"] == 1
    assert [r["content"] for r in pl.records()] == ["fresh"] and len(vi.records()) == 1


def test_sweep_skips_until_deleted_types(as_of):
    assert "embeddings" not in sweep(default_stores(), load_schedule(), as_of)


@pytest.mark.parametrize("cls", [PromptLog, VectorIndex, Cache, TraceStore])
def test_each_store_purges_only_the_subject(as_of, cls):
    s = cls()
    s.put("ana", T, "x", "ana text", as_of)
    s.put("ben", T, "x", "ben text", as_of)
    s.put("ana", "other-tenant", "x", "same name other tenant", as_of)
    assert s.purge_subject(T, "ana") == 1
    assert s.count_subject(T, "ana") == 0 and s.count_subject(T, "ben") == 1
    assert s.count_subject("other-tenant", "ana") == 1


def test_certificate_verified_across_all_four_stores(as_of):
    cert = process_deletion(req(as_of), seeded(as_of), as_of)
    purges = [e["body"] for e in cert["entries"] if e["body"]["step"] == "purge"]
    assert cert["status"] == "VERIFIED"
    assert {p["store"] for p in purges} == {"prompt_log", "vector_index", "cache", "traces"}
    assert all(p["deleted"] == 1 and p["remaining"] == 0 for p in purges)
    assert verify_certificate(cert) == []


def test_other_subjects_survive_and_control_canaries_removed(as_of):
    stores = seeded(as_of)
    process_deletion(req(as_of), stores, as_of)
    for s in stores:
        assert s.count_subject(T, "ben") == 1
        assert not any("CANARY" in r["content"] for r in s.records())


def test_certificate_has_no_raw_subject(as_of):
    cert = process_deletion(req(as_of, subject="ana.moreau@fernhollow.example"), seeded(as_of), as_of)
    import json
    assert "ana.moreau" not in json.dumps(cert)


def test_certificate_labelled_template(as_of):
    assert process_deletion(req(as_of), seeded(as_of), as_of)["label"] == "Template, not certified"


def test_backups_step_states_age_out_date(as_of):
    cert = process_deletion(req(as_of), seeded(as_of), as_of)
    b = next(e["body"] for e in cert["entries"] if e["body"]["step"] == "backups")
    assert b["aged_out_by"] == (as_of + timedelta(days=35)).date().isoformat()


class LeakyIndex(VectorIndex):
    """Simulates a real bug: purge deletes only the first matching vector."""

    def purge_subject(self, tenant, subject):
        for k, (_, m) in list(self.vectors.items()):
            if m["tenant"] == tenant and m["subject"] == subject:
                del self.vectors[k]
                return 1
        return 0


class OverDeletingCache(Cache):
    """Simulates the opposite bug: purge wipes the whole tenant."""

    def purge_subject(self, tenant, subject):
        n = len(self.entries)
        self.entries = {k: v for k, v in self.entries.items() if not k.startswith(f"{tenant}:")}
        return n


def test_canary_catches_incomplete_purge(as_of):
    stores = [PromptLog(), LeakyIndex(), Cache(), TraceStore()]
    for s in stores:
        s.put("ana", T, "x", "ana data", as_of)
    cert = process_deletion(req(as_of), stores, as_of)
    bad = next(e["body"] for e in cert["entries"] if e["body"].get("store") == "vector_index")
    assert cert["status"] == "FAILED" and bad["passed"] is False


def test_control_canary_catches_over_deletion(as_of):
    stores = [PromptLog(), VectorIndex(), OverDeletingCache(), TraceStore()]
    cert = process_deletion(req(as_of), stores, as_of)
    bad = next(e["body"] for e in cert["entries"] if e["body"].get("store") == "cache")
    assert cert["status"] == "FAILED" and bad["control_canary_present"] is False


def test_late_request_fails_sla(as_of):
    cert = process_deletion(req(as_of, days_ago=31), seeded(as_of), as_of)
    issued = cert["entries"][-1]["body"]
    assert cert["status"] == "FAILED" and issued["within_sla"] is False


def test_tampered_certificate_detected(as_of):
    cert = process_deletion(req(as_of), seeded(as_of), as_of)
    cert["entries"][1]["body"]["remaining"] = 0
    cert["entries"][1]["body"]["deleted"] = 99
    assert any("hash chain broken" in e for e in verify_certificate(cert))


def test_forged_status_detected(as_of):
    stores = [PromptLog(), LeakyIndex(), Cache(), TraceStore()]
    for s in stores:
        s.put("ana", T, "x", "a", as_of)
    cert = process_deletion(req(as_of), stores, as_of)
    cert["status"] = "VERIFIED"
    assert "status VERIFIED but a purge step failed" in verify_certificate(cert)


def test_canary_tokens_unique_per_store_and_kind():
    toks = {canary_token("r1", s, k) for s in ("a", "b") for k in ("subject", "control")}
    assert len(toks) == 4


def test_certificate_is_deterministic(as_of):
    a = process_deletion(req(as_of), seeded(as_of), as_of)
    b = process_deletion(req(as_of), seeded(as_of), as_of)
    assert a["head"] == b["head"]
