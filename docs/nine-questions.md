# The nine buyer questions, answered with evidence

Each section gives the short answer, where the evidence is, the code that enforces it, and the real
output of the command (filled in by `scripts/render_docs.py`, checked in CI with `--check`).
Every name is fictional. Every document is **Template, not certified**.

## Q1. Where are our prompts, logs and embeddings stored and processed?

**Answer.** Each tenant config names a region per data class (prompts, outputs, logs, embeddings,
caches, backups) and a boundary (geography, US / EU / APAC data zone, or global). The check
rejects:
- a Microsoft Foundry deployment type whose processing scope is wider than the boundary (for example `GlobalStandard` under an EU data-zone boundary);
- a store outside the boundary;
- cross-region fallback without a recorded customer consent;
- unknown regions.

The same deny list is written once in `infra/policies/*.json` and deployed by both Terraform and Bicep
as Azure Policy, keyed on `Microsoft.CognitiveServices/accounts/deployments/sku.name`.

Microsoft Foundry deployment types (from Microsoft Learn): Global = `GlobalStandard`, `GlobalProvisionedManaged`,
`GlobalBatch`, `DeveloperTier`; Data zone = `DataZoneStandard`, `DataZoneProvisionedManaged`, `DataZoneBatch`;
Geography = `Standard`, `ProvisionedManaged`. Data at rest stays in the resource's geography for all types;
the type changes where **inference** may run.

**Evidence.**
- `trustpack/residency/regions.py`, `check.py`, `policy.py`
- `trustpack/residency/configs/*.yaml`
- `infra/policies/`, `infra/terraform/`, `infra/bicep/`
- `tests/test_residency.py`, which includes parity tests between the Python deny list, the JSON policy files, Terraform and Bicep

<!-- run: python -m trustpack residency -->
```text
tenant=fernhollow-bank boundary=data_zone:EU
  prompts    swedencentral
  outputs    swedencentral
  logs       swedencentral
  embeddings swedencentral
  caches     swedencentral
  backups    swedencentral  replica swedensouth
  model chat-main    DataZoneStandard   swedencentral  primary scope=data_zone
  model chat-spare   DataZoneStandard   swedencentral  fallback scope=data_zone
  findings: 0 (PASS)
tenant=marlowe-freight boundary=geography:United States
  prompts    eastus2
  outputs    eastus2
  logs       eastus2
  embeddings eastus2
  caches     eastus2
  backups    eastus2        replica westus3
  model chat-main    Standard           eastus2        primary scope=geography
  model chat-spare   ProvisionedManaged westus3        fallback scope=geography
  findings: 0 (PASS)
```
<!-- /run -->

<!-- run: python -m trustpack residency broken-example || true -->
```text
tenant=pellucid-insure boundary=data_zone:EU
  prompts    swedencentral
  outputs    swedencentral
  logs       eastus2
  embeddings swedencentral
  caches     -
  backups    swedencentral  replica uksouth
  model chat-main    DataZoneStandard   swedencentral  primary scope=data_zone
  model chat-spare   GlobalStandard     francecentral  fallback scope=global
  findings: 6
    RES007 pellucid-insure.allowed_regions: 'eastus2' is outside boundary data_zone=EU
    RES001 pellucid-insure.caches: no storage region declared
    RES003 pellucid-insure.logs.region: stored in 'eastus2', outside EU
    RES003 pellucid-insure.backups.replica_region: stored in 'uksouth', outside EU
    RES006 pellucid-insure.deploy.chat-spare: GlobalStandard in francecentral may process data outside data_zone=EU
    RES005 pellucid-insure.deploy.chat-spare: falls back from swedencentral to francecentral without written customer consent
```
<!-- /run -->

## Q2. Will our data be used to train your models?

**Answer.** No, by default. `trustpack/data_use/policy.yaml` marks every data type:
- `never`: prompts, outputs, files and embeddings, and telemetry;
- `opt_in`: feedback only.

`TrainingGateway.route()` is the only path to a training corpus. It fails closed on unknown types and
destinations. It also requires a live opt-in for the tenant, and it requires the pseudonym key before it
releases anything. User IDs leave only as HMAC pseudonyms. Outbound provider calls are forced to the
settings in `provider_request.required` (`store: false`). Every decision is written to a hash-chained audit log.

```python
        elif rule["training"] == "never":
            d = Decision(False, f"{dtype} is never used for training")
        elif not self._consented(tenant, dtype, at):
            d = Decision(False, f"no live opt-in from {tenant} for {dtype}")
        elif not self.key:
            d = Decision(False, f"{KEY_ENV} not set; refusing to release un-pseudonymised data")
```

