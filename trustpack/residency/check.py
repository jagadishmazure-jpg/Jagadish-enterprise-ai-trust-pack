"""Check a per-tenant residency config. Pure functions, no network.

Rules (each failure is a Finding with a stable code):
  RES001 a required data class (prompts, logs, embeddings, caches, backups) has no region
  RES002 a data class, replica or deployment uses a region not in the region table
  RES003 a data class or its replica is stored outside the tenant boundary
  RES004 a model deployment type may process data outside the boundary (Microsoft Foundry rules)
  RES005 a fallback deployment sits in another region and the tenant has not consented
  RES006 a fallback deployment is outside the boundary (consent cannot override residency)
  RES007 the config allows a region outside its own boundary
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass

from ..common import PKG, load_yaml
from .regions import DEPLOYMENT_TYPES, REGIONS, STRICTNESS

REQUIRED_CLASSES = ("prompts", "outputs", "logs", "embeddings", "caches", "backups")
DEFAULT_CONFIGS = PKG / "residency" / "configs"


@dataclass(frozen=True)
class Finding:
    code: str
    subject: str
    message: str

    def __str__(self) -> str:
        return f"{self.code} {self.subject}: {self.message}"


def load_config(name_or_path: str | pathlib.Path) -> dict:
    p = pathlib.Path(name_or_path)
    if not p.exists():
        p = DEFAULT_CONFIGS / f"{name_or_path}.yaml"
    return load_yaml(p)


def processing_scope(sku: str) -> str:
    if sku not in DEPLOYMENT_TYPES:
        raise ValueError(f"unknown Microsoft Foundry deployment type: {sku}")
    return DEPLOYMENT_TYPES[sku]


def _in_boundary(region: str, boundary: dict) -> bool:
    info = REGIONS[region]
    if boundary["scope"] == "geography":
        return info["geography"] == boundary["value"]
    if boundary["scope"] == "data_zone":
        return info["data_zone"] == boundary["value"]
    return True


def _deployment_ok(dep: dict, boundary: dict) -> bool:
    scope = processing_scope(dep["sku"])
    if STRICTNESS[scope] < STRICTNESS[boundary["scope"]]:
        return False
    return _in_boundary(dep["region"], boundary)


def check_config(cfg: dict) -> list[Finding]:
    out: list[Finding] = []
    boundary = cfg["boundary"]
    tenant = cfg["tenant"]

    def known(region: str, subject: str) -> bool:
        if region not in REGIONS:
            out.append(Finding("RES002", subject, f"unknown region '{region}'"))
            return False
        return True

    for region in cfg.get("allowed_regions", []):
        if known(region, f"{tenant}.allowed_regions") and not _in_boundary(region, boundary):
            out.append(Finding("RES007", f"{tenant}.allowed_regions",
                               f"'{region}' is outside boundary {boundary['scope']}={boundary['value']}"))

    classes = cfg.get("data_classes", {})
    for name in REQUIRED_CLASSES:
        if name not in classes or not classes[name].get("region"):
            out.append(Finding("RES001", f"{tenant}.{name}", "no storage region declared"))
    for name, spec in classes.items():
        for key in ("region", "replica_region"):
            region = spec.get(key)
            if not region or not known(region, f"{tenant}.{name}.{key}"):
                continue
            if not _in_boundary(region, boundary):
                out.append(Finding("RES003", f"{tenant}.{name}.{key}",
                                   f"stored in '{region}', outside {boundary['value']}"))

    deps = cfg.get("model_deployments", [])
    primary = next((d for d in deps if d.get("role") == "primary"), None)
    for dep in deps:
        subject = f"{tenant}.deploy.{dep['name']}"
        if not known(dep["region"], subject):
            continue
        ok = _deployment_ok(dep, boundary)
        if not ok:
            code = "RES006" if dep.get("role") == "fallback" else "RES004"
            out.append(Finding(code, subject, f"{dep['sku']} in {dep['region']} may process data "
                                              f"outside {boundary['scope']}={boundary['value']}"))
        if (dep.get("role") == "fallback" and primary and dep["region"] != primary["region"]
                and not cfg.get("consent", {}).get("cross_region_fallback", False)):
            out.append(Finding("RES005", subject, f"falls back from {primary['region']} to {dep['region']} "
                                                  "without written customer consent"))
    return out


def report(cfg: dict) -> str:
    findings = check_config(cfg)
    b = cfg["boundary"]
    lines = [f"tenant={cfg['tenant']} boundary={b['scope']}:{b['value']}"]
    for name in REQUIRED_CLASSES:
        spec = cfg.get("data_classes", {}).get(name, {})
        rep = spec.get("replica_region")
        lines.append(f"  {name:<10} {spec.get('region', '-'):<14}" + (f" replica {rep}" if rep else ""))
    for d in cfg.get("model_deployments", []):
        lines.append(f"  model {d['name']:<12} {d['sku']:<18} {d['region']:<14} {d.get('role', '')} "
                     f"scope={processing_scope(d['sku'])}")
    lines.append(f"  findings: {len(findings)}" + ("" if findings else " (PASS)"))
    lines.extend(f"    {f}" for f in findings)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import sys
    names = (argv if argv is not None else sys.argv[1:]) or ["fernhollow-bank-eu", "marlowe-freight-us"]
    failed = 0
    for n in names:
        cfg = load_config(n)
        print(report(cfg))
        failed += bool(check_config(cfg))
    return 1 if failed else 0

