# Limitations and known failures

## Scope
- **Synthetic, in-memory stores.** `PromptLog`, `VectorIndex`, `Cache` and `TraceStore` stand in for real services. A real purge must also cover replicas, search index segments, CDN and edge caches, analytics exports and the vendor's own logs.
- **Backups are not rewritten.** The certificate records when immutable backups age out (35 days) and does not claim they were purged.
- **Templates, not certifications.** The mappings point a control to relevant evidence. They do not say the control is designed or operating effectively. Only an independent auditor can do that.
- **Region table.** `residency/regions.py` is a hand-written subset of Azure regions and data zones. Microsoft changes regions and deployment types, so check Microsoft Learn before relying on it.
- **Integrity tags are not encryption.** Per-tenant HMAC keys detect a misrouted document but do not encrypt it. Production needs per-tenant customer-managed keys.
- **The incident windows are examples.** 24/48/120 hours are sample contract terms. The 72-hour clock is GDPR Art. 33 for a controller; a processor's duty is "without undue delay", so contracts must set the real number.

## Known misses, kept visible as test cases
The sample guard in `security_tests/guard.py` uses regexes and validators. It does not use a model.
It misses these cases, and the tests assert that they are still missed. If the guard improves, the
tests must be updated on purpose.

| Case | Why it is missed |
|---|---|
| `inj-12` | base64-encoded instruction |
| `inj-13` | instruction in another language |
| `jb-09` | jailbreak framed as a game |
| `pii-09` | a bare name with a birth date (no checksum, no keyword) |

Tabletop scenario 04 misses its containment and customer-notice windows on purpose, so the report shows a failure.

## What is not here
- No real pen test or red-team engagement.
- No real DPA or legal review.
- No hosted portal.
- No real tenant data.
- Nothing has been applied to an Azure subscription.
