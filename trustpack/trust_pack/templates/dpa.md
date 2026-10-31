# Data Processing Addendum (DPA)

> **Template, not certified.** Not legal advice. Parties are fictional: *Quillstone AI Ltd*
> (processor, provider of the fictional product *Halcyon Assist*) and `<Customer>` (controller).
> Have counsel review before use.

## 1. Roles
The Customer is the controller of Customer Personal Data. Quillstone AI processes it only on the
Customer's documented instructions, to provide Halcyon Assist.

## 2. Use of Customer Data
Quillstone AI does not use prompts, outputs, files, embeddings or telemetry to train, fine-tune or
improve any model. Feedback (thumbs up or down with the rated text) is used only where the Customer
opts in in writing for that data type; the opt-in can be withdrawn at any time.
*Evidence: `trustpack/data_use/policy.yaml`, enforced by `trustpack/data_use/gateway.py`.*

## 3. Subprocessors
The current list is in Annex 2. Quillstone AI gives at least **30 days'** written notice before adding
a subprocessor or changing its purpose or region, and the Customer may object in that window.
*Evidence: `trustpack/subprocessors/registry.py` (`validate_notice`).*

## 4. Retention and deletion
Data is kept per the schedule in Annex 3. Verified deletion requests complete within **30 days** and
the Customer receives a deletion certificate. Immutable backups age out within 35 days.

## 5. Security incidents
Quillstone AI notifies the Customer of a Personal Data Breach without undue delay and within the
contract window for its severity (SEV1 24 hours, SEV2 48 hours), so the Customer can meet its own
72-hour regulator deadline. *Evidence: `trustpack/incidents/runbooks.yaml`.*

## Annex 1: Data residency
| Data class | Stored in | Processed in | Cross-region fallback |
|---|---|---|---|
| Prompts and outputs | `<region, e.g. swedencentral>` | `<Data Zone EU / region>` | Not without written consent |
| Logs and traces | `<region>` | `<region>` | Not without written consent |
| Embeddings (vector index) | `<region>` | `<region>` | Not without written consent |
| Caches | `<region>` | `<region>` | Not without written consent |
| Backups | `<region>` and replica `<paired region>` | n/a | Replica stays inside the boundary |

Model deployments use Microsoft Foundry deployment types whose processing scope is no wider than the
residency boundary (for an EU data-zone customer: Data Zone or Standard types only, never Global).
*Evidence: `python -m trustpack residency`, `infra/policies/deny-loose-ai-deployments.json`.*

## Annex 2: Subprocessors
Generated from `trustpack/subprocessors/registry.yaml`; see the trust portal page.

## Annex 3: Retention schedule
Generated from `trustpack/retention/schedule.yaml`; see the trust portal page.
