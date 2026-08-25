# Terraform provisioning

Creates the **32-client-identify** flags with **client-side SDK availability**
and **key** targeting for `alice` / `bob`.

Keywords: **Terraform** · **targeting rules** · **identify** · **using_environment_id**

- [Managing flags with Terraform](https://launchdarkly.com/docs/guides/infrastructure/terraform)
- [Target with rules](https://launchdarkly.com/docs/home/flags/target-rules)

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

| Key | Targeting (flag on) |
|-----|---------------------|
| `enable-identify-grid-highlight` | alice→green, bob→blue, else none |
| `show-identify-move-count` | alice→true, bob/else→false |
