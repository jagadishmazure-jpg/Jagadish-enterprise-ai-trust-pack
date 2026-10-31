from datetime import timedelta

import pytest

from trustpack.data_use import Consent, TrainingGateway, load_policy, pseudonymise
from trustpack.data_use.gateway import KEY_ENV

KEY = b"unit-test-key-0123456789abcdef"
NEVER = ["prompts", "outputs", "files_embeddings", "telemetry"]


def gw(as_of, consents=(), key=KEY):
    return TrainingGateway(consents=list(consents), key=key)


def rec(dtype, tenant="fernhollow-bank", **kw):
    return {"tenant": tenant, "data_type": dtype, **kw}


def test_policy_marks_only_feedback_opt_in():
    p = load_policy()["data_types"]
    assert {k for k, v in p.items() if v["training"] == "opt_in"} == {"feedback"}
    assert all(p[k]["training"] == "never" for k in NEVER)


@pytest.mark.parametrize("dtype", NEVER)
def test_never_types_blocked_even_with_consent(as_of, dtype):
    g = gw(as_of, [Consent("fernhollow-bank", dtype, as_of - timedelta(days=1))])
    assert not g.route(rec(dtype), "training_corpus", as_of).allowed


@pytest.mark.parametrize("dtype", NEVER + ["feedback"])
def test_inference_always_allowed(as_of, dtype):
    assert gw(as_of).route(rec(dtype), "inference", as_of).allowed


def test_feedback_blocked_without_opt_in(as_of):
    d = gw(as_of).route(rec("feedback"), "training_corpus", as_of)
    assert not d.allowed and "no live opt-in" in d.reason


def test_feedback_allowed_with_live_opt_in_and_pseudonymised(as_of):
    g = gw(as_of, [Consent("fernhollow-bank", "feedback", as_of - timedelta(days=1))])
    d = g.route(rec("feedback", user_id="u-17", text="great"), "training_corpus", as_of)
    assert d.allowed and "user_id" not in d.record and d.record["user_ref"].startswith("psn_")


def test_opt_in_is_per_tenant(as_of):
    g = gw(as_of, [Consent("fernhollow-bank", "feedback", as_of - timedelta(days=1))])
    assert not g.route(rec("feedback", tenant="marlowe-freight"), "training_corpus", as_of).allowed


def test_revoked_opt_in_blocks(as_of):
    c = Consent("fernhollow-bank", "feedback", as_of - timedelta(days=5), revoked_at=as_of - timedelta(hours=1))
    assert not gw(as_of, [c]).route(rec("feedback"), "training_corpus", as_of).allowed


def test_expired_opt_in_blocks(as_of):
    c = Consent("fernhollow-bank", "feedback", as_of - timedelta(days=400), expires_at=as_of - timedelta(days=35))
    assert not gw(as_of, [c]).route(rec("feedback"), "training_corpus", as_of).allowed


def test_future_opt_in_not_live_yet(as_of):
    c = Consent("fernhollow-bank", "feedback", as_of + timedelta(days=1))
    assert not gw(as_of, [c]).route(rec("feedback"), "training_corpus", as_of).allowed


def test_unknown_data_type_fails_closed(as_of):
    d = gw(as_of).route(rec("voice_audio"), "inference", as_of)
    assert not d.allowed and "fail closed" in d.reason


@pytest.mark.parametrize("dest", ["analytics_content", "vendor_bucket"])
def test_denied_or_unknown_destination(as_of, dest):
    assert not gw(as_of).route(rec("prompts"), dest, as_of).allowed


def test_missing_key_refuses_release(as_of, monkeypatch):
    monkeypatch.delenv(KEY_ENV, raising=False)
    g = TrainingGateway(consents=[Consent("fernhollow-bank", "feedback", as_of - timedelta(days=1))])
    d = g.route(rec("feedback", user_id="u1"), "training_corpus", as_of)
    assert not d.allowed and KEY_ENV in d.reason


def test_key_read_from_env(as_of, monkeypatch):
    monkeypatch.setenv(KEY_ENV, "env-key-abcdefghijklmnop")
    g = TrainingGateway(consents=[Consent("fernhollow-bank", "feedback", as_of - timedelta(days=1))])
    assert g.route(rec("feedback", user_id="u1"), "training_corpus", as_of).allowed


def test_pseudonym_is_stable_and_key_dependent():
    assert pseudonymise("u-1", KEY) == pseudonymise("u-1", KEY)
    assert pseudonymise("u-1", KEY) != pseudonymise("u-1", b"rotated-key-0000000000")
    assert "u-1" not in pseudonymise("u-1", KEY)
    with pytest.raises(ValueError):
        pseudonymise("u-1", b"")


def test_provider_request_forced_to_store_false(as_of):
    g = gw(as_of)
    out = g.prepare_provider_request({"model": "m", "store": True})
    assert out["store"] is False and g.check_provider_request(out) == []
    assert g.check_provider_request({"model": "m"}) != []


def test_every_decision_audited_in_intact_chain(as_of):
    g = gw(as_of)
    for t in NEVER:
        g.route(rec(t), "training_corpus", as_of)
    assert len(g.audit.entries) == 4 and g.audit.verify(g.audit.entries) is None
    assert all(e["body"]["allowed"] is False for e in g.audit.entries)
