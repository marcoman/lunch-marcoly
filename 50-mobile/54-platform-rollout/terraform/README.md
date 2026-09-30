# Terraform — 54-platform-rollout

Creates `enable-mobile-platform-rollout` in **state 1**: the flag is on,
fallthrough is `false`, and `platform in [android]` serves `true`.

Docs: [Terraform](https://launchdarkly.com/docs/guides/infrastructure/terraform) ·
[Target with rules](https://launchdarkly.com/docs/home/flags/target-with-rules)

Keywords: **targeting rules** · **platform** · **using_mobile_key**

```bash
export TF_VAR_access_token="$LD_ACCESS_TOKEN"
export TF_VAR_project_key="$LD_PROJECT_KEY"
export TF_VAR_environment_key="$LD_ENVIRONMENT_KEY"
terraform init
terraform apply
```

`rest/advance-rollout.sh` adds `ios` after that. **Another `terraform apply`
writes the rule back to `android` only.** Use REST for the classroom advance,
or stop applying Terraform once you want state 2 to stick.