<!-- run: python -m trustpack data-use -->
```text
tenant           data type         training_corpus
fernhollow-bank  prompts           deny   prompts is never used for training
fernhollow-bank  outputs           deny   outputs is never used for training
fernhollow-bank  files_embeddings  deny   files_embeddings is never used for training
fernhollow-bank  telemetry         deny   telemetry is never used for training
fernhollow-bank  feedback          ALLOW  opt-in live for fernhollow-bank/feedback
marlowe-freight  prompts           deny   prompts is never used for training
marlowe-freight  outputs           deny   outputs is never used for training
marlowe-freight  files_embeddings  deny   files_embeddings is never used for training
marlowe-freight  telemetry         deny   telemetry is never used for training
marlowe-freight  feedback          deny   no live opt-in from marlowe-freight for feedback
outbound provider request after policy: {'model': 'chat-main', 'store': False}
audit log: 10 entries, hash chain intact=True
```
<!-- /run -->

## Q3. Who else touches our data?

**Answer.** `trustpack/subprocessors/registry.yaml` lists every hop: model provider, cloud host, vector store,
observability and incident paging. Each hop has its purpose, data categories, region and transfer
mechanism. The tool validates the registry and compares it with the last published list in `history/`.
It then checks that the change notice gives at least 30 days. Any hop outside a customer's boundary
must carry a transfer mechanism and receive only redacted data.

<!-- run: python -m trustpack subprocessors -->
```text
registry 2026-11-01: 5 hops, validation errors: 0
  llm_provider      Microsoft Foundry Models  inference            swedencentral
  cloud_host        Microsoft Azure           compute and storage  swedencentral
  vector_db         Azure AI Search           retrieval            swedencentral
  observability     Tracewell Observability   traces               eastus2
  incident_tooling  Pagerlyn Alerts           on-call paging       swedencentral
changes since 2026-08-01: 4
  added    Pagerlyn Alerts: incident_tooling in swedencentral for on-call paging
  changed  Tracewell Observability: region: 'swedencentral' -> 'eastus2'
  changed  Tracewell Observability: transfer_mechanism: None -> 'SCCs'
  changed  Tracewell Observability: content_redacted: None -> True
notice 2026-10-01 -> effective 2026-11-01: OK (31 days)
EU boundary check: OK
```
<!-- /run -->

## Q4. Which model, which version, from whom?

**Answer.** `trustpack/provenance/manifest.json` pins the base model, fine-tune, prompt template and
guardrails config by sha256, with source and approval for each. `python -m trustpack provenance` fails
(and so does CI) if any artefact changes without its pin being updated. `CHANGELOG.md` is generated from
the release history, and CI fails when it is stale.

<!-- run: python -m trustpack provenance -->
```text
release v1.4: 4 pinned components
  base_model       vendor    2026-06-01   sha256:b90f55ac377f11cf
  fine_tune        in-house  ft-07        sha256:729a048ad8a44d84
  guardrails       in-house  v3           sha256:1a7cff0d7a31f4d6
  prompt_template  in-house  v12          sha256:9e18bb678914c94e
provenance check: PASS
```
<!-- /run -->

## Q5. How long do you keep our data, and can you prove it is gone?

**Answer.** `trustpack/retention/schedule.yaml` sets these retention periods:

| Data | Retention |
|---|---|
| prompts, outputs | 30 days |
| caches | 1 day |
| traces | 14 days |
| embeddings | until the source is deleted |
| backups | 35 days, immutable |
| audit logs | 365 days |

Deletion requests have a 30-day SLA.

A deletion request plants two canaries in every store (prompt log, vector index, cache, traces):
- a **subject** canary, which must be gone after the purge;
- a **control** canary, which must survive, to prove the store was really checked and not just emptied.

Each step is appended to a hash chain, and the certificate is `VERIFIED` only if every store passes.

```python
        subj_gone = not s.contains_text(canary_token(req.request_id, s.name, "subject"))
        control_ok = s.contains_text(canary_token(req.request_id, s.name, "control"))
        passed = left == 0 and subj_gone and control_ok
```

<!-- run: python -m trustpack retention -->
```text
sweep deleted (past retention): {'prompts': 2, 'outputs': 0, 'caches': 2, 'traces': 2}
deletion certificate del-0001: VERIFIED (Template, not certified)
  received request_id=del-0001, tenant=fernhollow-bank, subject_ref=2e12dc5e9253cca2, at=2026-10-28T12:00:00+00:00
  purge prompt_log   deleted=1 remaining=0 subject_canary_gone=True control_canary_present=True
  purge vector_index deleted=2 remaining=0 subject_canary_gone=True control_canary_present=True
  purge cache        deleted=1 remaining=0 subject_canary_gone=True control_canary_present=True
  purge traces       deleted=1 remaining=0 subject_canary_gone=True control_canary_present=True
  backups  note=immutable backups are not rewritten, aged_out_by=2026-12-04
  issued   status=VERIFIED, within_sla_days=30, within_sla=True, at=2026-10-30T12:00:00+00:00
  head sha256 e23bf5a49e0f4dd9..., verify errors: none
other subject's records untouched: 5
```
<!-- /run -->

