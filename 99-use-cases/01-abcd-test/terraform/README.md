# Terraform provisioning

Provisions `configure-navigation-count-label` for the ABCD test use case.

The flag is **off** in the target environment by default. Use the experiment utility or REST API to turn it on with percentage rollout before running trials.

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
