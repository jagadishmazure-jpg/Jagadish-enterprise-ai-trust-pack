# Data Protection Impact Assessment (DPIA) for Halcyon Assist

> **Template, not certified.** A structure to fill in, not a completed assessment. Fictional product.

| Section | What to write | Repo evidence |
|---|---|---|
| 1. Processing description | Purpose, data subjects, data categories, recipients | `trustpack/subprocessors/registry.yaml` |
| 2. Necessity and proportionality | Why each data class is needed; retention per class | `trustpack/retention/schedule.yaml` |
| 3. Transfers | Regions, data zones, transfer mechanisms (SCCs) | `trustpack/residency/`, `check_boundary()` |
| 4. Risks to individuals | PII in outputs, cross-tenant leakage, injection exfiltration, wrong advice | `trustpack/incidents/runbooks.yaml` |
| 5. Measures | No-training gateway, tenant keys, JIT access, PII redaction, deletion certificates | `trustpack/data_use/`, `trustpack/isolation/`, `trustpack/retention/` |
| 6. Residual risk | Known misses kept visible (encoded injection, names without other identifiers) | `python -m trustpack security` |
| 7. Sign-off | DPO advice, controller decision, review date | `<names and dates>` |
