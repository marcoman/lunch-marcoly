# Terraform — flag only

Creates `api-progressive-grid-highlight` and leaves it **off**. The default rule variation is `none`.

This provider call does not start an environment release. After apply:

```bash
cd ../rest && ./start-progressive-release.sh
```

```bash
terraform init
terraform apply \
  -var="access_token=${LD_ACCESS_TOKEN}" \
  -var="project_key=${LD_PROJECT_KEY}" \
  -var="environment_key=${LD_ENVIRONMENT_KEY}"
```

[Environment releases (beta)](https://launchdarkly.com/docs/api/environment-releases)
