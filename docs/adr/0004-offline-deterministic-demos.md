# ADR 0004: Offline, deterministic demos and docs generated from real runs

**Status:** accepted

**Context.** Trust evidence that cannot be reproduced is not evidence. Cloud calls, wall-clock
time and random keys make outputs drift.

**Decision.** Demos use a fixed as-of time (2026-10-30 12:00 UTC) and a fixed demo key. Every output
block in the docs comes from `scripts/render_docs.py`, and CI runs it with `--check`.

**Consequences.** The docs never show numbers the code does not produce. Real deployments must
replace the demo key and clock, and the code reads the key from `TRUSTPACK_PSEUDONYM_KEY` when it is set.
