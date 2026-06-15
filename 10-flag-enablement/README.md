# 10-flag-enablement

Feature flag naming, provisioning, and enablement for the **lunch-marcoly** grid navigator.

## What this demonstrates

This example is the **only** place LaunchDarkly is used in the repository. The [00-reference](../00-reference/) app is reference-only — it has no LaunchDarkly integration and serves as the baseline behavior described in [application.md](../00-reference/application.md) (`X` only, no colors).

Here you define three boolean feature flags that extend the grid navigator. See [application.md](application.md) for the full flag specification and desired effects. Provision flags with:

- **Terraform** ([terraform/](terraform/))
- **REST API** scripts ([rest/](rest/))

Future language implementations that evaluate these flags also belong in this folder (not in `00-reference`).

## Recommended flags

Summary below. Full behavior, acceptance criteria, and combined flag effects are in [application.md](application.md).

Naming follows the **action: subject** pattern from the [flag conventions guide](https://launchdarkly.com/docs/guides/flags/flag-conventions). Keys use **kebab-case**, matching the auto-generated key style.

### 1. Selection highlight on selected cell

00-reference uses **`X` only** with no colors. This flag **enables** colored highlight when turned on (default **pink**).

| Attribute | Value |
|-----------|-------|
| **Kind** | Configure (operational) |
| **Name** | `Configure: grid selection green highlight` |
| **Key** | `configure-grid-selection-green-highlight` |
| **Interpretation** | Enable colored highlight on the selected grid cell |
| **Temporary** | No |
| **Tags** | `grid-navigator`, `configure`, `ui` |
| **Default (off)** | `false` — `X` only, no colors (matches 00-reference) |
| **When `true`** | Pink highlight by default; username colored to match |
| **When `false`** | `X` only — same as [00-reference/application.md](../00-reference/application.md) |

**Variation labels**

| Variation | Label | Description |
|-----------|-------|-------------|
| `true` | Highlight enabled | Selected cell shows `X` with colored highlight |
| `false` | X only | Selected cell shows `X` with no colors (default) |

### 2. Context-based highlight colors

When enabled together with the highlight flag, colors are derived from **words in the login name**:

| Word in name | Cohort | Color |
|--------------|--------|-------|
| `human` | human | yellow |
| `robot` | robot | red |
| `beta` | beta | blue |
| human + beta | human-beta | green |
| robot + beta | robot-beta | purple |

The header shows a cohort label in parentheses (e.g. `(human-beta-green)` or `(no-color)`) after the username. The label always includes the color name; cohort identifiers appear when the context flag is on.

| Attribute | Value |
|-----------|-------|
| **Kind** | Configure (operational) |
| **Name** | `Configure: grid selection context highlight` |
| **Key** | `configure-grid-selection-context-highlight` |
| **Default (off)** | `false` — pink highlight when highlight flag is on |
| **When `true`** | Cohort-based colors; label like `(human-yellow)` or `(human-beta-green)` |
| **When `false`** | Pink highlight; label `(pink)` |

### 3. Navigation move count in header

A temporary **show** flag that controls visibility of a running navigation counter in the grid header.

| Attribute | Value |
|-----------|-------|
| **Kind** | Show (temporary) |
| **Name** | `Show: navigation move count` |
| **Key** | `show-navigation-move-count` |
| **Default (off)** | `false` — count is hidden |
| **When `true`** | Header displays `Count: N` |
| **When `false`** | No count is visible in the header |

## Visual design

Implementations use a **dark background** (web: `#1e1e2e`; console: dark gray ANSI background) so light colors like yellow and dark colors like purple both have sufficient contrast.

## Prerequisites

- A LaunchDarkly account with a project and at least one environment
- API access token with permission to manage feature flags
- For Terraform: Terraform 1.5+ and the [LaunchDarkly provider](https://registry.terraform.io/providers/launchdarkly/launchdarkly/latest)

Set environment variables before provisioning (see [project.md](../project.md#environment-variables)):

```bash
export LD_API_HOST="https://app.launchdarkly.com"   # optional
export LD_PROJECT_KEY="default"
export LD_ENVIRONMENT_KEY="test"
export LD_API_ACCESS_TOKEN="api-..."   # rest/ examples
export LD_ACCESS_TOKEN="api-..."       # terraform/ examples
```

## Provisioning

| Approach | Directory | What it creates |
|----------|-----------|----------------|
| Terraform | [terraform/](terraform/) | All three flags; all default to **off** in the target environment |
| REST API | [rest/](rest/) | Shell scripts demonstrating create, retrieve, update, and delete |

Run provisioning **before** adding language implementations in this folder.

## Flag keys in code

When implementations evaluate these flags, use the keys exactly as shown:

```text
configure-grid-selection-green-highlight
configure-grid-selection-context-highlight
show-navigation-move-count
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

All implementations require `LD_SDK_KEY` and provisioned flags. See each language README for build and run commands.

## Further reading

- [Flag conventions](https://launchdarkly.com/docs/guides/flags/flag-conventions)
- [Using the LaunchDarkly REST API](https://launchdarkly.com/docs/guides/api/rest-api)
- [Managing flags with Terraform](https://launchdarkly.com/docs/guides/infrastructure/terraform)
- [application.md](application.md) — flag specification and desired effects
- [00-reference/application.md](../00-reference/application.md) — baseline grid navigator behavior
