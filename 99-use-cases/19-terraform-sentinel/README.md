# 19-terraform-sentinel

Sentinel policies for LaunchDarkly flags defined in Terraform. No grid app and no SDK.

Two policies, each with a pass fixture and a fail fixture. `./run.sh` prints the policy result. It does not call LaunchDarkly.

Keywords: **Terraform** · **Sentinel** · **temporary flags** · **custom properties**

Docs: [Sentinel testing](https://developer.hashicorp.com/sentinel/docs/writing/testing) ·
[tfplan/v2](https://developer.hashicorp.com/terraform/cloud-docs/policy-enforcement/sentinel/import/tfplan-v2) ·
[Flag lifecycle settings](https://launchdarkly.com/docs/home/flags/flag-lifecycle-settings) ·
[Custom properties](https://launchdarkly.com/docs/home/infrastructure/custom-properties)

## Policies

| Policy | Pass | Fail |
|--------|------|------|
| [policies/temporary.sentinel](policies/temporary.sentinel) | Boolean flag with `temporary = true` | Boolean flag with `temporary = false` |
| [policies/sunset.sentinel](policies/sunset.sentinel) | Boolean flag with custom property `sunset = ["2026-12-31"]` | Boolean flag with no `sunset` property |

String flags are ignored. `sunset` is a convention this policy enforces. LaunchDarkly stores the property and does not archive the flag on that date. A change that turns a flag off at a clock time is [17-scheduled-changes](../../10-code-control/17-scheduled-changes/).

The mocks match the **provider ~> 2.0** plan shape (`custom_properties` blocks). That is the provider pin used in the rest of this repo.

## Run

Install the [Sentinel CLI](https://developer.hashicorp.com/sentinel/install). Open-source Terraform does not evaluate these policies. Enforcement in a real pipeline is a policy set on HCP Terraform or Terraform Enterprise. These scripts run the same rules locally against a plan slice.

```bash
cd 99-use-cases/19-terraform-sentinel
./run.sh
```

```text
Four Terraform plan fixtures. Sentinel only — no LaunchDarkly API call.

temporary/pass: pass
  Policy   boolean flags must set temporary = true
  Flag     enable-sentinel-temporary
  Saw      variation_type = boolean, temporary = true
  Why      temporary is true, so this plan passes

temporary/fail: fail
  Policy   boolean flags must set temporary = true
  Flag     enable-sentinel-temporary
  Saw      variation_type = boolean, temporary = false
  Why      temporary is false. LaunchDarkly allows a permanent flag; this policy does not

sunset/pass: pass
  Policy   boolean flags must set custom property sunset to one YYYY-MM-DD value
  Flag     enable-sentinel-sunset
  Saw      sunset = 2026-12-31
  Why      the value matches YYYY-MM-DD, so this plan passes. LaunchDarkly stores the date and does not archive the flag

sunset/fail: fail
  Policy   boolean flags must set custom property sunset to one YYYY-MM-DD value
  Flag     enable-sentinel-sunset
  Saw      no sunset custom property
  Why      sunset is missing, so this plan fails
```

One fixture prints the same block for that case:

```bash
./temporary/pass/run.sh
./sunset/fail/run.sh
```

`fail` means the policy rejected the flag. The script still exits 0, because that rejection is the expected result. A missing `sentinel` binary, or a policy that accepts the fail fixture, exits non-zero.

## Do not apply the fail folders

`temporary/fail` and `sunset/fail` are valid LaunchDarkly Terraform. The provider will create those flags. The lesson stops at Sentinel.

The pass folders can be applied if you want the flags in a project. That is optional and needs `LD_ACCESS_TOKEN` and `LD_PROJECT_KEY`:

```bash
cd temporary/pass
terraform init
terraform apply \
  -var="access_token=${LD_ACCESS_TOKEN}" \
  -var="project_key=${LD_PROJECT_KEY}"
```

## Layout

| Path | Role |
|------|------|
| `policies/` | The two Sentinel rules, shared by each pair |
| `temporary/pass`, `temporary/fail` | `temporary` flag plus the plan slice `run.sh` evaluates |
| `sunset/pass`, `sunset/fail` | `sunset` custom property plus the plan slice `run.sh` evaluates |
| `run.sh` | All four results |
| [application.md](application.md) | What each rule checks |
