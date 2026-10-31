# Model card: Halcyon Assist release v1.4

> **Template, not certified.** Fictional product. Component versions come from
> `trustpack/provenance/manifest.json`; the trust portal shows the live table with sha256 pins.

| Field | Value |
|---|---|
| Intended use | Answer customer-support questions from the tenant's own documents |
| Out of scope | Legal, medical or financial advice; decisions about individuals |
| Components | base model (vendor, pinned), fine-tune ft-07 (in-house), prompt template v12, guardrails v3 |
| Data | No customer data is used for training (see DPA section 2) |
| Evaluation | Synthetic regression suites only (`python -m trustpack security`); not a quality benchmark |
| Known limitations | Encoded or translated injections and bare names are missed by the sample guard |
| Change control | Any component change needs a new manifest entry; CI fails on an unpinned change |
| Transparency | Users are told they are talking to an AI system; outputs cite retrieved sources |
