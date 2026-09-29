# Terraform Sentinel flag policy

This document defines **19-terraform-sentinel** under [99-use-cases](../README.md).

## Goal

Show two Sentinel rules that read a Terraform plan for `launchdarkly_feature_flag` resources. Each rule has a fixture that passes and a fixture that fails. The script output is the policy result.

There is no grid navigator and no SDK evaluation.

Keywords: **Terraform** · **Sentinel** · **tfplan/v2** · **temporary flags** · **custom properties**

Docs: [Sentinel testing](https://developer.hashicorp.com/sentinel/docs/writing/testing) ·
[tfplan/v2 import](https://developer.hashicorp.com/terraform/cloud-docs/policy-enforcement/sentinel/import/tfplan-v2) ·
[Flag lifecycle settings](https://launchdarkly.com/docs/home/flags/flag-lifecycle-settings) ·
[Custom properties](https://launchdarkly.com/docs/home/infrastructure/custom-properties) ·
[`launchdarkly_feature_flag`](https://registry.terraform.io/providers/launchdarkly/launchdarkly/latest/docs/resources/feature_flag)

## Rules

Both rules consider boolean `launchdarkly_feature_flag` creates and updates in the plan. A plan with no boolean flags passes. String, number, and JSON flags are out of scope.

| Rule | Requirement | Pass fixture | Fail fixture |
|------|-------------|--------------|--------------|
| `temporary` | `temporary` is `true` | `temporary/pass` | `temporary/fail` (`temporary = false`) |
| `sunset` | Custom property `sunset` has one value matching `YYYY-MM-DD` | `sunset/pass` (`2026-12-31`) | `sunset/fail` (property omitted) |

`sunset` is local policy recorded on the flag. LaunchDarkly does not expire the flag on that date. Expiring individual targets are a different REST feature and are not in the Terraform `launchdarkly_feature_flag_environment` schema, so this example does not policy them.

## How a case runs

`run.sh` builds a temporary Sentinel test around `policies/<name>.sentinel` and that folder's `mock-tfplan-v2.sentinel`. The mock is the `resource_changes` slice the rule reads, kept in step with `main.tf`.

| Case | Asserted `main` | Script prints | Script exit |
|------|-----------------|---------------|-------------|
| pass | `true` | `pass` | 0 |
| fail | `false` | `fail` | 0 |
| unexpected result, or no `sentinel` binary | — | error on stderr | non-zero |

## Acceptance

From `99-use-cases/19-terraform-sentinel`:

Each case prints `<policy>/<result>: <result>`, then `Policy`, `Flag`, `Saw`, and `Why`. The four result lines are:

```text
temporary/pass: pass
temporary/fail: fail
sunset/pass: pass
sunset/fail: fail
```

Fail Terraform is not applied.
