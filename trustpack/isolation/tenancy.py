"""Tenant isolation by construction: each tenant has its own index, namespace and key.

The caller's tenant comes from the authenticated identity, never from the request body. Every
read path (search, get, list, cache) resolves the caller's own index first, so there is no code
path that can name another tenant's index. Each document carries an HMAC tag made with the
tenant's derived key; a document moved into the wrong index fails verification on read.
(Integrity tags, not encryption: production would add Key Vault customer-managed keys.)
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field


class CrossTenantError(PermissionError):
    pass


@dataclass
class _Tenant:
    name: str
    index: str
    namespace: str
    key_id: str
    key: bytes
    docs: dict[str, dict] = field(default_factory=dict)
    cache: dict[str, str] = field(default_factory=dict)


class TenantStore:
    def __init__(self, master_key: bytes):
        if len(master_key) < 16:
            raise ValueError("master key must be at least 16 bytes")
        self._master = master_key
        self._tenants: dict[str, _Tenant] = {}

    def onboard(self, tenant: str) -> dict:
        if tenant in self._tenants:
            raise ValueError(f"tenant {tenant} exists")
        key = hmac.new(self._master, f"tenant-key|{tenant}".encode(), hashlib.sha256).digest()
        key_id = "kid-" + hashlib.sha256(key).hexdigest()[:12]
        t = _Tenant(tenant, f"idx-{tenant}", f"ns-{tenant}", key_id, key)
        self._tenants[tenant] = t
        return {"tenant": tenant, "index": t.index, "namespace": t.namespace, "key_id": key_id}

    def _own(self, caller: str) -> _Tenant:
        if caller not in self._tenants:
            raise CrossTenantError(f"unknown caller tenant '{caller}'")
        return self._tenants[caller]

    def _tag(self, t: _Tenant, doc_id: str, text: str) -> str:
        return hmac.new(t.key, f"{t.namespace}|{doc_id}|{text}".encode(), hashlib.sha256).hexdigest()

    def add(self, caller: str, doc_id: str, text: str) -> None:
        t = self._own(caller)
        t.docs[doc_id] = {"text": text, "tag": self._tag(t, doc_id, text), "key_id": t.key_id}

    def _verified(self, t: _Tenant, doc_id: str, d: dict) -> bool:
        return d["key_id"] == t.key_id and hmac.compare_digest(d["tag"], self._tag(t, doc_id, d["text"]))

    def search(self, caller: str, query: str, filters: dict | None = None) -> list[str]:
        if filters and any(k in filters for k in ("tenant", "index", "namespace")):
            raise CrossTenantError("tenant, index and namespace come from identity, not the request")
        t = self._own(caller)
        words = {w for w in query.lower().split() if w}
        return sorted(i for i, d in t.docs.items()
                      if self._verified(t, i, d) and words & set(d["text"].lower().split()))

    def get(self, caller: str, doc_id: str) -> str | None:
        t = self._own(caller)
        d = t.docs.get(doc_id)
        if d is None:
            return None
        if not self._verified(t, doc_id, d):
            raise CrossTenantError(f"document {doc_id} failed tenant key check in {t.index}")
        return d["text"]

    def list_ids(self, caller: str) -> list[str]:
        return sorted(self._own(caller).docs)

    def cache_put(self, caller: str, key: str, value: str) -> None:
        t = self._own(caller)
        t.cache[f"{t.namespace}:{key}"] = value

    def cache_get(self, caller: str, key: str) -> str | None:
        t = self._own(caller)
        return t.cache.get(f"{t.namespace}:{key}")

    def describe(self, tenant: str) -> dict:
        t = self._own(tenant)
        return {"tenant": t.name, "index": t.index, "namespace": t.namespace, "key_id": t.key_id}

    def _raw_move(self, src: str, dst: str, doc_id: str) -> None:
        """Test hook: simulate a storage bug that copies a doc into another tenant's index."""
        self._tenants[dst].docs[doc_id] = dict(self._tenants[src].docs[doc_id])


def cross_tenant_canary_suite(store: TenantStore, tenants: list[str]) -> list[dict]:
    """Plant a unique canary per tenant, then try to reach it from every other tenant by every path."""
    canaries = {}
    for t in tenants:
        token = "canary" + hashlib.sha256(t.encode()).hexdigest()[:10]
        store.add(t, f"canary-{t}", f"{token} secret note for {t}")
        store.cache_put(t, "last_answer", token)
        canaries[t] = token
    results = []
    for victim, token in canaries.items():
        for attacker in tenants:
            if attacker == victim:
                continue
            leaks = []
            if store.search(attacker, token):
                leaks.append("search")
            if store.get(attacker, f"canary-{victim}") is not None:
                leaks.append("get")
            if f"canary-{victim}" in store.list_ids(attacker):
                leaks.append("list")
            if store.cache_get(attacker, "last_answer") == token:
                leaks.append("cache")
            try:
                store.search(attacker, token, filters={"tenant": victim})
                leaks.append("filter-override")
            except CrossTenantError:
                pass
            results.append({"attacker": attacker, "victim": victim, "leaks": leaks})
    return results
