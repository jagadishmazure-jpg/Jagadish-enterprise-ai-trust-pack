"""Azure Policy rules for residency, shared by Terraform and Bicep.

Both IaC stacks read the same JSON files in infra/policies/, so there is one source of truth.
This module rebuilds the expected rules in Python so tests can prove the JSON did not drift.
"""
from __future__ import annotations

import json

from ..common import ROOT
from .regions import DEPLOYMENT_TYPES, STRICTNESS

POLICY_DIR = ROOT / "infra" / "policies"


def denied_skus(boundary_scope: str) -> list[str]:
    """Deployment SKUs whose processing scope is looser than the boundary."""
    need = STRICTNESS[boundary_scope]
    return sorted(s for s, scope in DEPLOYMENT_TYPES.items() if STRICTNESS[scope] < need)


def deny_deployment_rule() -> dict:
    return {
        "if": {"allOf": [
            {"field": "type", "equals": "Microsoft.CognitiveServices/accounts/deployments"},
            {"field": "Microsoft.CognitiveServices/accounts/deployments/sku.name",
             "in": "[parameters('deniedSkus')]"},
        ]},
        "then": {"effect": "[parameters('effect')]"},
    }


def allowed_locations_rule() -> dict:
    return {
        "if": {"allOf": [
            {"field": "location", "notIn": "[parameters('allowedLocations')]"},
            {"field": "location", "notEquals": "global"},
            {"field": "tags['data-class']", "exists": "true"},
        ]},
        "then": {"effect": "[parameters('effect')]"},
    }


def policy_files() -> dict[str, dict]:
    return {p.name: json.loads(p.read_text()) for p in sorted(POLICY_DIR.glob("*.json"))}