## Q6. Can other customers, or your staff, see our data?

**Answer.**
- **Isolation.** Each tenant gets its own index, namespace and HMAC key. The tenant is taken from the authenticated caller, never from the request. Documents carry per-tenant integrity tags, so a misrouted document fails verification.
- **Canary probes.** The cross-tenant suite plants a canary per tenant. It then probes 5 read paths (search, get by id, list, cache, tenant filter override) for every ordered pair of tenants.
- **Staff access.** Vendor staff get access only through `SupportAccess`. A grant needs customer-admin approval, cannot be self-approved, is scoped to listed actions and lasts at most 4 hours. Each grant is written to a hash-chained review log.

<!-- run: python -m trustpack isolation -->
```text
  fernhollow-bank  index=idx-fernhollow-bank  namespace=ns-fernhollow-bank  kid=kid-624aeb820654
  marlowe-freight  index=idx-marlowe-freight  namespace=ns-marlowe-freight  kid=kid-34f86f1c91d8
  pellucid-insure  index=idx-pellucid-insure  namespace=ns-pellucid-insure  kid=kid-7d32d2a86381
cross-tenant canary probes: 6 attacker/victim pairs x 5 paths, leaks=0
JIT support access: before approval=False, during=True, wrong action=False, after expiry=False (expires 2026-10-30T14:10:00+00:00)
access log: 6 entries, hash chain intact=True
```
<!-- /run -->

## Q7. What happens when something goes wrong?

**Answer.** `trustpack/incidents/runbooks.yaml` has four AI runbooks:
- PII in model output
- harmful output
- prompt-injection data exfiltration (`injection_exfiltration`)
- model regression

Each has severity rules and timed steps. The notification windows are:

| Severity | Customer (contract) | RCA |
|---|---|---|
| SEV1 | 24h | 120h |
| SEV2 | 48h | 120h |
| SEV3 | 120h | 240h |

Personal-data breaches also start a 72-hour regulator clock (GDPR Art. 33, as controller). The
tabletop simulator replays a timeline and reports every missed window. Scenario 04 misses on purpose,
so the report shows what a failure looks like.

<!-- run: python -m trustpack tabletop -->
```text
tabletop-01 PII in a support answer (fictional tenant fernhollow-bank): pii_in_output SEV2 personal_data=True -> PASS
  contain                  due    4h  done   2.5h  ok
  notify_customer          due   48h  done    20h  ok
  rca                      due  120h  done    96h  ok
  controller_can_meet_72h  due   48h  done    20h  ok
tabletop-02 injected PDF exfiltrates via a link tool (fictional tenant marlowe-freight): injection_exfiltration SEV1 personal_data=True -> PASS
  contain                  due    1h  done  0.75h  ok
  notify_customer          due   24h  done     6h  ok
  rca                      due  120h  done   110h  ok
  controller_can_meet_72h  due   48h  done     6h  ok
tabletop-03 wrong refund advice sent to users of two tenants: harmful_output SEV2 personal_data=False -> PASS
  contain                  due    4h  done     3h  ok
  notify_customer          due   48h  done    30h  ok
  rca                      due  120h  done   110h  ok
tabletop-04 prompt v12 regression, notice sent late (kept failing on purpose): model_regression SEV3 personal_data=False -> MISS
  contain                  due   24h  done    30h  MISSED
  notify_customer          due  120h  done   140h  MISSED
  rca                      due  240h  done   200h  ok
tabletop: 3/4 scenarios met every deadline
```
<!-- /run -->

## Q8. How do you test for prompt injection, jailbreaks and data leakage?

**Answer.** Three suites (injection, jailbreak, PII) are registered through hooks and run against a
sample guard. The report keeps misses and false positives visible rather than hiding them. External
tools plug in through `ingest_external()`. `pentest_template.md` is a template and says so; no pen test
has been run.

<!-- run: python -m trustpack security -->
```text
security report (Synthetic regression checks, not a pen test)
suite      cases attacks blocked benign false+  known misses
injection     18      13      11      5      0  inj-12, inj-13
jailbreak     13       9       8      4      0  jb-09
pii           14       9       8      5      0  pii-09
total blocked 27/31; gate (no unexpected results): PASS
```
<!-- /run -->

## Q9. Can you send us your security documentation?

**Answer.** `trustpack/trust_pack/mappings.yaml` maps SOC 2 Trust Services Criteria, ISO/IEC 27001:2022
Annex A and ISO/IEC 42001 controls to evidence paths in this repo. A test checks that every path exists.
`templates/` holds a DPA with a residency annex, a DPIA, a model card and a pen-test letter, all marked
**Template, not certified**. `python -m trustpack portal` renders a static, escaped, CSP-locked trust
portal into `docs/trust-portal/index.html`.

<!-- run: python -m trustpack portal --check -->
```text
trust portal up to date
```
<!-- /run -->
