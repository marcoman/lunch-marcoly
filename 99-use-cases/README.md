# 99-use-cases

LaunchDarkly **use-case examples** built as variations of the [00-reference-code](../00-reference-code/) grid navigator.

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
| [18-sdk-fallbacks/](18-sdk-fallbacks/) | **Stub:** init failure / stream loss → default vs last-known evaluation |

## Conventions

- Baseline behavior inherits from [00-reference-code/application.md](../00-reference-code/application.md)
- Each use case includes its own `application.md`, provisioning (`terraform/`, `rest/`), and language folders
- Experiment utilities (where applicable) live alongside the application in each language folder

## Further reading

- [project.md](../project.md) — repository layout and LaunchDarkly conventions
- [00-reference-code/application.md](../00-reference-code/application.md) — baseline grid navigator
