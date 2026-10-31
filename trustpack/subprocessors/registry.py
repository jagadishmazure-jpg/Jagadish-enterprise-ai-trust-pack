"""Subprocessor registry: validate, diff two versions, and enforce a 30-day change-notice window."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..common import PKG, load_yaml
from ..residency.regions import REGIONS

REGISTRY = PKG / "subprocessors" / "registry.yaml"
HISTORY = PKG / "subprocessors" / "history"
NOTICE_DAYS = 30
REQUIRED_ROLES = ("llm_provider", "cloud_host", "vector_db", "observability")
FIELDS = ("name", "role", "purpose", "region", "data_classes", "dpa_signed")
WATCHED = ("role", "purpose", "region", "data_classes", "transfer_mechanism", "content_redacted")


def load_registry(path=REGISTRY) -> dict:
    return load_yaml(path)


def validate(reg: dict) -> list[str]:
    errs = []
    names = [s.get("name") for s in reg.get("subprocessors", [])]
    for dup in sorted({n for n in names if names.count(n) > 1}):
        errs.append(f"duplicate subprocessor '{dup}'")
    for s in reg.get("subprocessors", []):
        for f in FIELDS:
            if f not in s:
                errs.append(f"{s.get('name', '?')}: missing '{f}'")
        if s.get("region") and s["region"] not in REGIONS:
            errs.append(f"{s['name']}: unknown region '{s['region']}'")
        if s.get("dpa_signed") is False:
            errs.append(f"{s['name']}: no signed DPA")
    roles = {s.get("role") for s in reg.get("subprocessors", [])}
    errs += [f"no '{r}' hop listed (every hop must be listed)" for r in REQUIRED_ROLES if r not in roles]
    return errs


def check_boundary(reg: dict, data_zone: str) -> list[str]:
    """Hops that carry customer data outside the tenant data zone need a transfer mechanism."""
    out = []
    for s in reg["subprocessors"]:
        if not s.get("data_classes"):
            continue
        if REGIONS.get(s["region"], {}).get("data_zone") == data_zone:
            continue
        if not s.get("transfer_mechanism"):
            out.append(f"{s['name']}: {s['region']} is outside {data_zone} and has no transfer mechanism")
        elif not s.get("content_redacted"):
            out.append(f"{s['name']}: outside {data_zone}; content must be redacted before transfer")
    return out


@dataclass(frozen=True)
class Change:
    kind: str  # added | removed | changed
    name: str
    detail: str

    @property
    def needs_notice(self) -> bool:
        return self.kind in ("added", "changed")


def diff(old: dict, new: dict) -> list[Change]:
    o = {s["name"]: s for s in old["subprocessors"]}
    n = {s["name"]: s for s in new["subprocessors"]}
    out = [Change("added", k, f"{n[k]['role']} in {n[k]['region']} for {n[k]['purpose']}") for k in sorted(n.keys() - o.keys())]
    out += [Change("removed", k, "no longer used") for k in sorted(o.keys() - n.keys())]
    for k in sorted(o.keys() & n.keys()):
        for f in WATCHED:
            if o[k].get(f) != n[k].get(f):
                out.append(Change("changed", k, f"{f}: {o[k].get(f)!r} -> {n[k].get(f)!r}"))
    return out


def validate_notice(changes: list[Change], notice_date: date, effective_date: date,
                    days: int = NOTICE_DAYS) -> list[str]:
    gap = (effective_date - notice_date).days
    if any(c.needs_notice for c in changes) and gap < days:
        return [f"notice given {gap} days before effect; contract requires {days}"]
    return []


def notice_markdown(changes: list[Change], notice_date: date, effective_date: date, version: str) -> str:
    lines = [f"# Subprocessor change notice ({version})", "", "_Template, not certified._", "",
             f"Notice date: {notice_date.isoformat()}  ", f"Effective date: {effective_date.isoformat()}  ",
             f"Objection window: {(effective_date - notice_date).days} days (contract minimum {NOTICE_DAYS})", "",
             "| Change | Subprocessor | Detail |", "|---|---|---|"]
    lines += [f"| {c.kind} | {c.name} | {c.detail} |" for c in changes]
    return "\n".join(lines) + "\n"


def main() -> int:
    old = load_registry(sorted(HISTORY.glob("*.yaml"))[-1])
    new = load_registry()
    print(f"registry {new['version']}: {len(new['subprocessors'])} hops, validation errors: {len(validate(new))}")
    for s in new["subprocessors"]:
        print(f"  {s['role']:<17} {s['name']:<25} {s['purpose']:<20} {s['region']}")
    changes = diff(old, new)
    print(f"changes since {old['version']}: {len(changes)}")
    for c in changes:
        print(f"  {c.kind:<8} {c.name}: {c.detail}")
    nd, ed = date(2026, 10, 1), date(2026, 11, 1)
    print(f"notice {nd} -> effective {ed}: {validate_notice(changes, nd, ed) or f'OK ({(ed - nd).days} days)'}")
    print(f"EU boundary check: {check_boundary(new, 'EU') or 'OK'}")
    return 0

