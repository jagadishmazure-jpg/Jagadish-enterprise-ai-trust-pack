# ADR 0005: Treat the Microsoft Foundry deployment type as a residency control

**Status:** accepted

**Context.** Storage-region checks alone miss the main residency gap. Global deployment types may
process prompts in any region, even when data at rest stays in the resource's geography.

**Decision.** Each deployment SKU maps to a processing scope: global, data zone or geography. The
scopes are ordered by strictness. A deployment whose scope is less strict than the tenant's boundary
is a finding, and so is any cross-region fallback without consent. A fallback outside the boundary
is a finding even with consent.

**Consequences.** The check stays small and explainable. The SKU table must follow Microsoft Learn,
and an unknown SKU is rejected rather than assumed safe.
