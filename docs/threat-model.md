# Threat model

Scope: a multi-tenant AI assistant ("Halcyon Assist", fictional) and the trust pack that describes
it. The assets are customer prompts, outputs, files and embeddings, the tenant keys, the pseudonym
key, the audit chains and the evidence shown to buyers.

## STRIDE

| Threat | Example | Mitigation here | Residual risk |
|---|---|---|---|
| **S**poofing | A request claims `tenant=victim` | Tenant comes from the authenticated caller; filter override raises `CrossTenantError` | Real authentication is out of scope |
| **S**poofing | A vendor engineer approves their own access | `SupportAccess.approve` requires a customer admin and rejects self-approval | Compromised customer-admin account |
| **T**ampering | Editing a deletion certificate or audit log | `HashChain` with prev-hash; `verify_certificate()` | Whole-chain rewrite unless the head is anchored externally (planned: WORM) |
| **T**ampering | Swapping the prompt template or guardrails | sha256 pins; CI fails on an unpinned change | A malicious change that updates the pin too, which code review must catch |
| **R**epudiation | "No one accessed our data" | JIT log records every request, approval, rejected approval, access attempt (allowed or denied) and revoke | Log only covers the paths that call `SupportAccess` |
| **I**nformation disclosure | Cross-tenant retrieval or cache bleed | Per-tenant index and namespace, HMAC tags, canary suite over 5 paths | Side channels such as timing and shared model caches are not tested |
| **I**nformation disclosure | Prompts used for training | Fail-closed gateway, `never` types, `store=false` | Provider behaviour must be checked contractually |
| **I**nformation disclosure | Inference in another region | RES004/RES006, Azure Policy deny on Global SKUs | Regions or SKUs added after the table was written |
| **D**enial of service | Purge request that never completes | 30-day SLA checked in the certificate | No queueing or retry logic modelled |
| **E**levation of privilege | Grant outlives its purpose | 4-hour cap, expiry checked on every use, revoke | Clock skew across systems |

## OWASP Top 10 for LLM Applications (2025)

| Risk | Relevance | Where handled |
|---|---|---|
| LLM01 Prompt injection | Indirect injection exfiltrating tenant data | `security_tests/cases/injection.yaml`, runbook `injection_exfiltration` |
| LLM02 Sensitive information disclosure | PII in outputs, cross-tenant leakage | PII suite (Luhn, IBAN), isolation canaries, runbook `pii_in_output` |
| LLM03 Supply chain | Unpinned model, prompt or guardrails | `provenance/`, SHA-pinned actions, Dependabot |
| LLM04 Data and model poisoning | Unconsented data reaching a training corpus | `data_use/gateway.py` |
| LLM05 Improper output handling | Model output rendered into the portal | Portal escapes all text and sets a strict CSP |
| LLM06 Excessive agency | Support tooling with broad access | JIT scoped actions |
| LLM07 System prompt leakage | "Reveal your instructions" | Injection suite reveal patterns |
| LLM08 Vector and embedding weaknesses | Shared index across tenants | Per-tenant index, namespace and tags |
| LLM09 Misinformation | Model regression after an update | Runbook `model_regression`, provenance change log |
| LLM10 Unbounded consumption | Not covered | Out of scope here |
