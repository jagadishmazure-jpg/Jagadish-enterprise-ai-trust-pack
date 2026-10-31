import copy
from datetime import date

import pytest

from trustpack.subprocessors import (
    NOTICE_DAYS,
    REQUIRED_ROLES,
    check_boundary,
    diff,
    load_registry,
    notice_markdown,
    validate,
    validate_notice,
)
from trustpack.subprocessors.registry import HISTORY


@pytest.fixture
def reg():
    return copy.deepcopy(load_registry())


@pytest.fixture
def old():
    return load_registry(sorted(HISTORY.glob("*.yaml"))[-1])


def test_current_registry_valid(reg):
    assert validate(reg) == []


def test_every_required_hop_listed(reg):
    roles = {s["role"] for s in reg["subprocessors"]}
    assert set(REQUIRED_ROLES) <= roles


@pytest.mark.parametrize("role", REQUIRED_ROLES)
def test_missing_role_flagged(reg, role):
    reg["subprocessors"] = [s for s in reg["subprocessors"] if s["role"] != role]
    assert any(role in e for e in validate(reg))


@pytest.mark.parametrize("field", ["purpose", "region", "dpa_signed"])
def test_missing_field_flagged(reg, field):
    del reg["subprocessors"][0][field]
    assert any(f"missing '{field}'" in e for e in validate(reg))


def test_unsigned_dpa_flagged(reg):
    reg["subprocessors"][2]["dpa_signed"] = False
    assert any("no signed DPA" in e for e in validate(reg))


def test_duplicate_flagged(reg):
    reg["subprocessors"].append(dict(reg["subprocessors"][0]))
    assert any("duplicate" in e for e in validate(reg))


def test_diff_finds_add_and_region_change(reg, old):
    ch = diff(old, reg)
    kinds = {(c.kind, c.name) for c in ch}
    assert ("added", "Pagerlyn Alerts") in kinds
    assert any(c.kind == "changed" and "region" in c.detail and "eastus2" in c.detail for c in ch)


def test_diff_removal_needs_no_notice(reg, old):
    ch = diff(reg, old)
    removed = [c for c in ch if c.kind == "removed"]
    assert removed and not any(c.needs_notice for c in removed)


def test_diff_of_identical_is_empty(reg):
    assert diff(reg, reg) == []


@pytest.mark.parametrize("days,ok", [(30, True), (31, True), (29, False), (0, False)])
def test_thirty_day_window(reg, old, days, ok):
    nd = date(2026, 10, 1)
    ed = date.fromordinal(nd.toordinal() + days)
    assert (validate_notice(diff(old, reg), nd, ed) == []) is ok


def test_removal_only_can_take_effect_immediately(reg, old):
    assert validate_notice(diff(reg, old)[:0] + [c for c in diff(reg, old) if c.kind == "removed"],
                           date(2026, 10, 1), date(2026, 10, 1)) == []


def test_notice_days_is_thirty():
    assert NOTICE_DAYS == 30


def test_us_observability_needs_transfer_mechanism(reg):
    assert check_boundary(reg, "EU") == []
    obs = next(s for s in reg["subprocessors"] if s["role"] == "observability")
    del obs["transfer_mechanism"]
    assert any("transfer mechanism" in e for e in check_boundary(reg, "EU"))


def test_out_of_zone_hop_must_redact_content(reg):
    obs = next(s for s in reg["subprocessors"] if s["role"] == "observability")
    obs["content_redacted"] = False
    assert any("redacted" in e for e in check_boundary(reg, "EU"))


def test_hop_without_customer_data_is_exempt(reg):
    reg["subprocessors"].append({"name": "Statusboard", "role": "status_page", "purpose": "status",
                                 "region": "eastus", "data_classes": [], "dpa_signed": True})
    assert check_boundary(reg, "EU") == []


def test_notice_markdown_lists_every_change(reg, old):
    ch = diff(old, reg)
    md = notice_markdown(ch, date(2026, 10, 1), date(2026, 11, 1), reg["version"])
    assert "Template, not certified" in md and md.count("\n| ") == len(ch) + 1 and "31 days" in md
