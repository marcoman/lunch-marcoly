# REST provisioning

Creates the Acme boolean **feature flag** and custom conversion **metric** used
by the mobile Experimentation lesson.

- [REST API overview](https://launchdarkly.com/docs/guides/api/rest-api)
- [Create a feature flag](https://launchdarkly.com/docs/api/feature-flags/post-feature-flag)
- [Create a metric](https://launchdarkly.com/docs/api/metrics/post-metric)
- [Create an experiment](https://launchdarkly.com/docs/api/experiments/create-experiment)

## Configure and provision

Credentials and destination keys come only from environment variables:

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"     # example; choose your project
export LD_ENVIRONMENT_KEY="experiment"    # prefer a dedicated environment

chmod +x ./*.sh
./create-flag.sh
./create-metric.sh
./status.sh
```

`create-flag.sh` is safe to rerun: it creates a missing flag, then sets the
selected environment to **off**, where `false` is the off/control variation.
If turned on outside an experiment, fallthrough is `true`. It does not replace
an existing project-level flag definition.

## Configure the experiment

Experiment creation is intentionally not posted automatically. The current API
requires an environment-specific allocation rule ID plus variation IDs and a
flag configuration version. Guessing the rule ID creates a broken draft; the
Terraform provider also does not manage experiments.

In the LaunchDarkly dashboard:

1. Open project `$LD_PROJECT_KEY`, environment `$LD_ENVIRONMENT_KEY`.
2. Create one experiment named **First-run helper vs grid** — not the flag
   display name **Acme: mobile onboarding helper**, and not the near duplicate
   **Acme mobile onboarding helper**.
3. Assignment method **LaunchDarkly flag or config**; flag **Acme: mobile
   onboarding helper**; targeting rule **Default rule**.
4. Randomize by `user`. Put 50% of `user` contexts in the experiment, split
   50/50 Control (`false`) / Treatment (`true`), and leave **Disable
   reshuffling** on. Do not target by platform.
5. Select primary custom metric `mobile_onboarding_completed`.
6. Add result attributes `platform` and `app-version`.
7. Review audience and allocation. Validate exposure and conversion from both
   platforms—prefer an A/A check if instrumentation is uncertain.
8. Start only after review. Nothing in this directory starts an experiment.

`./generate-experiment-payload.sh > experiment-draft.json` resolves the
variation IDs and config version and emits a current API-shaped draft. Its
`REPLACE_WITH_DASHBOARD_ALLOCATION_RULE_ID` marker is deliberate: configure the
allocation in the dashboard and use the draft for teaching/review, not blind
execution.

Synthetic simulator traffic should use a dedicated environment; concurrent
classes otherwise share targeting, allocation, and results.

Cleanup is destructive and explicit:

```bash
./delete-resources.sh --yes
```
