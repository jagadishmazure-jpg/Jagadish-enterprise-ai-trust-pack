"""Incident engine: severity, deadlines, phase order, and a tabletop simulator.

All times are hours from awareness (t=0). A scenario lists when each phase happened; the
simulator checks the phase order and every deadline and prints a pass/miss table.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..common import PKG, load_yaml

RUNBOOKS = PKG / "incidents" / "runbooks.yaml"
SCENARIOS = PKG / "incidents" / "scenarios"
SEVERITIES = ("SEV1", "SEV2", "SEV3", "SEV4")
ORDER = ("detect", "contain", "notify", "rca")


def load_runbooks(path=RUNBOOKS) -> dict:
    return load_yaml(path)


def classify(kind: str, *, tenants_affected: int = 1, personal_data_exposed: bool = False,
             ongoing: bool = False, runbooks: dict | None = None) -> str:
    """Start from the runbook default and escalate on blast radius. Never downgrades."""
    rb = (runbooks or load_runbooks())["runbooks"][kind]
    level = SEVERITIES.index(rb["default_severity"])
    if personal_data_exposed:
        level = min(level, 1)
    if tenants_affected > 1:
        level -= 1
    if ongoing:
        level -= 1
    return SEVERITIES[max(level, 0)]


def deadlines(kind: str, severity: str, personal_data_exposed: bool, runbooks: dict | None = None) -> dict:
    w = (runbooks or load_runbooks())["windows"]
    out = {"contain": w["contain_hours"][severity], "notify_customer": w["contract_hours"][severity],
           "rca": w["rca_hours"][severity]}
    if personal_data_exposed:
        out["regulator_clock"] = w["regulator_hours"]
    return {k: v for k, v in out.items() if v is not None}


@dataclass(frozen=True)
class Check:
    name: str
    due: float | None
    done: float | None

    @property
    def met(self) -> bool:
        return self.done is not None and (self.due is None or self.done <= self.due)


def simulate(scenario: dict, runbooks: dict | None = None) -> dict:
    rbs = runbooks or load_runbooks()
    kind = scenario["kind"]
    pd = scenario.get("personal_data_exposed", rbs["runbooks"][kind]["personal_data"])
    sev = classify(kind, tenants_affected=scenario.get("tenants_affected", 1), personal_data_exposed=pd,
                   ongoing=scenario.get("ongoing", False), runbooks=rbs)
    due = deadlines(kind, sev, pd, rbs)
    t = scenario["timeline"]
    errors = []
    seen = [p for p in ORDER if p in t]
    if "detect" not in t:
        errors.append("no detect time")
    for a, b in (("detect", "contain"), ("detect", "notify"), ("contain", "rca")):
        if a in t and b in t and t[b] < t[a]:
            errors.append(f"{b} happened before {a}")
    checks = [Check("contain", due.get("contain"), t.get("contain")),
              Check("notify_customer", due.get("notify_customer"), t.get("notify")),
              Check("rca", due.get("rca"), t.get("rca"))]
    if "regulator_clock" in due:
        checks.append(Check("controller_can_meet_72h", due["regulator_clock"] - 24, t.get("notify")))
    return {"name": scenario["name"], "kind": kind, "severity": sev, "personal_data": pd, "phases": seen,
            "checks": checks, "errors": errors,
            "passed": not errors and all(c.met for c in checks)}


def format_result(r: dict) -> str:
    lines = [f"{r['name']}: {r['kind']} {r['severity']} personal_data={r['personal_data']} "
             f"-> {'PASS' if r['passed'] else 'MISS'}"]
    for c in r["checks"]:
        done = "-" if c.done is None else f"{c.done:g}h"
        lines.append(f"  {c.name:<24} due {c.due:>4g}h  done {done:>6}  {'ok' if c.met else 'MISSED'}")
    lines += [f"  error: {e}" for e in r["errors"]]
    return "\n".join(lines)


def load_scenarios() -> list[dict]:
    return [load_yaml(p) for p in sorted(SCENARIOS.glob("*.yaml"))]


def tabletop() -> int:
    results = [simulate(s) for s in load_scenarios()]
    for r in results:
        print(format_result(r))
    passed = sum(r["passed"] for r in results)
    print(f"tabletop: {passed}/{len(results)} scenarios met every deadline")
    return 0
