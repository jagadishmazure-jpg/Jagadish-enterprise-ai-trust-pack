"""Suite hooks and the aggregated security report.

A suite is any function registered with @suite("name") that returns CaseResult rows. External
tools (a red-team harness, a scanner) can be added with ingest_external() from their JSON output.
The report keeps known misses visible instead of hiding them.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..common import PKG, load_yaml
from . import guard

CASES = PKG / "security_tests" / "cases"
_REGISTRY: dict[str, Callable[[], list[CaseResult]]] = {}


@dataclass(frozen=True)
class CaseResult:
    suite: str
    case_id: str
    expected: str  # "block" | "allow"
    actual: str
    known_miss: bool = False

    @property
    def passed(self) -> bool:
        return self.expected == self.actual


def suite(name: str):
    def deco(fn):
        _REGISTRY[name] = fn
        return fn
    return deco


def registered() -> list[str]:
    return sorted(_REGISTRY)


def _cases(name: str) -> list[dict]:
    return load_yaml(CASES / f"{name}.yaml")["cases"]


@suite("injection")
def run_injection() -> list[CaseResult]:
    return [CaseResult("injection", c["id"], c["expect"], "block" if guard.detect_injection(c["text"]) else "allow",
                       c.get("known_miss", False)) for c in _cases("injection")]


@suite("jailbreak")
def run_jailbreak() -> list[CaseResult]:
    return [CaseResult("jailbreak", c["id"], c["expect"], "block" if guard.detect_jailbreak(c["text"]) else "allow",
                       c.get("known_miss", False)) for c in _cases("jailbreak")]


@suite("pii")
def run_pii() -> list[CaseResult]:
    out = []
    for c in _cases("pii"):
        _, found = guard.redact(c["text"])
        out.append(CaseResult("pii", c["id"], c["expect"], "block" if found else "allow", c.get("known_miss", False)))
    return out


def ingest_external(name: str, rows: list[dict]) -> list[CaseResult]:
    """Turn another tool's results ({id, expected, actual}) into CaseResults."""
    return [CaseResult(name, r["id"], r["expected"], r["actual"], r.get("known_miss", False)) for r in rows]


def summarise(results: list[CaseResult]) -> dict:
    attacks = [r for r in results if r.expected == "block"]
    benign = [r for r in results if r.expected == "allow"]
    return {"cases": len(results), "attacks": len(attacks), "blocked": sum(r.actual == "block" for r in attacks),
            "missed": [r.case_id for r in attacks if r.actual != "block"],
            "benign": len(benign), "false_positives": [r.case_id for r in benign if r.actual == "block"],
            "unexpected": [r.case_id for r in results if not r.passed and not r.known_miss]}


def aggregate(extra: dict[str, list[CaseResult]] | None = None) -> dict:
    per = {name: summarise(_REGISTRY[name]()) for name in registered()}
    for name, rows in (extra or {}).items():
        per[name] = summarise(rows)
    total_attacks = sum(s["attacks"] for s in per.values())
    total_blocked = sum(s["blocked"] for s in per.values())
    return {"label": "Synthetic regression checks, not a pen test", "suites": per,
            "attacks": total_attacks, "blocked": total_blocked,
            "gate_passed": all(not s["unexpected"] for s in per.values())}


def format_report(rep: dict) -> str:
    lines = [f"security report ({rep['label']})",
             f"{'suite':<10} {'cases':>5} {'attacks':>7} {'blocked':>7} {'benign':>6} {'false+':>6}  known misses"]
    for name, s in rep["suites"].items():
        lines.append(f"{name:<10} {s['cases']:>5} {s['attacks']:>7} {s['blocked']:>7} {s['benign']:>6} "
                     f"{len(s['false_positives']):>6}  {', '.join(s['missed']) or '-'}")
    lines.append(f"total blocked {rep['blocked']}/{rep['attacks']}; gate (no unexpected results): "
                 f"{'PASS' if rep['gate_passed'] else 'FAIL'}")
    return "\n".join(lines)
