# 99-use-cases

LaunchDarkly **use-case examples** built as variations of the [00-reference-feature](../00-reference-feature/) grid navigator.

Each subdirectory demonstrates a specific product pattern (A/B testing, rollouts, etc.) with focused documentation, provisioning, and runnable implementations.

## Use cases

| Directory | Description |
|-----------|-------------|
| [01-abcd-test/](01-abcd-test/) | A-B-C-D test on navigation count label (`configure-navigation-count-label`) |
| [02-segments-by-name/](02-segments-by-name/) | Segment targeting from username-derived context attributes |
| [11-create-eval-flag/](11-create-eval-flag/) | Create and evaluate a single highlight color flag; toggle via UI or curl |
| [14-progressive-rollout/](14-progressive-rollout/) | Progressive rollout of green highlight over 15 minutes (10→100%) |
| [15-guarded-rollout/](15-guarded-rollout/) | Guarded rollout with latency, error rate, and movement guardrails |
| [16-adaptive-triggers/](16-adaptive-triggers/) | Adaptive trigger: custom latency metric switches highlight variation (`green` → `none`) |
| [17-migration-flags/](17-migration-flags/) | **Stub:** migration flag dual-store cutover (parked 10-series 16) |
| [18-sdk-fallbacks/](18-sdk-fallbacks/) | Init failure / stream loss → default vs last-known evaluation (Python / Node / Java / .NET web) |
| [19-terraform-sentinel/](19-terraform-sentinel/) | Sentinel policies for Terraform flags: `temporary` and a `sunset` custom property (pass and fail fixtures, no SDK) |
| [20-multi-arm-bandit/](20-multi-arm-bandit/) | **Stub:** multi-armed bandit on the grid. Traffic shifts toward the winning variation. Not the fixed split in `01`, and not `503-mobile-experiment` |
| [21-tenant-datacenters/](21-tenant-datacenters/) | Five datacenters, 52 tenants. Border palette and fill flags, plus size, datacenter, and footprint segments |
| [22-api-progressive-rollout/](22-api-progressive-rollout/) | Progressive highlight ramp started with the environment releases beta API |
| [23-api-guarded-rollout/](23-api-guarded-rollout/) | Guarded highlight rollout, 10/20/30/50, started with the same beta API. Web: Python **:8784**, Node **:8785**, Java **:8786**, .NET **:8787**. Consoles read the flag |
| [24-multitenant-datacenter/](24-multitenant-datacenter/) | Six AWS-region datacenters, shared and single-tenant replicas, S/M/L rows. Rolling deployments in the page. Python **:8788**. Flags are stubs |
| [25-prerequisite-tree/](25-prerequisite-tree/) | **Stub:** six flags. One grandparent, two parents (one child and two children). The tree in the drawer changes as flags toggle |
| [26-agent-adaptive-trigger/](26-agent-adaptive-trigger/) | **Stub:** [16-adaptive-triggers](16-adaptive-triggers/) for Agent Management. A metric switches the briefing to a safer model |
| [27-archive-flag/](27-archive-flag/) | **Stub:** selected cell blinks while a flag is on, then stops when the flag is archived. The page steps through setup, run, and archive |
| [28-big-segment/](28-big-segment/) | **Stub:** server-side big segment. Membership is in one us-east-1 DynamoDB table. Not the browser badge in `303` |

## Conventions

- Baseline behavior inherits from [00-reference-feature/application.md](../00-reference-feature/application.md)
- Each use case includes its own `application.md`. Grid use cases add provisioning (`terraform/`, `rest/`) and language folders. [19-terraform-sentinel](19-terraform-sentinel/) is policies only: no SDK and no grid app.
- Experiment utilities (where applicable) live alongside the application in each language folder

## Further reading

- [project.md](../project.md) — repository layout and LaunchDarkly conventions
- [00-reference-feature/application.md](../00-reference-feature/application.md) — baseline grid navigator
