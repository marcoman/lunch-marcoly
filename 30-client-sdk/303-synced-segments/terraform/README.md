# Terraform provisioning

Creates **`marcoly-inner-circle`** and **`show-inner-circle-badge`** with a
`segmentMatch` rule. Default `unbounded_segment=true` (big/synced-style).

```bash
terraform init
terraform apply \
  -var="access_token=${LD_ACCESS_TOKEN}" \
  -var="project_key=${LD_PROJECT_KEY}" \
  -var="environment_key=${LD_ENVIRONMENT_KEY}"
```

If unbounded segments are not allowed on the plan:

```bash
terraform apply \
  -var="access_token=${LD_ACCESS_TOKEN}" \
  -var="project_key=${LD_PROJECT_KEY}" \
  -var="environment_key=${LD_ENVIRONMENT_KEY}" \
  -var="unbounded_segment=false"
```
