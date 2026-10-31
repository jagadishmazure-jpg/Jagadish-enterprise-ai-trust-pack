# How to run

## Offline (default, no accounts needed)

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
ruff check .
python scripts/count_tests.py
python scripts/check_brands.py
python scripts/render_docs.py --check
```

The module commands:

| Command | Question |
|---|---|
| `python -m trustpack residency [config ...]` | Q1 (defaults to the two passing configs; try `broken-example`) |
| `python -m trustpack data-use` | Q2 |
| `python -m trustpack subprocessors` | Q3 |
| `python -m trustpack provenance [--changelog [--check]]` | Q4 |
| `python -m trustpack retention` | Q5 |
| `python -m trustpack isolation` | Q6 |
| `python -m trustpack tabletop` | Q7 (exits 0; scenario 04 misses on purpose) |
| `python -m trustpack security` | Q8 |
| `python -m trustpack portal [--check]` | Q9 |

The demos print fixed timestamps (as-of 2026-10-30 12:00 UTC) and use a fixed demo HMAC key, so the
output is identical on every run. Real use reads the key from `TRUSTPACK_PSEUDONYM_KEY`.

## Infrastructure checks (offline)

```bash
terraform -chdir=infra/terraform init -backend=false
terraform -chdir=infra/terraform fmt -check -recursive
terraform -chdir=infra/terraform validate
terraform -chdir=infra/terraform test        # mocked azurerm provider, no credentials
tflint --chdir=infra/terraform
checkov -d infra/terraform --framework terraform
bicep build infra/bicep/main.bicep            # or: az bicep build --file ...
```

## Optional: apply the policies to your own subscription

This step creates two policy definitions and two assignments, which have no Azure charge. It needs
`Resource Policy Contributor` on the subscription. Review the plan first:

```bash
az login
terraform -chdir=infra/terraform plan -var subscription_id=/subscriptions/<guid>   # defaults: EU locations, EU data-zone deny list, effect Deny
```

Or with Bicep: `az deployment sub create -l swedencentral -f infra/bicep/main.bicep`.
To remove them afterwards, run `terraform destroy` or delete the assignments and definitions.
There is no deploy workflow in CI.
