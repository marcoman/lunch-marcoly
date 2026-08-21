# Terraform provisioning

Provision the string flag, environment defaults, and three team targeting rules with the [LaunchDarkly Terraform provider](https://registry.terraform.io/providers/launchdarkly/launchdarkly/latest/docs).

```bash
export LD_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="default"
export LD_ENVIRONMENT_KEY="test"

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

The environment is on by default. Off and fallthrough serve `plain`; rules map public `team` values `red`, `blue`, and `yellow` to their matching colored variations. When No team omits the attribute, no clause matches.

See [targeting rules](https://launchdarkly.com/docs/home/flags/target-rules) and [context attributes](https://launchdarkly.com/docs/home/flags/context-attributes).
