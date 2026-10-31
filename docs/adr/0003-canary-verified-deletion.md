# ADR 0003: Verify deletion with subject and control canaries

**Status:** accepted

**Context.** "We ran DELETE" is not proof. A store that was never queried, or one that dropped
everything, also returns zero rows.

**Decision.** Plant a subject canary and a control canary in every store before purging. Pass only
when the subject canary is gone **and** the control canary is still present. Record both facts in
the certificate.

**Consequences.** This catches skipped stores and over-deletion. It cannot see stores that do not
implement the `Store` protocol, so the store list itself must be reviewed.
