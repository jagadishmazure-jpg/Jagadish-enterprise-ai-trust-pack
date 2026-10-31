# ADR 0001: One JSON policy source for Terraform, Bicep and Python

**Status:** accepted

**Context.** Residency rules have to be identical in the Python check, Terraform and Bicep.
Hand-copied lists drift.

**Decision.** The Azure Policy rules live in `infra/policies/*.json`:
- Terraform reads them with `file()`/`jsondecode`;
- Bicep reads them with `loadJsonContent`;
- pytest compares them with `residency.policy.denied_skus()`.

**Consequences.** Any change touches one file and the tests show the impact. The trade-off is that
policy parameters must be expressible in plain JSON.
