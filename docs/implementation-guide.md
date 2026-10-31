# Implementation guide for adopters

> Status: every module runs offline against synthetic data. The Azure mapping below is a
> **plan**. Only the Azure Policy definitions exist as IaC, and they have never been applied.

## 1. Order of adoption
1. **Q9 first, as the index.** Copy `trust_pack/questions.yaml` and `mappings.yaml`. For each question, write the answer you give buyers today and point it at real evidence. Any empty evidence path is your backlog.
2. **Q1 residency.** Write one config per customer boundary. Run `python -m trustpack residency` in CI against your real deployment inventory. Then assign the Azure Policy in **Audit** (`effect = "Audit"`) for two weeks, review the non-compliant list and switch to **Deny**.
3. **Q4 provenance.** Pin every model, fine-tune, prompt and guardrail file by sha256. Make the CI check required on `main`.
4. **Q2 data use.** Route every write to a training or eval corpus through the gateway. There must be no other code path; enforce that with a storage-account network rule or RBAC role that only the gateway identity holds.
5. **Q5 retention and Q6 isolation.** Implement the `Store` protocol (`put`, `purge_subject`, `count_subject`, `contains_text`) for each real store. Then run the canary suites nightly in a staging tenant.
6. **Q3, Q7, Q8.** Keep the registry and runbooks in the same repo as the code. Run a tabletop each quarter and record the result.

## 2. Azure service mapping (planned)

| Component here | Azure service | Notes |
|---|---|---|
| Model deployments | Microsoft Foundry, `DataZoneStandard` (EU/US) or `Standard` (single geography) | Choose the deployment type from the customer's boundary; Global types process anywhere |
| Residency enforcement | Azure Policy (this repo's `infra/`) | Assign at the management group for customer-dedicated subscriptions |
| `PromptLog`, outputs | Azure Cosmos DB with TTL per container | TTL from `retention/schedule.yaml` |
| `VectorIndex` | Azure AI Search, one index per tenant | Index name from the tenant record, never from the request |
| `Cache` | Azure Cache for Redis, key prefix per tenant and a TTL | Purge by tenant prefix and subject |
| `TraceStore` | Application Insights / Log Analytics with PII masking | Purge API for subject requests |
| Tenant keys, pseudonym key | Azure Key Vault (customer-managed keys where offered) | Rotation per `docs/guardrails.md` |
| `SupportAccess` | Microsoft Entra PIM (just-in-time roles) + Customer Lockbox where supported | Keep the hash-chained log or export PIM audit |
| Hash-chained logs | Immutable Blob storage (WORM) | Anchor the chain head daily |
| Trust portal | Static Web Apps or a GitHub Pages site | Publish only reviewed templates |

## 3. Things that must change for production
- Replace the regex guard with a maintained classifier and keep these cases as a regression set.
- Replace the demo key with Key Vault. Never use `DEMO_KEY` outside tests.
- Get legal review of every template and an independent audit before calling anything certified.
- Add your real regions and verify deployment-type availability per region on Microsoft Learn.

## 4. What to measure
- Residency findings per release (target 0 in Deny mode).
- Deletion requests closed within the SLA, and certificates that verify.
- Cross-tenant canary leaks (must be 0) and JIT grants without a ticket (must be 0).
- Tabletop windows met per quarter.
- Security-suite block rate and false-positive rate over time.
