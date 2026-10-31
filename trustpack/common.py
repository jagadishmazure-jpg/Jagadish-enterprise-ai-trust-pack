"""Shared helpers: canonical JSON, SHA-256, hash chains, YAML loading, the template label."""
from __future__ import annotations

import hashlib
import json
import pathlib
from dataclasses import dataclass, field
from typing import Any

import yaml

TEMPLATE_LABEL = "Template, not certified"
GENESIS = "0" * 64
PKG = pathlib.Path(__file__).resolve().parent
ROOT = PKG.parent


def canonical(obj: Any) -> str:
    """Deterministic JSON: sorted keys, no whitespace, UTF-8 kept readable."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def load_yaml(path: str | pathlib.Path) -> Any:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@dataclass
class HashChain:
    """Append-only log where every entry carries the hash of the one before it.

    Changing, removing or reordering any entry breaks every hash after it,
    so ``verify`` reports the first broken index.
    """

    entries: list[dict] = field(default_factory=list)

    @property
    def head(self) -> str:
        return self.entries[-1]["hash"] if self.entries else GENESIS

    def append(self, body: dict) -> dict:
        record = {"index": len(self.entries), "prev": self.head, "body": body}
        record["hash"] = sha256_hex(canonical({k: record[k] for k in ("index", "prev", "body")}))
        self.entries.append(record)
        return record

    @staticmethod
    def verify(entries: list[dict]) -> int | None:
        """Return None if the chain is intact, else the first index that fails."""
        prev = GENESIS
        for i, rec in enumerate(entries):
            expect = sha256_hex(canonical({"index": i, "prev": prev, "body": rec.get("body")}))
            if rec.get("index") != i or rec.get("prev") != prev or rec.get("hash") != expect:
                return i
            prev = rec["hash"]
        return None
