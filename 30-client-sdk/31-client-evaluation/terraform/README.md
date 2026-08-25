# Terraform provisioning

Creates the two **31-client-evaluation** flags with **client-side SDK availability**.

Keywords: **Terraform** · **client_side_availability** · **using_environment_id**

- [Managing flags with Terraform](https://launchdarkly.com/docs/guides/infrastructure/terraform)
- [`launchdarkly_feature_flag`](https://registry.terraform.io/providers/launchdarkly/launchdarkly/latest/docs/resources/feature_flag)

## Environment variables

| Variable | Required |
|----------|----------|
| `LD_ACCESS_TOKEN` | Yes |
| `LD_PROJECT_KEY` | Yes |
| `LD_ENVIRONMENT_KEY` | Yes |
| `LD_API_HOST` | No |

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

| Key | Default in target environment |
|-----|-------------------------------|
| `enable-client-grid-highlight` | Off (`none`) |
| `show-client-move-count` | Off (`false`) |
