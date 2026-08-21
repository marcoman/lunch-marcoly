# Terraform provisioning

Provisions `enable-grid-selection-highlight` as a **string** flag for the progressive rollout use case.

The flag is **off** in the target environment by default. Use `./rest/start-progressive-rollout.sh` or the LaunchDarkly UI to begin the rollout after apply.

> In this example, we have a progressive rollout over **15 minutes** in **five equal stages**: **10%**, **20%**, **40%**, **60%**, and **100%** of users receive the green highlight.

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

Then start the rollout:

```bash
cd ../rest && ./start-progressive-rollout.sh
```
