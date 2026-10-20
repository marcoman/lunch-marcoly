# 11-flag-enablement

Feature flag naming, provisioning, and enablement for the **lunch-marcoly** grid navigator.

## What this demonstrates

This example teaches LaunchDarkly **feature flags** on the grid navigator. The [00-reference-code](../../00-reference-code/) app is reference-only — it has no LaunchDarkly integration and serves as the baseline behavior described in [application.md](../../00-reference-code/application.md) (`X` only, no colors). For other variation types (number / JSON), see sibling [12-flag-variations](../12-flag-variations/).

Here you define flags that extend the grid navigator — including a **string** highlight color flag and **boolean** enable/show flags. See [application.md](application.md) for the full flag specification and desired effects. Provision flags with:

- **Terraform** ([terraform/](terraform/))
- **REST API** scripts ([rest/](rest/))

Future language implementations that evaluate these flags also belong in this folder (not in `00-reference-code`).

## Recommended flags

Summary below. Full behavior, acceptance criteria, and combined flag effects are in [application.md](application.md).

Naming follows the **action: subject** pattern from the [flag conventions guide](https://launchdarkly.com/docs/guides/flags/flag-conventions). Keys use **kebab-case**, matching the auto-generated key style.

### 1. Enable grid selection highlight

00-reference-code uses **`X` only** with no colors. This **string** flag enables colored highlight when on (fallthrough color) and serves `none` when off.

| Attribute | Value |
|-----------|-------|
| **Kind** | Enable (operational) |
| **Name** | `Enable: grid selection highlight` |
| **Key** | `enable-grid-selection-highlight` |
| **Variation type** | string |
| **Interpretation** | Enable colored highlight on the selected grid cell |
| **Temporary** | No |
| **Tags** | `grid-navigator`, `enable`, `ui`, `string` |
| **Default (off)** | `none` — `X` only, no colors (matches 00-reference-code) |
| **When on** | Fallthrough color (default green); username colored to match |
| **When off** | `none` — `X` only — same as [00-reference-code/application.md](../../00-reference-code/application.md) |

**Variation labels**

| Variation | Label | Description |
|-----------|-------|-------------|
| `none` | No highlight | Selected cell shows `X` with no colors |
| `green` / `yellow` / `red` / `blue` / `purple` | Color name | Selected cell shows `X` with that highlight |

### 2. Enable grid highlight color override

When enabled together with a non-`none` highlight, colors are derived from **words in the login name**:

| Word in name | Cohort | Color |
|--------------|--------|-------|
| `human` | human | yellow |
| `robot` | robot | red |
| `beta` | beta | blue |
| human + beta | human-beta | green |
| robot + beta | robot-beta | purple |

The header shows a cohort label in parentheses (e.g. `(human-beta-green)` or `(no-color)`) after the username. The label always includes the color name; cohort identifiers appear when the override flag is on.

| Attribute | Value |
|-----------|-------|
| **Kind** | Enable (operational) |
| **Name** | `Enable: grid highlight color override` |
| **Key** | `enable-grid-highlight-color-override` |
| **Variation type** | boolean |
| **Default (off)** | `false` — use base fallthrough color from the highlight flag |
| **When `true`** | Cohort-based colors; label like `(human-yellow)` or `(human-beta-green)` |
| **When `false`** | Base fallthrough color; label like `(green)` |

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

### 4. Host OS emoji (private attribute)

Shows an OS emoji before the username. The host OS is sent as private context attribute `hostOs` for LaunchDarkly targeting.

| Attribute | Value |
|-----------|-------|
| **Key** | `show-host-os-emoji` |
| **Default (off)** | `false` — no emoji |
| **When `true`** | 🐧 linux, 🍎 macOS, 🪟 Windows, 😊 other — displayed as `emoji username` |

## Visual design

Implementations use a **dark background** (web: `#1e1e2e`; console: dark gray ANSI background) so light colors like yellow and dark colors like purple both have sufficient contrast.

## Prerequisites

- A LaunchDarkly account with a project and at least one environment
- API access token with permission to manage feature flags
- For Terraform: Terraform 1.5+ and the [LaunchDarkly provider](https://registry.terraform.io/providers/launchdarkly/launchdarkly/latest)

Set environment variables before provisioning (see [project.md](../../project.md#environment-variables)):

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
| Terraform | [terraform/](terraform/) | All four flags; all default to **off** in the target environment |
| REST API | [rest/](rest/) | Shell scripts demonstrating create, retrieve, update, and delete |

Run provisioning **before** adding language implementations in this folder.

## Flag keys in code

When implementations evaluate these flags, use the keys exactly as shown:

```text
enable-grid-selection-highlight
enable-grid-highlight-color-override
show-navigation-move-count
show-host-os-emoji
```

## Language implementations

| Language | Directory | Application type | Status |
|----------|-----------|------------------|--------|
| Python | [python/](python/) | Web application | Done |
| Python | [python-console/](python-console/) | Console application | Done |
| Node.js | [node/](node/) | Web application | Done |
| Node.js | [node-console/](node-console/) | Console application | Done |
| .NET | [dotnet/](dotnet/) | Web application | Done |
| Java | [java/](java/) | Web application | Done |
| Java | [java-console/](java-console/) | Console application | Done |
| C++ | [cpp/](cpp/) | Console application | Done |
| Go | [go/](go/) | Console application | Done |
| Rust | [rust/](rust/) | Console application | Done |

All implementations require `LD_SDK_KEY` and provisioned flags. See each language README for build and run commands.

## Portal (series)

The [10-code-control portal](../portal/) embeds examples **11–15** in tabs:

| Language | Entry | URL |
|----------|-------|-----|
| Python | [../portal/python/](../portal/python/) | http://127.0.0.1:8100/ |
| Node.js | [../portal/node/](../portal/node/) | http://127.0.0.1:8101/ |
| Java | [../portal/java/](../portal/java/) | http://127.0.0.1:8102/ |
| .NET | [../portal/dotnet/](../portal/dotnet/) | http://127.0.0.1:8103/ |

See [../portal/README.md](../portal/README.md).

## Further reading

- [Flag conventions](https://launchdarkly.com/docs/guides/flags/flag-conventions)
- [Using the LaunchDarkly REST API](https://launchdarkly.com/docs/guides/api/rest-api)
- [Managing flags with Terraform](https://launchdarkly.com/docs/guides/infrastructure/terraform)
- [application.md](application.md) — flag specification and desired effects
- [00-reference-code/application.md](../../00-reference-code/application.md) — baseline grid navigator behavior
