import copy
import json
import shutil

import pytest

from trustpack.provenance import REQUIRED, changelog, compare, file_sha, load, verify
from trustpack.provenance.manifest import ARTIFACTS, CHANGELOG, all_releases


@pytest.fixture
def sandbox(tmp_path):
    """Copy manifest + artifacts into a temp root so tests can tamper safely."""
    art = tmp_path / "trustpack/provenance/artifacts"
    shutil.copytree(ARTIFACTS, art)
    return tmp_path, art, copy.deepcopy(load())


def test_committed_manifest_verifies():
    assert verify(load()) == []


def test_all_four_components_pinned():
    comps = load()["components"]
    assert set(REQUIRED) == set(comps)
    assert all(len(c["sha256"]) == 64 for c in comps.values())


def test_sources_and_versions_match_release_table():
    c = load()["components"]
    assert (c["base_model"]["source"], c["fine_tune"]["version"], c["prompt_template"]["version"],
            c["guardrails"]["version"]) == ("vendor", "ft-07", "v12", "v3")


@pytest.mark.parametrize("fname", ["prompt_template.txt", "guardrails.yaml", "fine_tune.json", "base_model.json"])
def test_unpinned_edit_fails(sandbox, fname):
    root, art, m = sandbox
    (art / fname).write_text((art / fname).read_text() + "\n# silent change\n")
    errs = verify(m, root=root, artifacts=art)
    assert any("unpinned change" in e for e in errs)


def test_new_unlisted_artifact_fails(sandbox):
    root, art, m = sandbox
    (art / "reranker.json").write_text("{}")
    assert any("not pinned" in e for e in verify(m, root=root, artifacts=art))


def test_missing_component_fails(sandbox):
    root, art, m = sandbox
    del m["components"]["guardrails"]
    errs = verify(m, root=root, artifacts=art)
    assert "guardrails: not in manifest" in errs


@pytest.mark.parametrize("v", ["latest", "main", ""])
def test_floating_version_fails(sandbox, v):
    root, art, m = sandbox
    m["components"]["base_model"]["version"] = v
    assert any("floating version" in e for e in verify(m, root=root, artifacts=art))


def test_repinning_after_edit_passes(sandbox):
    root, art, m = sandbox
    f = art / "prompt_template.txt"
    f.write_text(f.read_text() + "Be concise.\n")
    m["components"]["prompt_template"]["sha256"] = file_sha(f)
    assert verify(m, root=root, artifacts=art) == []


def test_same_version_different_content_rejected():
    old, new = copy.deepcopy(load()), copy.deepcopy(load())
    new["release"] = "v1.5"
    new["components"]["guardrails"]["sha256"] = "f" * 64
    _, errs = compare(old, new)
    assert any("version stayed 'v3'" in e for e in errs)


def test_release_must_bump_when_components_change():
    old, new = copy.deepcopy(load()), copy.deepcopy(load())
    new["components"]["guardrails"].update(sha256="f" * 64, version="v4")
    _, errs = compare(old, new)
    assert any("release stayed" in e for e in errs)


def test_history_compares_cleanly():
    rels = all_releases()
    for a, b in zip(rels[:-1], rels[1:]):
        assert compare(a, b)[1] == []


def test_changelog_newest_first_and_committed():
    text = changelog(all_releases())
    assert text.index("## v1.4") < text.index("## v1.3") < text.index("## v1.2")
    assert "prompt_template: v11 -> v12" in text
    assert CHANGELOG.read_text() == text


def test_manifest_is_valid_json_on_disk():
    from trustpack.provenance.manifest import MANIFEST
    assert json.loads(MANIFEST.read_text())["release"] == "v1.4"
