import pytest

from trustpack.incidents import classify, deadlines, load_runbooks, load_scenarios, simulate
from trustpack.incidents.engine import ORDER, format_result

KINDS = ["pii_in_output", "harmful_output", "injection_exfiltration", "model_regression"]


def test_four_ai_runbooks_exist():
    assert sorted(load_runbooks()["runbooks"]) == sorted(KINDS)


@pytest.mark.parametrize("kind", KINDS)
def test_runbook_has_every_phase(kind):
    rb = load_runbooks()["runbooks"][kind]
    for phase in ("detect", "contain", "rca", "notify"):
        assert rb[phase], f"{kind} missing {phase}"


def test_phase_order_is_detect_contain_notify_rca():
    assert ORDER == ("detect", "contain", "notify", "rca")


@pytest.mark.parametrize("kind,sev", [("pii_in_output", "SEV2"), ("harmful_output", "SEV3"),
                                      ("injection_exfiltration", "SEV1"), ("model_regression", "SEV3")])
def test_default_severity(kind, sev):
    assert classify(kind) == sev


def test_personal_data_escalates_to_at_least_sev2():
    assert classify("harmful_output", personal_data_exposed=True) == "SEV2"


def test_blast_radius_and_ongoing_escalate():
    assert classify("model_regression", tenants_affected=3) == "SEV2"
    assert classify("model_regression", tenants_affected=3, ongoing=True) == "SEV1"


def test_severity_never_goes_below_sev1():
    assert classify("injection_exfiltration", tenants_affected=9, ongoing=True) == "SEV1"


def test_contract_windows():
    assert deadlines("injection_exfiltration", "SEV1", True)["notify_customer"] == 24
    assert deadlines("pii_in_output", "SEV2", True)["notify_customer"] == 48


def test_regulator_clock_only_for_personal_data():
    assert deadlines("pii_in_output", "SEV2", True)["regulator_clock"] == 72
    assert "regulator_clock" not in deadlines("harmful_output", "SEV3", False)


def test_sev4_has_no_contract_notice():
    assert "notify_customer" not in deadlines("model_regression", "SEV4", False)


def test_tabletop_results_three_pass_one_kept_failing():
    res = {r["name"].split()[0]: r["passed"] for r in (simulate(s) for s in load_scenarios())}
    assert res == {"tabletop-01": True, "tabletop-02": True, "tabletop-03": True, "tabletop-04": False}


def test_missed_scenario_names_the_missed_checks():
    r = simulate(next(s for s in load_scenarios() if s["name"].startswith("tabletop-04")))
    assert {c.name for c in r["checks"] if not c.met} == {"contain", "notify_customer"}


def test_notify_late_for_controller_72h():
    r = simulate({"name": "t", "kind": "pii_in_output", "timeline": {"detect": 0, "contain": 1, "notify": 50, "rca": 90}})
    missed = {c.name for c in r["checks"] if not c.met}
    assert "notify_customer" in missed and "controller_can_meet_72h" in missed


def test_out_of_order_phases_flagged():
    r = simulate({"name": "t", "kind": "harmful_output", "timeline": {"detect": 5, "contain": 2, "notify": 6, "rca": 8}})
    assert "contain happened before detect" in r["errors"] and not r["passed"]


def test_missing_phase_counts_as_miss():
    r = simulate({"name": "t", "kind": "harmful_output", "timeline": {"detect": 0, "contain": 2}})
    assert not r["passed"] and any(c.name == "notify_customer" and not c.met for c in r["checks"])


def test_format_result_shows_missed():
    r = simulate(load_scenarios()[-1])
    assert "MISSED" in format_result(r) and "MISS" in format_result(r).splitlines()[0]
