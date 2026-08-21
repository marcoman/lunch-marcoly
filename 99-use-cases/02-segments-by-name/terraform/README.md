# Terraform — segments by name

Provisions segments, string highlight flag, VIP boolean flag, and segment-based targeting for [02-segments-by-name](../application.md).

## Prerequisites

| Variable | Environment variable |
|----------|---------------------|
| `access_token` | `LD_ACCESS_TOKEN` |
| `project_key` | `LD_PROJECT_KEY` |
| `environment_key` | `LD_ENVIRONMENT_KEY` |

## Apply

```bash
export LD_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="default"
export LD_ENVIRONMENT_KEY="production"

terraform init
terraform apply \
  -var="access_token=${LD_ACCESS_TOKEN}" \
  -var="project_key=${LD_PROJECT_KEY}" \
  -var="environment_key=${LD_ENVIRONMENT_KEY}"
```

Highlight flag is **on** with segment targeting after apply. Default fallthrough is `none`.

VIP flag is **off** (`false`) after apply. Turn it **on** in LaunchDarkly to show `**VIP**` for usernames whose `name` contains `vip`.

## Resources

- 8 rule-based segments (`seg-by-name-*`, including `seg-by-name-vip`)
- `enable-grid-selection-highlight` as a **string** flag (6 color variations + `none`)
- `VIP` as a **boolean** flag (default `false`)