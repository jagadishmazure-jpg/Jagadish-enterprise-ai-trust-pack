import json
import pathlib
import re

import pytest

from trustpack.residency import REQUIRED_CLASSES, check_config, denied_skus, load_config, processing_scope
from trustpack.residency.check import report
from trustpack.residency.policy import allowed_locations_rule, deny_deployment_rule, policy_files
from trustpack.residency.regions import DEPLOYMENT_TYPES

ROOT = pathlib.Path(__file__).resolve().parent.parent


def codes(cfg):
    return sorted(f.code for f in check_config(cfg))


@pytest.mark.parametrize("name", ["fernhollow-bank-eu", "marlowe-freight-us"])
def test_shipped_configs_pass(name):
    assert check_config(load_config(name)) == []


def test_broken_example_catches_every_rule_it_breaks():
    assert codes(load_config("broken-example")) == ["RES001", "RES003", "RES003", "RES005", "RES006", "RES007"]


@pytest.mark.parametrize("cls", REQUIRED_CLASSES)
def test_missing_data_class_flagged(eu_cfg, cls):
    del eu_cfg["data_classes"][cls]
    assert "RES001" in codes(eu_cfg)


def test_required_classes_cover_buyer_list():
    for c in ("prompts", "logs", "embeddings", "caches", "backups"):
        assert c in REQUIRED_CLASSES


@pytest.mark.parametrize("sku,scope", [("GlobalStandard", "global"), ("GlobalBatch", "global"),
                                       ("DataZoneStandard", "data_zone"), ("DataZoneProvisionedManaged", "data_zone"),
                                       ("Standard", "geography"), ("ProvisionedManaged", "geography"),
                                       ("DeveloperTier", "global")])
def test_foundry_deployment_scope(sku, scope):
    assert processing_scope(sku) == scope


def test_unknown_sku_rejected():
    with pytest.raises(ValueError):
        processing_scope("SuperGlobal")


def test_global_deployment_breaks_eu_zone(eu_cfg):
    eu_cfg["model_deployments"][0]["sku"] = "GlobalStandard"
    assert codes(eu_cfg) == ["RES004"]


def test_data_zone_deployment_breaks_geography_boundary(us_cfg):
    us_cfg["model_deployments"][0]["sku"] = "DataZoneStandard"
    assert codes(us_cfg) == ["RES004"]


def test_standard_deployment_is_fine_inside_eu_zone(eu_cfg):
    eu_cfg["model_deployments"][0]["sku"] = "Standard"
    assert codes(eu_cfg) == []


def test_deployment_region_outside_zone(eu_cfg):
    eu_cfg["model_deployments"][0]["region"] = "eastus2"
    assert "RES004" in codes(eu_cfg)


def test_cross_region_fallback_needs_consent(eu_cfg):
    eu_cfg["model_deployments"][1]["region"] = "francecentral"
    assert codes(eu_cfg) == ["RES005"]
    eu_cfg["consent"]["cross_region_fallback"] = True
    assert codes(eu_cfg) == []


def test_consent_cannot_override_boundary(eu_cfg):
    eu_cfg["consent"]["cross_region_fallback"] = True
    eu_cfg["model_deployments"][1].update(region="eastus2")
    assert "RES006" in codes(eu_cfg)


def test_global_fallback_in_same_region_still_fails(eu_cfg):
    eu_cfg["model_deployments"][1]["sku"] = "GlobalStandard"
    assert codes(eu_cfg) == ["RES006"]


def test_backup_replica_outside_boundary(eu_cfg):
    eu_cfg["data_classes"]["backups"]["replica_region"] = "uksouth"
    assert codes(eu_cfg) == ["RES003"]


def test_unknown_region_flagged(eu_cfg):
    eu_cfg["data_classes"]["caches"]["region"] = "moonbase1"
    assert "RES002" in codes(eu_cfg)


def test_report_shows_pass_and_scope():
    text = report(load_config("fernhollow-bank-eu"))
    assert "findings: 0 (PASS)" in text and "scope=data_zone" in text


def test_denied_skus_by_scope():
    assert denied_skus("data_zone") == ["DeveloperTier", "GlobalBatch", "GlobalProvisionedManaged", "GlobalStandard"]
    assert "DataZoneStandard" in denied_skus("geography") and "Standard" not in denied_skus("geography")
    assert denied_skus("global") == []


def test_policy_json_matches_python_rules():
    files = policy_files()
    assert files["deny-loose-ai-deployments.json"]["policyRule"] == deny_deployment_rule()
    assert files["allowed-locations-ai-data.json"]["policyRule"] == allowed_locations_rule()


def test_policy_targets_foundry_deployment_sku_alias():
    rule = json.dumps(deny_deployment_rule())
    assert "Microsoft.CognitiveServices/accounts/deployments/sku.name" in rule


def _tf_default(name):
    text = (ROOT / "infra/terraform/variables.tf").read_text()
    block = text[text.index(f'variable "{name}"'):]
    return re.findall(r'"([^"]+)"', block[block.index("default"):block.index("]")])


def _bicep_default(name):
    text = (ROOT / "infra/bicep/main.bicep").read_text()
    block = text[text.index(f"param {name} array"):]
    return re.findall(r"'([^']+)'", block[:block.index("]")])


def test_terraform_bicep_python_denied_sku_parity():
    assert _tf_default("denied_skus") == _bicep_default("deniedSkus") == denied_skus("data_zone")


def test_terraform_bicep_allowed_locations_parity():
    eu = load_config("fernhollow-bank-eu")
    assert _tf_default("allowed_locations") == _bicep_default("allowedLocations") == eu["allowed_regions"]


def test_both_iac_stacks_load_the_same_policy_files():
    tf = (ROOT / "infra/terraform/main.tf").read_text()
    bicep = (ROOT / "infra/bicep/main.bicep").read_text()
    for f in policy_files():
        assert f in tf and f in bicep


def test_no_deprecated_product_name_anywhere():
    bad = "Azure " + "AI Foundry"
    for p in ROOT.rglob("*"):
        if p.is_file() and p.suffix in {".py", ".md", ".yaml", ".tf", ".bicep", ".json", ".html"} and ".git" not in p.parts:
            assert bad not in p.read_text(errors="ignore"), p


def test_every_deployment_type_has_known_scope():
    assert set(DEPLOYMENT_TYPES.values()) <= {"global", "data_zone", "geography"}
