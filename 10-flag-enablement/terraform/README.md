# Terraform provisioning

Provision the two grid navigator feature flags using the [LaunchDarkly Terraform provider](https://registry.terraform.io/providers/launchdarkly/launchdarkly/latest).

## Prerequisites

- Terraform 1.5+
- LaunchDarkly API access token with flag management permissions

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_ACCESS_TOKEN` | Yes | API access token for the Terraform provider |
| `LD_PROJECT_KEY` | Yes | Project that owns the flags |
| `LD_ENVIRONMENT_KEY` | Yes | Environment for default targeting (both flags default to **off**) |
| `LD_API_HOST` | No | API host (defaults to `https://app.launchdarkly.com`) |

```bash
export LD_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="default"
export LD_ENVIRONMENT_KEY="test"
# export LD_API_HOST="https://app.launchdarkly.com"  # optional
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

To pass a non-default API host:

```bash
terraform apply \
  -var="access_token=${LD_ACCESS_TOKEN}" \
  -var="project_key=${LD_PROJECT_KEY}" \
  -var="environment_key=${LD_ENVIRONMENT_KEY}" \
  -var="api_host=${LD_API_HOST}"
```

Re-running `terraform apply` is safe — it updates existing flags in place.

To remove the flags:

```bash
terraform destroy \
  -var="access_token=${LD_ACCESS_TOKEN}" \
  -var="project_key=${LD_PROJECT_KEY}" \
  -var="environment_key=${LD_ENVIRONMENT_KEY}"
```

## What to expect

Terraform creates two boolean feature flags:

| Key | Name | Default in target environment |
|-----|------|-------------------------------|
| `configure-grid-selection-green-highlight` | Configure: grid selection green highlight | Off (`false` — X only, no colors) |
| `configure-grid-selection-context-highlight` | Configure: grid selection context highlight | Off (`false` — pink when highlight on) |
| `show-navigation-move-count` | Show: navigation move count | Off (`false` — hidden) |

Verify in the LaunchDarkly UI under **Feature flags** for your project, or run:

```bash
curl -s -X GET "${LD_API_HOST:-https://app.launchdarkly.com}/api/v2/flags/${LD_PROJECT_KEY}/show-navigation-move-count" \
  -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
  -H "LD-API-Version: ${LD_API_VERSION:-20240415}" | jq '.key, .name, .tags'
```

## Further reading

- [Managing flags with Terraform](https://launchdarkly.com/docs/guides/infrastructure/terraform)
- [launchdarkly_feature_flag](https://registry.terraform.io/providers/launchdarkly/launchdarkly/latest/docs/resources/feature_flag)
- [launchdarkly_feature_flag_environment](https://registry.terraform.io/providers/launchdarkly/launchdarkly/latest/docs/resources/feature_flag_environment)
