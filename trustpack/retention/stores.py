"""Four in-memory stand-ins for the places customer content lands: prompt log, vector index, cache, traces.

Each store keeps content differently on purpose (rows, vectors with metadata, keyed entries,
span attributes) so a purge has to be written per store, as it would be in production.
"""
from __future__ import annotations

from datetime import datetime, timedelta


class Store:
    name = "store"

    def put(self, subject: str, tenant: str, data_type: str, content: str, at: datetime) -> None:
        raise NotImplementedError

    def records(self) -> list[dict]:
        raise NotImplementedError

    def purge_subject(self, tenant: str, subject: str) -> int:
        raise NotImplementedError

    def expire(self, data_type: str, older_than: datetime) -> int:
        raise NotImplementedError

    def contains_text(self, text: str) -> bool:
        return any(text in r["content"] for r in self.records())

    def count_subject(self, tenant: str, subject: str) -> int:
        return sum(1 for r in self.records() if r["tenant"] == tenant and r["subject"] == subject)


class PromptLog(Store):
    name = "prompt_log"

    def __init__(self):
        self.rows: list[dict] = []

    def put(self, subject, tenant, data_type, content, at):
        self.rows.append({"subject": subject, "tenant": tenant, "data_type": data_type, "content": content, "at": at})

    def records(self):
        return list(self.rows)

    def purge_subject(self, tenant, subject):
        keep = [r for r in self.rows if not (r["tenant"] == tenant and r["subject"] == subject)]
        n = len(self.rows) - len(keep)
        self.rows = keep
        return n

    def expire(self, data_type, older_than):
        keep = [r for r in self.rows if not (r["data_type"] == data_type and r["at"] < older_than)]
        n = len(self.rows) - len(keep)
        self.rows = keep
        return n


class VectorIndex(Store):
    name = "vector_index"

    def __init__(self):
        self.vectors: dict[str, tuple[list[float], dict]] = {}
        self._n = 0

    def put(self, subject, tenant, data_type, content, at):
        self._n += 1
        vec = [float(ord(ch) % 7) for ch in content[:4]]
        self.vectors[f"v{self._n}"] = (vec, {"subject": subject, "tenant": tenant, "data_type": data_type,
                                             "content": content, "at": at})

    def records(self):
        return [m for _, m in self.vectors.values()]

    def purge_subject(self, tenant, subject):
        ids = [k for k, (_, m) in self.vectors.items() if m["tenant"] == tenant and m["subject"] == subject]
        for k in ids:
            del self.vectors[k]
        return len(ids)

    def expire(self, data_type, older_than):
        ids = [k for k, (_, m) in self.vectors.items() if m["data_type"] == data_type and m["at"] < older_than]
        for k in ids:
            del self.vectors[k]
        return len(ids)


class Cache(Store):
    name = "cache"

    def __init__(self):
        self.entries: dict[str, dict] = {}

    def put(self, subject, tenant, data_type, content, at):
        self.entries[f"{tenant}:{subject}:{len(self.entries)}"] = {
            "subject": subject, "tenant": tenant, "data_type": data_type, "content": content, "at": at}

    def records(self):
        return list(self.entries.values())

    def purge_subject(self, tenant, subject):
        ids = [k for k in self.entries if k.startswith(f"{tenant}:{subject}:")]
        for k in ids:
            del self.entries[k]
        return len(ids)

    def expire(self, data_type, older_than):
        ids = [k for k, v in self.entries.items() if v["data_type"] == data_type and v["at"] < older_than]
        for k in ids:
            del self.entries[k]
        return len(ids)


class TraceStore(Store):
    name = "traces"

    def __init__(self):
        self.spans: list[dict] = []

    def put(self, subject, tenant, data_type, content, at):
        self.spans.append({"attributes": {"enduser.id": subject, "tenant": tenant, "gen_ai.prompt": content},
                           "data_type": data_type, "start": at})

    def records(self):
        return [{"subject": s["attributes"]["enduser.id"], "tenant": s["attributes"]["tenant"],
                 "data_type": s["data_type"], "content": s["attributes"]["gen_ai.prompt"], "at": s["start"]}
                for s in self.spans]

    def purge_subject(self, tenant, subject):
        keep = [s for s in self.spans
                if not (s["attributes"]["tenant"] == tenant and s["attributes"]["enduser.id"] == subject)]
        n = len(self.spans) - len(keep)
        self.spans = keep
        return n

    def expire(self, data_type, older_than):
        keep = [s for s in self.spans if not (s["data_type"] == data_type and s["start"] < older_than)]
        n = len(self.spans) - len(keep)
        self.spans = keep
        return n


def default_stores() -> list[Store]:
    return [PromptLog(), VectorIndex(), Cache(), TraceStore()]


def days_ago(now: datetime, days: int) -> datetime:
    return now - timedelta(days=days)
