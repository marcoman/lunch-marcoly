# Terraform provisioning

Provision the four grid navigator feature flags (boolean, string, number, JSON) using the [LaunchDarkly Terraform provider](https://registry.terraform.io/providers/launchdarkly/launchdarkly/latest).

## Prerequisites

- Terraform 1.5+
- LaunchDarkly API access token with flag management permissions

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_ACCESS_TOKEN` | Yes | API access token for the Terraform provider |
| `LD_PROJECT_KEY` | Yes | Project that owns the flags |
| `LD_ENVIRONMENT_KEY` | Yes | Environment for default targeting |
| `LD_API_HOST` | No | API host (defaults to `https://app.launchdarkly.com`) |

```bash
export LD_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="default"
export LD_ENVIRONMENT_KEY="test"
```

## How to run

From this directory:

```bash
terraform init
terraform plan \
  -var="access_token=${LD_ACCESS_TOKEN}" \
  -var="project_key=${LD_PROJECT_KEY}" \
  -var="environment_key=${LD_ENVIRONMENT_KEY}"
terraform apply \
  -var="access_token=${LD_ACCESS_TOKEN}" \
  -var="project_key=${LD_PROJECT_KEY}" \
  -var="environment_key=${LD_ENVIRONMENT_KEY}"
```

Re-running `terraform apply` is safe — it updates existing flags in place.

## What to expect

| Key | Type | Default in target environment |
|-----|------|-------------------------------|
| `show-anonymous-host-os-emoji` | Boolean | Off — no emoji |
| `configure-navigation-count-label` | String | On — `"Count"` |
| `configure-lucky-number` | Number | On — `0` |
| `configure-max-navigation-moves` | JSON | On — `{"maxMoves": 100}` |

## Further reading

- [Managing flags with Terraform](https://launchdarkly.com/docs/guides/infrastructure/terraform)
- [launchdarkly_feature_flag](https://registry.terraform.io/providers/launchdarkly/launchdarkly/latest/docs/resources/feature_flag)
