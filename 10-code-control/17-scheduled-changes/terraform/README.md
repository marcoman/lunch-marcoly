# Terraform provisioning — 17-scheduled-changes

Provision the dedicated string flag in its initial **off** state. When on, its
fallthrough variation is `green`.

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

Terraform owns the stable flag configuration. The Python lab creates and
replaces the short-lived scheduled change through the LaunchDarkly REST API.
It needs `LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, and `LD_ENVIRONMENT_KEY` at
runtime.

Scheduled flag changes require a LaunchDarkly **Enterprise** plan.
