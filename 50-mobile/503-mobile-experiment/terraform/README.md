# Terraform provisioning

Creates the mobile-available boolean flag, its selected **environment
configuration**, and the custom conversion **metric**.

- [Manage LaunchDarkly with Terraform](https://launchdarkly.com/docs/guides/infrastructure/terraform)
- [`launchdarkly_feature_flag`](https://registry.terraform.io/providers/launchdarkly/launchdarkly/2.29.0/docs/resources/feature_flag)
- [`launchdarkly_metric`](https://registry.terraform.io/providers/launchdarkly/launchdarkly/2.29.0/docs/resources/metric)

All destinations and credentials are variables:

```bash
export LD_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"     # example; choose your project
export LD_ENVIRONMENT_KEY="experiment"    # prefer a dedicated environment

terraform init
terraform apply \
  -var="access_token=${LD_ACCESS_TOKEN}" \
  -var="project_key=${LD_PROJECT_KEY}" \
  -var="environment_key=${LD_ENVIRONMENT_KEY}"
```

Provider v2.29 reliably supports this non-numeric custom metric. It does not
provide an experiment resource. After apply, follow the dashboard runbook in
[`../rest/README.md`](../rest/README.md) to configure and explicitly start the
experiment. Terraform leaves the flag off and never starts an experiment.

Use a dedicated environment for synthetic traffic. Shared environments also
share experiment allocation and results.
