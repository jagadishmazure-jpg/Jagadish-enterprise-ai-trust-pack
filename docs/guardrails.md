# Guardrails and security controls

| Control | Where | Test that proves it |
|---|---|---|
| Fail-closed training gateway (unknown type or destination is denied) | `data_use/gateway.py` | `tests/test_data_use.py` |
| HMAC-SHA256 pseudonyms, key from `TRUSTPACK_PSEUDONYM_KEY`, refuses to release data without a key | `data_use/gateway.py` | `tests/test_data_use.py` |
| Provider calls forced to `store=false` | `data_use/policy.yaml` | `tests/test_data_use.py` |
| Deployment-type and region boundary, no silent cross-region fallback | `residency/check.py`, `infra/` | `tests/test_residency.py`, `infra/terraform/tests/` |
| Tenant from the authenticated caller, never the request; filter override rejected | `isolation/tenancy.py` | `tests/test_isolation.py` |
| Per-tenant integrity tags (a misrouted document fails verification) | `isolation/tenancy.py` | `tests/test_isolation.py` |
| JIT support access: ticket, customer-admin approval, no self-approval, at most 4h, scoped actions, revocable | `isolation/jit.py` | `tests/test_isolation.py` |
| Hash-chained audit, access, deletion and incident logs; tamper detection | `common.HashChain` | `tests/test_common.py`, `tests/test_retention.py` |
| Canary-verified deletion with a control canary | `retention/engine.py` | `tests/test_retention.py` |
| sha256 pins for model, fine-tune, prompt, guardrails | `provenance/manifest.py` | `tests/test_provenance.py` |
| Injection, jailbreak and PII checks with Luhn and IBAN mod-97 validators | `security_tests/guard.py` | `tests/test_security_tests.py` |
| Portal output HTML-escaped, strict Content-Security-Policy, no scripts | `trust_pack/portal.py` | `tests/test_trust_pack.py` |
| "Template, not certified" on every template, policy and the portal | everywhere | `tests/test_trust_pack.py` |
| Supply chain: actions pinned to full SHAs, pinned tool versions, Dependabot, CodeQL, gitleaks over full history | `.github/` | CI |
| No real brand names, using a blocklist stored only as sha256 hashes | `scripts/check_brands.py` | CI |

## Key rotation (pseudonyms)
Pseudonyms are keyed, so rotating `TRUSTPACK_PSEUDONYM_KEY` breaks links to old pseudonyms on purpose.
1. Write the new key to Key Vault with a version.
2. Record the key version next to each released batch.
3. Re-pseudonymise any retained opt-in corpus under the new key.
4. Destroy the old key after the corpus retention ends.
