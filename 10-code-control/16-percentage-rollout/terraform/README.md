# Terraform provisioning — 16-percentage-rollout

Provision the dedicated string flag and a static percentage rollout on its
default rule.

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) **1.5+**
- LaunchDarkly API access token

## Run

```bash
export LD_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"

terraform init
terraform apply \
  -var="access_token=${LD_ACCESS_TOKEN}" \
  -var="project_key=${LD_PROJECT_KEY}" \
  -var="environment_key=${LD_ENVIRONMENT_KEY}"
```

The default is **30% green / 70% none**. Override it:

```bash
terraform apply \
  -var="access_token=${LD_ACCESS_TOKEN}" \
  -var="project_key=${LD_PROJECT_KEY}" \
  -var="environment_key=${LD_ENVIRONMENT_KEY}" \
  -var="green_percent=50"
```

The weights are static. Terraform does not create a progressive schedule.

Cleanup:

```bash
terraform destroy \
  -var="access_token=${LD_ACCESS_TOKEN}" \
  -var="project_key=${LD_PROJECT_KEY}" \
  -var="environment_key=${LD_ENVIRONMENT_KEY}"
```
