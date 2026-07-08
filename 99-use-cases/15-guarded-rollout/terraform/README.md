# Terraform provisioning

Provisions `configure-grid-selection-green-highlight` as a **string** flag and the three guardrail metrics for the guarded rollout use case.

The flag is **off** in the target environment by default. Use `./rest/start-guarded-rollout.sh` or the LaunchDarkly UI to begin the guarded rollout after apply.

> In this example, we have a guarded rollout over **12 minutes** in **four equal stages**: **10%**, **20%**, **30%**, and **50%** of users receive the green highlight.

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
cd ../rest && ./start-guarded-rollout.sh
```

Configure guardrail metrics in the LaunchDarkly UI when enabling guarded rollout on the default rule (Terraform creates `grid-nav-latency`, `grid-highlight-error-rate`, and `grid-nav-movement`).
