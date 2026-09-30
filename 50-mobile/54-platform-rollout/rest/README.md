# REST — 54-platform-rollout

Provision `enable-mobile-platform-rollout` and move it from Android-only to
Android and iOS.

Docs: [Target with rules](https://launchdarkly.com/docs/home/flags/target-with-rules) ·
[Patch a feature flag](https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag)

Keywords: **targeting rules** · **addRule** · **addValuesToClause** · **mobile SDK**

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
chmod +x *.sh
./create-flag.sh       # state 1: platform in [android] → true
./status.sh
./advance-rollout.sh   # state 2: add ios
./status.sh
```

`create-flag.sh` does not remove `ios` if the clause already has it.
`advance-rollout.sh` is a no-op once `ios` is present.

A later Terraform apply returns the rule to `android` only. See
[../terraform/README.md](../terraform/README.md).

`./delete-flag.sh enable-mobile-platform-rollout` removes the flag.
