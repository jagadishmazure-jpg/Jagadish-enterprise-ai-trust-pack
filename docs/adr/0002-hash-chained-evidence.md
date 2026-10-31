# ADR 0002: Hash-chained evidence instead of a database

**Status:** accepted

**Context.** Deletion certificates, audit logs, JIT access logs and incident timelines must be
checkable by a third party without trusting our database.

**Decision.** Use one `HashChain` helper. Each entry stores the sha256 of its canonical JSON body
plus the previous hash. `verify()` reports the first broken index.

**Consequences.** Tampering is detected offline. A full rewrite of the chain is only caught if the
head is anchored elsewhere. Planned: write daily heads to immutable (WORM) storage.
