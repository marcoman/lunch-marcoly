# Segments by Name

LaunchDarkly **segments** driven by **context attributes** parsed from the login username.

## What this demonstrates

- **Context attributes** the application supplies (`segmentType`, `namedColor`, `userKind`, `beta`, `generic`)
- **Rule-based segments** that match those attributes
- **Segment-targeted flag** — `configure-grid-selection-green-highlight` returns a highlight **color** variation
- [00-reference](../../00-reference/) grid navigator with colored selection when flagged on

See [application.md](application.md) for context rules, segment types, and acceptance criteria.

## How it works

```text
Username → application builds LD context → segment match → flag variation (color)
```

**Priority rules** (early exit):

1. `generic` → no color
2. Exact color name (`yellow`, `red`, …) → that color
3. Even letters → human; odd → robot
4. Contains `beta` → beta segment combined with human/robot

**Allowed types:** Generic, named color, human, robot, human+beta, robot+beta

## Flag key

```text
configure-grid-selection-green-highlight
```

String variations: `none`, `yellow`, `red`, `blue`, `green`, `purple`.

> This use case provisions the flag as **string** for segment targeting. [10-flag-enablement](../../10-flag-enablement/) uses the same key as **boolean** — use a dedicated environment if both exist.

## Prerequisites

```bash
export LD_PROJECT_KEY="default"
export LD_ENVIRONMENT_KEY="production"
export LD_SDK_KEY="sdk-..."
export LD_API_ACCESS_TOKEN="api-..."   # rest/
export LD_ACCESS_TOKEN="api-..."       # terraform/
```

## Provisioning

| Approach | Directory |
|----------|-----------|
| Terraform | [terraform/](terraform/) |
| REST API | [rest/](rest/) |

Terraform and REST turn the flag **on** with segment targeting after provisioning.

## Try it

```bash
cd python-console
python 02-segments-by-name.py
```

Example usernames:

| Username | Segment type | Highlight (flag on) |
|----------|--------------|---------------------|
| `generic` | Generic | none |
| `yellow` | Named color | yellow |
| `ab` | Human (2 letters) | yellow |
| `alice` | Robot (5 letters) | red |
| `beta` | Human + beta | green |
| `abeta` | Robot + beta | purple |

## Language implementations

| Language | Directory | Application type |
|----------|-----------|------------------|
| Python | [python-console/](python-console/) | Console |
| Python | [python/](python/) | Web |
| Node.js | [node-console/](node-console/) | Console |
| Node.js | [node/](node/) | Web |
| Java | [java-console/](java-console/) | Console |
| Java | [java/](java/) | Web |
| Go | [go/](go/) | Console |
| Rust | [rust/](rust/) | Console |
| C++ | [cpp/](cpp/) | Console |

Shared modules: [`segment_context.py`](segment_context.py) / [`segment-context.js`](segment-context.js), [`segment_style.py`](segment_style.py) / [`segment-style.js`](segment-style.js).

## LaunchDarkly capabilities

- [Contexts](https://launchdarkly.com/docs/home/observability/context-kinds) — custom attributes on user contexts
- [Segments](https://launchdarkly.com/docs/home/flags/segments) — rule-based audience definitions
- [Targeting rules](https://launchdarkly.com/docs/home/flags/targeting-rules) — `segmentMatch` serves flag variations
- [String flag variations](https://launchdarkly.com/docs/sdk/features/flag-types) — color returned from evaluation

## Related examples

- [00-reference](../../00-reference/) — baseline grid
- [10-flag-enablement](../../10-flag-enablement/) — boolean highlight + app-side cohort parsing
- [01-abcd-test](../01-abcd-test/) — percentage rollout A/B/C/D test
