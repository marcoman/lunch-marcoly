# Terraform — segments by name

Provisions segments, string highlight flag, and segment-based targeting for [02-segments-by-name](../application.md).

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

Flag is **on** with segment targeting after apply. Default fallthrough is `none`.

## Resources

- 7 rule-based segments (`seg-by-name-*`)
- `configure-grid-selection-green-highlight` as a **string** flag (6 color variations + `none`)
