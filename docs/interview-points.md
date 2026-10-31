# Interview points

- **The buyer is asking for evidence, not reassurance.** Each of the nine answers points to a file, a test and a command, and CI fails when the answer stops being true.
- **Residency comes down to deployment types.** In Microsoft Foundry, data at rest stays in the resource's geography, but the deployment type decides where inference may run. Global can run anywhere, Data zone stays within the US or EU, and Standard stays in one geography. A config that is EU-only on storage but uses `GlobalStandard` is the classic gap, and RES004 catches it.
- **One policy source, two IaC tools.** The deny list lives in JSON, and Terraform, Bicep and the Python tests all read it, so parity is tested rather than hoped for.
- **Fail closed and pseudonymise at the boundary.** The training gateway is the only path to a corpus. Unknown means deny, and opt-in data leaves only with keyed HMAC pseudonyms.
- **Proving deletion needs a control canary.** If only the subject canary is checked, a store that was never queried looks clean. The control canary proves the store was really checked. The hash chain shows the certificate was not edited.
- **Isolation tests must be able to fail.** A test that plants a bug, `LeakyCacheStore`, shows the canary suite catches it. A suite that always passes proves nothing.
- **JIT access is a product feature.** It needs customer approval, no self-approval, a 4-hour cap, scoped actions and a review log, which maps to Entra PIM and Customer Lockbox in Azure.
- **Known misses stay visible.** The guard's misses (encoded, translated and game-framed attacks, and bare names with dates) are asserted in tests, so nobody can quietly claim 100%.
- **Templates are labelled as templates.** "Template, not certified" appears on every document, because over-claiming compliance is itself a risk.
- **Trade-offs.**
  - Everything is offline and deterministic, so it is reproducible, but it is not production-scale.
  - Regex guards are explainable and fast, but they are weak against obfuscation.
