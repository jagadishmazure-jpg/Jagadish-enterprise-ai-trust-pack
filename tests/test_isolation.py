from datetime import timedelta

import pytest

from trustpack.isolation import MAX_GRANT, AccessDenied, CrossTenantError, SupportAccess, TenantStore
from trustpack.isolation import cross_tenant_canary_suite as suite

KEY = b"isolation-test-master-key-000000"
TENANTS = ["fernhollow-bank", "marlowe-freight", "pellucid-insure"]


@pytest.fixture
def store():
    s = TenantStore(KEY)
    for t in TENANTS:
        s.onboard(t)
    return s


def test_each_tenant_has_own_index_namespace_and_key(store):
    d = [store.describe(t) for t in TENANTS]
    for field in ("index", "namespace", "key_id"):
        assert len({x[field] for x in d}) == 3


def test_short_master_key_rejected():
    with pytest.raises(ValueError):
        TenantStore(b"short")


def test_duplicate_onboarding_rejected(store):
    with pytest.raises(ValueError):
        store.onboard("fernhollow-bank")


def test_canary_suite_no_leaks(store):
    res = suite(store, TENANTS)
    assert len(res) == 6 and all(r["leaks"] == [] for r in res)


def test_own_tenant_can_find_its_canary(store):
    suite(store, TENANTS)
    assert store.search("fernhollow-bank", "secret") == ["canary-fernhollow-bank"]


def test_filter_override_rejected(store):
    with pytest.raises(CrossTenantError):
        store.search("marlowe-freight", "x", filters={"tenant": "fernhollow-bank"})


@pytest.mark.parametrize("key", ["index", "namespace"])
def test_index_or_namespace_override_rejected(store, key):
    with pytest.raises(CrossTenantError):
        store.search("marlowe-freight", "x", filters={key: "idx-fernhollow-bank"})


def test_unknown_caller_rejected(store):
    with pytest.raises(CrossTenantError):
        store.search("not-a-tenant", "x")


def test_same_doc_id_in_two_tenants_stays_separate(store):
    store.add("fernhollow-bank", "doc-1", "fernhollow pricing")
    store.add("marlowe-freight", "doc-1", "marlowe pricing")
    assert store.get("fernhollow-bank", "doc-1") == "fernhollow pricing"
    assert store.get("marlowe-freight", "doc-1") == "marlowe pricing"


def test_cache_keys_namespaced(store):
    store.cache_put("fernhollow-bank", "q", "A")
    assert store.cache_get("marlowe-freight", "q") is None


def test_storage_bug_copy_detected_by_tenant_key(store):
    store.add("fernhollow-bank", "doc-9", "confidential merger plan")
    store._raw_move("fernhollow-bank", "marlowe-freight", "doc-9")
    with pytest.raises(CrossTenantError):
        store.get("marlowe-freight", "doc-9")
    assert store.search("marlowe-freight", "merger") == []


class LeakyCacheStore(TenantStore):
    """Simulates a real bug: the cache key forgets the tenant namespace."""

    def cache_put(self, caller, key, value):
        self._own(caller)
        self.__dict__.setdefault("shared", {})[key] = value

    def cache_get(self, caller, key):
        self._own(caller)
        return self.__dict__.get("shared", {}).get(key)


def test_canary_suite_catches_a_namespace_bug():
    s = LeakyCacheStore(KEY)
    for t in TENANTS:
        s.onboard(t)
    leaks = [r for r in suite(s, TENANTS) if r["leaks"]]
    assert leaks and all(r["leaks"] == ["cache"] for r in leaks)


@pytest.fixture
def sa():
    return SupportAccess({"fernhollow-bank": {"admin-fh"}})


def grant(sa, as_of, **kw):
    args = {"engineer": "eng-ravi", "tenant": "fernhollow-bank", "actions": {"read_logs_redacted"},
            "ticket": "SUP-1", "reason": "debug", "at": as_of}
    args.update(kw)
    return sa.request(**args)


def test_no_standing_access(sa, as_of):
    assert not sa.check("eng-ravi", "fernhollow-bank", "read_logs_redacted", as_of)


def test_unapproved_grant_denied(sa, as_of):
    grant(sa, as_of)
    assert not sa.check("eng-ravi", "fernhollow-bank", "read_logs_redacted", as_of + timedelta(minutes=1))


def test_approved_grant_allows_scoped_action_until_expiry(sa, as_of):
    g = grant(sa, as_of)
    sa.approve(g.grant_id, "admin-fh", as_of)
    assert sa.check("eng-ravi", "fernhollow-bank", "read_logs_redacted", as_of + timedelta(hours=1))
    assert not sa.check("eng-ravi", "fernhollow-bank", "read_documents", as_of + timedelta(hours=1))
    assert not sa.check("eng-ravi", "fernhollow-bank", "read_logs_redacted", as_of + timedelta(hours=2))


def test_grant_does_not_cross_tenants(sa, as_of):
    g = grant(sa, as_of)
    sa.approve(g.grant_id, "admin-fh", as_of)
    assert not sa.check("eng-ravi", "marlowe-freight", "read_logs_redacted", as_of + timedelta(minutes=5))


def test_only_customer_admin_can_approve(sa, as_of):
    g = grant(sa, as_of)
    with pytest.raises(AccessDenied):
        sa.approve(g.grant_id, "eng-other", as_of)


def test_self_approval_blocked(as_of):
    sa = SupportAccess({"fernhollow-bank": {"eng-ravi"}})
    g = grant(sa, as_of)
    with pytest.raises(AccessDenied):
        sa.approve(g.grant_id, "eng-ravi", as_of)


def test_revoke_ends_access(sa, as_of):
    g = grant(sa, as_of)
    sa.approve(g.grant_id, "admin-fh", as_of)
    sa.revoke(g.grant_id, as_of + timedelta(minutes=10))
    assert not sa.check("eng-ravi", "fernhollow-bank", "read_logs_redacted", as_of + timedelta(minutes=11))


@pytest.mark.parametrize("dur", [MAX_GRANT + timedelta(minutes=1), timedelta(0)])
def test_duration_bounds(sa, as_of, dur):
    with pytest.raises(ValueError):
        grant(sa, as_of, duration=dur)


def test_ticket_and_known_actions_required(sa, as_of):
    with pytest.raises(ValueError):
        grant(sa, as_of, ticket="")
    with pytest.raises(ValueError):
        grant(sa, as_of, actions={"drop_database"})


def test_access_log_complete_and_intact(sa, as_of):
    g = grant(sa, as_of)
    sa.check("eng-ravi", "fernhollow-bank", "read_logs_redacted", as_of)
    sa.approve(g.grant_id, "admin-fh", as_of)
    sa.check("eng-ravi", "fernhollow-bank", "read_logs_redacted", as_of + timedelta(minutes=1))
    events = [e["event"] for e in sa.review("fernhollow-bank")]
    assert events == ["requested", "access", "approved", "access"]
    assert sa.log.verify(sa.log.entries) is None
    denied = [e for e in sa.review("fernhollow-bank") if e["event"] == "access" and not e["allowed"]]
    assert denied[0]["reason"] == "not approved"
