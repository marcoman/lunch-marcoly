# 99-use-cases

LaunchDarkly **use-case examples** built as variations of the [00-reference](../00-reference/) grid navigator.

Each subdirectory demonstrates a specific product pattern (A/B testing, rollouts, etc.) with focused documentation, provisioning, and runnable implementations.

## Use cases

| Directory | Description |
|-----------|-------------|
| [01-abcd-test/](01-abcd-test/) | A-B-C-D test on navigation count label (`configure-navigation-count-label`) |

## Conventions

- Baseline behavior inherits from [00-reference/application.md](../00-reference/application.md)
- Each use case includes its own `application.md`, provisioning (`terraform/`, `rest/`), and language folders
- Experiment utilities (where applicable) live alongside the application in each language folder

## Further reading

- [project.md](../project.md) — repository layout and LaunchDarkly conventions
- [00-reference/application.md](../00-reference/application.md) — baseline grid navigator
