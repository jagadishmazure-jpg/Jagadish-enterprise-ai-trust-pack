"""Generate the static trust portal page from live module output.

The page is rebuilt from code on every run (no hand-edited numbers) and written to
docs/trust-portal/index.html. `--check` fails if the committed page is stale.
Everything inserted into the HTML is escaped.
"""
from __future__ import annotations

import html
import pathlib

from ..common import PKG, ROOT, TEMPLATE_LABEL, load_yaml

OUT = ROOT / "docs" / "trust-portal" / "index.html"
TEMPLATES = PKG / "trust_pack" / "templates"
NDA_GATED = {"pentest_letter.md", "dpia.md"}


def load_questions() -> list[dict]:
    return load_yaml(PKG / "trust_pack" / "questions.yaml")["questions"]


def load_mappings() -> dict:
    return load_yaml(PKG / "trust_pack" / "mappings.yaml")["frameworks"]


def check_mappings(frameworks: dict | None = None, root: pathlib.Path = ROOT) -> list[str]:
    fw = frameworks or load_mappings()
    qids = {q["id"] for q in load_questions()}
    errs = []
    for key, f in fw.items():
        ids = [c["id"] for c in f["controls"]]
        errs += [f"{key}: duplicate control {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
        for c in f["controls"]:
            errs += [f"{key} {c['id']}: unknown question {q}" for q in c["questions"] if q not in qids]
            errs += [f"{key} {c['id']}: evidence path missing: {p}" for p in c["evidence"] if not (root / p).exists()]
    for q in sorted(qids):
        for key in ("soc2_tsc", "iso27001_annex_a"):
            if key in fw and not any(q in c["questions"] for c in fw[key]["controls"]):
                errs.append(f"{q} has no {key} control")
    return errs


def _e(x) -> str:
    return html.escape(str(x), quote=True)


def _table(headers: list[str], rows: list[list]) -> str:
    th = "".join(f"<th>{_e(h)}</th>" for h in headers)
    trs = "".join("<tr>" + "".join(f"<td>{_e(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>"


def build_html() -> str:
    from .. import demos
    from ..retention import load_schedule

    qs = {q["id"]: q for q in load_questions()}
    sections: dict[str, str] = {}

    res = demos.residency_summary()
    sections["Q1"] = _table(["Tenant config", "Boundary", "Findings"],
                            [[r["config"], r["boundary"], len(r["findings"])] for r in res]) + \
        "<p>The <code>broken-example</code> config is misconfigured on purpose and must fail.</p>"
    du = demos.data_use_summary()
    sections["Q2"] = _table(["Tenant", "Data type", "Training corpus"],
                            [[r["tenant"], r["data_type"], "allowed (opt-in)" if r["allowed"] else "blocked"]
                             for r in du["rows"]])
    sp = demos.subprocessor_summary()
    sections["Q3"] = _table(["Subprocessor", "Role", "Purpose", "Region"],
                            [[s["name"], s["role"], s["purpose"], s["region"]] for s in sp["registry"]["subprocessors"]]) + \
        f"<p>{len(sp['changes'])} changes since the last published list; 30-day notice window enforced.</p>"
    pv = demos.provenance_summary()
    sections["Q4"] = _table(["Component", "Source", "Version", "sha256 (first 16)"],
                            [[k, c["source"], c["version"], c["sha256"][:16]] for k, c in sorted(pv["components"].items())]) + \
        f"<p>Release {_e(pv['release'])}: provenance check {'passes' if not pv['errors'] else 'FAILS'}.</p>"
    sched = load_schedule()
    rt = demos.retention_summary()
    sections["Q5"] = _table(["Data type", "Retention"],
                            [[k, f"{v['days']} days" if v["days"] is not None else "until deleted"]
                             for k, v in sched["schedule"].items()]) + \
        f"<p>Sample deletion certificate: {_e(rt['certificate']['status'])}, " \
        f"head sha256 {_e(rt['certificate']['head'][:16])}.</p>"
    iso = demos.isolation_summary()
    sections["Q6"] = f"<p>{iso['pairs']} cross-tenant canary pairs probed over 5 read paths: " \
        f"{iso['leaks']} leaks. Vendor support access is just-in-time, customer-approved, " \
        f"expires after at most 4 hours, and every check is logged.</p>"
    inc = demos.incidents_summary()
    sections["Q7"] = _table(["Tabletop", "Severity", "Result"],
                            [[r["name"], r["severity"], "met every deadline" if r["passed"] else "missed a deadline"]
                             for r in inc])
    sec = demos.security_summary()
    sections["Q8"] = _table(["Suite", "Attacks", "Blocked", "False positives"],
                            [[n, s["attacks"], s["blocked"], len(s["false_positives"])] for n, s in sec["suites"].items()]) + \
        "<p>Synthetic regression checks written by the author. Not a penetration test.</p>"
    docs = sorted(p.name for p in TEMPLATES.glob("*.md"))
    sections["Q9"] = _table(["Document", "Access", "Status"],
                            [[d, "NDA-gated" if d in NDA_GATED else "public", TEMPLATE_LABEL] for d in docs]) + \
        _table(["Framework", "Controls mapped"], [[f["name"], len(f["controls"])] for f in load_mappings().values()])

    body = []
    for qid, q in qs.items():
        body.append(f"<section id='{_e(qid.lower())}'><h2>{_e(qid)}. {_e(q['title'])}</h2>"
                    f"<p class='ask'>{_e(q['ask'])}</p>{sections[qid]}"
                    f"<p class='ev'>Evidence: {', '.join('<code>' + _e(p) + '</code>' for p in q['evidence'])}</p>"
                    f"<p class='ev'>Reproduce: <code>{_e(q['command'])}</code></p></section>")
    style = ("body{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#1b1f24}"
             "table{border-collapse:collapse;margin:.5rem 0;width:100%}th,td{border:1px solid #ccd;padding:4px 8px;"
             "text-align:left;font-size:14px}th{background:#eef2f7}.banner{background:#fff4ce;border:1px solid #e0c060;"
             "padding:.6rem 1rem}.ask{font-style:italic}.ev{font-size:13px;color:#445}")
    return ("<!doctype html>\n<html lang='en'><head><meta charset='utf-8'>"
            "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'\">"
            f"<title>Trust portal: Halcyon Assist (fictional)</title><style>{style}</style></head><body>"
            "<h1>Trust portal: Halcyon Assist</h1>"
            f"<p class='banner'><strong>{_e(TEMPLATE_LABEL)}.</strong> Fictional product and companies. Generated "
            "from synthetic, offline runs of this repository. Not an audit report, certification or pen test.</p>"
            + "".join(body) + "</body></html>\n")


def main(argv: list[str]) -> int:
    errs = check_mappings()
    if errs:
        print("mapping errors:\n" + "\n".join(f"  {e}" for e in errs))
        return 1
    page = build_html()
    if "--check" in argv:
        ok = OUT.exists() and OUT.read_text() == page
        print("trust portal up to date" if ok else "docs/trust-portal/index.html is stale; run: python -m trustpack portal")
        return 0 if ok else 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page)
    fw = load_mappings()
    print(f"wrote {OUT.relative_to(ROOT)} ({len(page)} bytes): 9 questions, "
          + ", ".join(f"{k}={len(v['controls'])} controls" for k, v in fw.items()))
    return 0
