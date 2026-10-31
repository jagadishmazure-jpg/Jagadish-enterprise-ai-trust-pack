"""python -m trustpack <command>. Every command is offline and deterministic."""
from __future__ import annotations

import sys

from . import demos


def _residency(args):
    from .residency.check import main
    return main(args or ["fernhollow-bank-eu", "marlowe-freight-us"])


def _data_use(_):
    s = demos.data_use_summary()
    print(f"{'tenant':<16} {'data type':<17} training_corpus")
    for r in s["rows"]:
        print(f"{r['tenant']:<16} {r['data_type']:<17} {'ALLOW' if r['allowed'] else 'deny '}  {r['reason']}")
    print(f"outbound provider request after policy: {s['provider_request']}")
    print(f"audit log: {s['audit_entries']} entries, hash chain intact={s['audit_intact']}")
    return 0


def _subprocessors(_):
    from .subprocessors.registry import main
    return main()


def _provenance(args):
    from .provenance.manifest import main
    return main(args)


def _retention(_):
    s = demos.retention_summary()
    print(f"sweep deleted (past retention): {s['swept']}")
    c = s["certificate"]
    print(f"deletion certificate {c['request_id']}: {c['status']} ({c['label']})")
    for e in c["entries"]:
        b = e["body"]
        if b["step"] == "purge":
            print(f"  purge {b['store']:<12} deleted={b['deleted']} remaining={b['remaining']} "
                  f"subject_canary_gone={b['subject_canary_gone']} control_canary_present={b['control_canary_present']}")
        else:
            print(f"  {b['step']:<8} " + ", ".join(f"{k}={v}" for k, v in b.items() if k != "step"))
    print(f"  head sha256 {c['head'][:16]}..., verify errors: {s['verify_errors'] or 'none'}")
    print(f"other subject's records untouched: {s['ben_left']}")
    return 0


def _isolation(_):
    s = demos.isolation_summary()
    for t in s["layout"]:
        print(f"  {t['tenant']:<16} index={t['index']:<20} namespace={t['namespace']:<19} kid={t['key_id']}")
    print(f"cross-tenant canary probes: {s['pairs']} attacker/victim pairs x 5 paths, leaks={s['leaks']}")
    j = s["jit"]
    print(f"JIT support access: before approval={j['before_approval']}, during={j['during']}, "
          f"wrong action={j['wrong_action']}, after expiry={j['after_expiry']} (expires {j['expires_at']})")
    print(f"access log: {j['log_entries']} entries, hash chain intact={j['log_intact']}")
    return 0


def _tabletop(_):
    from .incidents.engine import tabletop
    return tabletop()


def _security(_):
    from .security_tests import format_report
    r = demos.security_summary()
    print(format_report(r))
    return 0 if r["gate_passed"] else 1


def _portal(args):
    from .trust_pack.portal import main
    return main(args)


COMMANDS = {"residency": _residency, "data-use": _data_use, "subprocessors": _subprocessors,
            "provenance": _provenance, "retention": _retention, "isolation": _isolation,
            "tabletop": _tabletop, "security": _security, "portal": _portal}


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in COMMANDS:
        print("usage: python -m trustpack {" + ",".join(COMMANDS) + "} [args]")
        return 2
    return COMMANDS[argv[0]](argv[1:])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
