# 11-flag-variations

LaunchDarkly **flag variation types** for the **lunch-marcoly** grid navigator.

## What this demonstrates

This example extends the [00-reference](../00-reference/) grid navigator with four flags — one per multivariate type (plus anonymous context for the boolean flag):

| Flag | Type | Effect |
|------|------|--------|
| `show-anonymous-host-os-emoji` | Boolean (anonymous context) | OS emoji before username via anonymous + private `hostOs` |
| `configure-navigation-count-label` | String | Label for move counter (`Count`, `Moves`, …) |
| `configure-lucky-number` | Number | Header line `Lucky Number is: N` (0–5) |
| `configure-max-navigation-moves` | JSON | Session move limit (`maxMoves`, default 100) |

Unlike [10-flag-enablement](../10-flag-enablement/), this example does **not** include highlight or cohort flags — it focuses on variation types and their runtime effects.

See [application.md](application.md) for the full specification and acceptance criteria.

## Prerequisites

- A LaunchDarkly account with a project and environment
- API access token for provisioning
- `LD_SDK_KEY` for language implementations

```bash
export LD_PROJECT_KEY="default"
export LD_ENVIRONMENT_KEY="test"
export LD_SDK_KEY="sdk-..."
export LD_API_ACCESS_TOKEN="api-..."   # rest/
export LD_ACCESS_TOKEN="api-..."       # terraform/
```

## Provisioning

| Approach | Directory |
|----------|-----------|
| Terraform | [terraform/](terraform/) |
| REST API | [rest/](rest/) |

Run provisioning before starting language implementations.

## Flag keys in code

```text
show-anonymous-host-os-emoji
configure-navigation-count-label
configure-lucky-number
configure-max-navigation-moves
```

## Language implementations

| Language | Directory | Application type | Status |
|----------|-----------|------------------|--------|
| Python | [python/](python/) | Web application | Done |
| Python | [python-console/](python-console/) | Console application | Done |
| Node.js | [node/](node/) | Web application | Done |
| Node.js | [node-console/](node-console/) | Console application | Done |
| Java | [java/](java/) | Web application | Done |
| Java | [java-console/](java-console/) | Console application | Done |
| C++ | [cpp/](cpp/) | Console application | Done |
| Go | [go/](go/) | Console application | Done |
| Rust | [rust/](rust/) | Console application | Done |

## Further reading

- [application.md](application.md) — flag specification and acceptance criteria
- [00-reference/application.md](../00-reference/application.md) — baseline grid navigator
- [10-flag-enablement/application.md](../10-flag-enablement/application.md) — boolean flags and host OS reference
- [Multivariate flags](https://launchdarkly.com/docs/sdk/features/flag-types)
