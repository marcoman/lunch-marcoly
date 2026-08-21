# Terraform provisioning

Provisions `enable-grid-selection-highlight` as a **string** flag for the create/eval use case.

The flag is **off** in the target environment by default. Use `./rest/turn-flag-on.sh` or the LaunchDarkly UI to turn it on after apply.

## Environment variables

| Variable | Required |
|----------|----------|
| `LD_ACCESS_TOKEN` | Yes |
| `LD_PROJECT_KEY` | Yes |
| `LD_ENVIRONMENT_KEY` | Yes |

## How to run

```bash
terraform init
terraform apply \
  -var="access_token=${LD_ACCESS_TOKEN}" \
  -var="project_key=${LD_PROJECT_KEY}" \
  -var="environment_key=${LD_ENVIRONMENT_KEY}"
```
