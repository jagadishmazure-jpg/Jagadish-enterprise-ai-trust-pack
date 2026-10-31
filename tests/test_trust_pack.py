import copy
import pathlib

import pytest

from trustpack.common import PKG, ROOT, TEMPLATE_LABEL
from trustpack.trust_pack import build_html, check_mappings, load_mappings, load_questions
from trustpack.trust_pack.portal import OUT, TEMPLATES

TEMPLATE_FILES = sorted(TEMPLATES.glob("*.md"))


def test_nine_questions():
    assert [q["id"] for q in load_questions()] == [f"Q{i}" for i in range(1, 10)]


def test_every_question_evidence_path_exists():
    for q in load_questions():
        for p in q["evidence"]:
            assert (ROOT / p).exists(), f"{q['id']}: {p}"


def test_mappings_valid():
    assert check_mappings() == []


def test_three_frameworks_mapped():
    fw = load_mappings()
    assert set(fw) == {"soc2_tsc", "iso27001_annex_a", "iso42001_annex_a"}
    assert len(fw["soc2_tsc"]["controls"]) == 12 and len(fw["iso27001_annex_a"]["controls"]) == 16
    assert len(fw["iso42001_annex_a"]["controls"]) == 9


def test_mapping_errors_detected():
    fw = copy.deepcopy(load_mappings())
    fw["soc2_tsc"]["controls"][0]["evidence"].append("no/such/file.py")
    fw["soc2_tsc"]["controls"][1]["questions"].append("Q42")
    errs = check_mappings(fw)
    assert any("missing" in e for e in errs) and any("Q42" in e for e in errs)


def test_unmapped_question_detected():
    fw = copy.deepcopy(load_mappings())
    for c in fw["iso27001_annex_a"]["controls"]:
        c["questions"] = [q for q in c["questions"] if q != "Q8"]
    assert "Q8 has no iso27001_annex_a control" in check_mappings(fw)


@pytest.mark.parametrize("path", TEMPLATE_FILES, ids=lambda p: p.name)
def test_every_template_labelled(path):
    assert TEMPLATE_LABEL in path.read_text()


def test_required_documents_present():
    names = {p.name for p in TEMPLATE_FILES}
    assert {"dpa.md", "dpia.md", "model_card.md", "pentest_letter.md"} <= names


def test_dpa_has_residency_annex_and_30_day_notice():
    t = (TEMPLATES / "dpa.md").read_text()
    assert "Annex 1: Data residency" in t and "30 days" in t and "Microsoft Foundry" in t


def test_pentest_letter_not_real():
    assert "NOT A REAL PEN TEST" in (TEMPLATES / "pentest_letter.md").read_text()


def test_portal_is_deterministic_and_committed():
    page = build_html()
    assert page == build_html()
    assert OUT.read_text() == page


def test_portal_covers_nine_questions_and_banner():
    page = build_html()
    for i in range(1, 10):
        assert f"id='q{i}'" in page
    assert TEMPLATE_LABEL in page and "Not an audit report" in page


def test_portal_has_strict_csp_and_no_scripts():
    page = build_html()
    assert "default-src 'none'" in page and "<script" not in page.lower()


def test_portal_escapes_content(monkeypatch):
    from trustpack.trust_pack import portal
    orig = portal.load_questions
    def evil():
        qs = orig()
        qs[0] = dict(qs[0], title="<script>alert(1)</script>")
        return qs
    monkeypatch.setattr(portal, "load_questions", evil)
    page = portal.build_html()
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page


def test_nda_gated_docs_marked():
    page = build_html()
    assert "NDA-gated" in page


def test_mapping_titles_are_short_paraphrases():
    for f in load_mappings().values():
        for c in f["controls"]:
            assert len(c["title"].split()) <= 10, c


def test_questions_point_to_existing_modules():
    for q in load_questions():
        assert (ROOT / q["module"]).is_dir()
        assert pathlib.Path(PKG).name in q["module"]
