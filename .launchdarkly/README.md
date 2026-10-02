# `.launchdarkly/` — inventory and visibility

Repo-root contract for **what LaunchDarkly resources this collection expects**, and a thin CLI to compare that inventory to live LaunchDarkly state and to the codebase.

This phase is **inventory + visibility + declare helpers**. Create, delete, toggle, Terraform apply, and GitHub Actions provisioning are deferred. Example [`rest/`](../10-code-control/11-flag-enablement/rest/) and [`terraform/`](../10-code-control/11-flag-enablement/terraform/) folders remain the customer-facing provisioners.

## Declare loop

```text
code change → ldctl discover → ldctl instrument [--write] → polish inventory → validate / status
```

“Declare” means desired state in `inventory/*.yaml`, not applying resources in LaunchDarkly.

## Source of truth (hybrid)

| Layer | Role |
|-------|------|
| **Git inventory** (`inventory/`, optional `plans/`) | Desired keys, metadata, example links |
| **Repo scan** (`discover`) | Keys referenced in app code and provisioning |
| **LaunchDarkly API** | Actual state (`status` / `report`) |

## Layout

```text
.launchdarkly/
├── README.md
├── project.yaml
├── inventory/
│   ├── flags.yaml
│   ├── agent-configs.yaml
│   └── metrics.yaml
├── plans/
│   └── guarded-rollouts.yaml
├── .ldctlignore
├── python/ldctl/
└── bin/ldctl
```

## CLI

Requires the repo venv and `PyYAML` (see root `requirements.txt`).

```bash
source .venv/bin/activate
export LD_API_ACCESS_TOKEN=…   # required for status/report
export LD_PROJECT_KEY=lunch-marcoly
export LD_ENVIRONMENT_KEY=test

.launchdarkly/bin/ldctl validate
.launchdarkly/bin/ldctl discover
.launchdarkly/bin/ldctl discover --json
.launchdarkly/bin/ldctl status
.launchdarkly/bin/ldctl status --off --kind flag
.launchdarkly/bin/ldctl status --tag grid-navigator
.launchdarkly/bin/ldctl instrument          # dry-run
.launchdarkly/bin/ldctl instrument --write  # comments + inventory merge
```

| Command | API token? | Purpose |
|---------|------------|---------|
| `validate` | No | Schema, unique keys, example paths |
| `discover` | No | Repo ↔ inventory gaps (flags + AI Configs) |
| `status` / `report` | Yes | Desired vs live; filters below |
| `instrument` | No | Comment markup (py/node/java); `--write` merges inventory |

### `discover`

Scans **evaluation** (`.py` / `.js` / `.java`) and **provisioning** (`rest/`, `terraform/`). Each gap row includes provenance: `evaluation`, `provisioning`, or `both`.

Kotlin (`.kt`) and Swift (`.swift`) are skipped, along with Go, Rust, and C++. `discover` and `instrument` share one language set: Python, Node, and Java. The 50-mobile apps are Kotlin and Swift, so a flag that lives only in those sources is not an evaluation hit.

An AI Config hit is `CONFIG_KEY` / `configKey`, any other `*_KEY = "equity-…"`, `DEFAULT_NODE_* = "equity-…"`, or a shell default `${LD_…:=equity-…}`. Judge keys and graph node keys use those shapes. Variation names stay out.

Provisioning files contain many `key` strings (variations, segments, metrics). A provisioning hit is kept when the key starts with `configure-` (a value the app reads), `show-` (a boolean that reveals a UI element), or `enable-` (turn a capability on).

[`.ldctlignore`](.ldctlignore) uses gitignore syntax. Patterns are relative to the **repo root**, not to `.launchdarkly/`. `discover` and `instrument` skip matching paths before the prefix gate. `99-use-cases/19-terraform-sentinel/` is ignored because that example is a policy fixture, not an app that deploys a flag.

- **In repo, not in inventory** — declare candidates  
- **In inventory, not in repo** — unused inventory or non-scanned languages (Kotlin, Swift, Go, Rust, C++)

Exit `1` if either gap list is non-empty. Text fits ~100 columns; use `--json` for CI receipts later.

### `status` / `report` filters

| Flag | Behavior |
|------|----------|
| `--on` / `--off` | Env targeting for `LD_ENVIRONMENT_KEY` |
| `--tag TAG` | Live tags (repeatable = AND) |
| `--kind` | `flag` \| `agent_config` \| `metric` \| `model_config` |
| `--key SUBSTR` | Case-insensitive substring |
| `--example` | Stub (warns; ignored) |
| `--state` | Stub (warns; ignored) |
| `--json` | Machine-readable. Use this when the text table truncates `KEY`, `TAGS`, or `DETAIL`. |

`status` and `report` are the same command. They compare `inventory/` to the project in `LD_PROJECT_KEY` and the environment in `LD_ENVIRONMENT_KEY` (`project.yaml` defaults to `test`). `ldctl` does not create, edit, or delete anything.

Columns: `STATE`, `ON` (flag targeting in that environment), `KIND`, `KEY`, `TAGS`, `DETAIL`. The text table shortens long cells. `ON` is `on` or `off` for a flag, `n/a` for an AI Config, and `—` when the row has no targeting value (missing resources, model configs).

#### States

| State | Meaning | What to do |
|-------|---------|------------|
| `present` | The resource is in LaunchDarkly and matches the inventory field this command compares. | Nothing. `ON=off` is still `present`: the flag exists and its variation type matches. Off is a targeting choice, not drift. |
| `drift` | The resource exists, and one compared field differs. | Read `DETAIL` (`--json` if the table cut it off). Fix the side that is wrong. This tool will not push the correction. |
| `missing` | LaunchDarkly returned 404 for that key. | Create it from the example's `rest/` or `terraform/`, or remove the inventory entry if the key should not exist in this project. |
| `error` | The API call failed (auth, network, or a non-404 status). | Fix the token, host, or project key and run the report again. |

Compared fields:

- **Flag** — variation type (`boolean`, `string`, `number`, `json`) versus `kind` in `inventory/flags.yaml`.
- **AI Config** — `mode`, and any variation keys listed in `inventory/agent-configs.yaml` that are absent live.
- **Metric** — `eventKey` versus `event_key` in `inventory/metrics.yaml`.
- **Model config** — presence of the key. A found model config stays `present`.

#### What a production report looks like

`LD_ENVIRONMENT_KEY=production` on this repo produced `drift=10`, `missing=5`, `present=38` (`shown=53`). Counts move as flags are created. The shape of a row does not:

```text
project=lunch-marcoly  environment=production

STATE    ON   KIND          KEY                              DETAIL
-------  ---  ------------  -------------------------------  ------------------------------------
present  on   flag          enable-grid-selection-highlight  env=production:on; variations=6
present  off  flag          show-host-os-emoji               env=production:off; variations=2
drift    off  flag          configure-team-label-style       … kind desired=boolean actual=string
missing  —    flag          enable-mobile-platform-rollout   not found in project
present  n/a  agent_config  equity-briefing-completion       variations=3; env=production:n/a
missing  —    agent_config  equity-briefing-graph            not found
```

**Drift in that run** is flag kind. `instrument --write` stores `kind: boolean` when the scan cannot see a typed `variation` call. Several live flags are strings (a highlight color, or `configure-team-label-style`). `DETAIL` says `kind desired=boolean actual=string`.

Set `kind` in `inventory/flags.yaml` to the type in that example's `application.md`. Do not change the live flag to boolean to satisfy a guessed inventory kind.

**Missing in that run:**

| Key | Next step |
|-----|-----------|
| `enable-client-bootstrap-highlight`, `show-client-bootstrap-move-count` | Provision [35-client-bootstrap](../30-client-sdk/35-client-bootstrap/rest/). |
| `enable-mobile-platform-rollout` | Provision [54-platform-rollout](../50-mobile/54-platform-rollout/rest/). `create-flag.sh` is state 1 (Android only). |
| `show-twilio-inner-circle-badge` | Provision [34-synced-segments-twilio](../30-client-sdk/34-synced-segments-twilio/rest/). |
| `equity-briefing-graph` | This is the graph id (`DEFAULT_GRAPH_KEY`), not an AI Config. The node configs (`equity-briefing-graph-assess`, and the rest) are the AI Configs, and they reported `present`. Remove this key from `inventory/agent-configs.yaml`. Do not create an AI Config with this key. |

### `instrument`

- Default: dry-run plan of comment inserts.
- `--write`: insert comments above evaluation key definitions; **merge** missing keys into inventory (never delete; do not overwrite non-empty `name` / `notes`).
- Languages: Python, Node, Java only.
- Idempotent: skips if a nearby `LaunchDarkly:` line already has the same `key=`.

### Comment contract

`instrument --write` inserts two comment lines above the key assignment. Python uses `#`. JavaScript and Java use `//`. The project key and host come from `project.yaml`.

Include **key**, **name**, and **kind** (or `mode` for an AI Config). Do not list variation values in comments.

**Flag** — `configure-lucky-number`

```python
# LaunchDarkly: flag key=configure-lucky-number name="Configure: lucky number" kind=number
# https://app.launchdarkly.com/projects/lunch-marcoly/features/configure-lucky-number
FLAG_LUCKY = "configure-lucky-number"
```

```javascript
// LaunchDarkly: flag key=configure-lucky-number name="Configure: lucky number" kind=number
// https://app.launchdarkly.com/projects/lunch-marcoly/features/configure-lucky-number
const FLAG_LUCKY = "configure-lucky-number";
```

```java
// LaunchDarkly: flag key=configure-lucky-number name="Configure: lucky number" kind=number
// https://app.launchdarkly.com/projects/lunch-marcoly/features/configure-lucky-number
static final String FLAG_LUCKY = "configure-lucky-number";
```

**AI Config** — `equity-briefing-completion`

```python
# LaunchDarkly: ai-config key=equity-briefing-completion name="Equity briefing completion" mode=completion
# https://app.launchdarkly.com/projects/lunch-marcoly/ai-configs/equity-briefing-completion
DEFAULT_CONFIG_KEY = "equity-briefing-completion"
```

```javascript
// LaunchDarkly: ai-config key=equity-briefing-completion name="Equity briefing completion" mode=completion
// https://app.launchdarkly.com/projects/lunch-marcoly/ai-configs/equity-briefing-completion
const DEFAULT_CONFIG_KEY = "equity-briefing-completion";
```

```java
// LaunchDarkly: ai-config key=equity-briefing-completion name="Equity briefing completion" mode=completion
// https://app.launchdarkly.com/projects/lunch-marcoly/ai-configs/equity-briefing-completion
static final String DEFAULT_CONFIG_KEY = "equity-briefing-completion";
```

### Environment variables

Aligned with [`project.md`](../project.md):

| Variable | Required | Notes |
|----------|----------|-------|
| `LD_API_ACCESS_TOKEN` | For status/report | Authorization header |
| `LD_PROJECT_KEY` | No | Defaults from `project.yaml` |
| `LD_ENVIRONMENT_KEY` | No | Defaults from `project.yaml` |
| `LD_API_HOST` | No | Defaults to `https://app.launchdarkly.com` |

## How this relates to Terraform, REST, and GitHub

| Layer | Role today | This folder |
|-------|------------|-------------|
| **REST / Terraform** | Provision per example | Untouched; discover reports provisioning hits |
| **GitHub Actions** | None yet | Future: `discover --json` / `report --json` as PR receipts |

## Docs keywords

- Feature flags · boolean / multivariate variations · contexts  
  https://docs.launchdarkly.com/home/flags  
- AgentControl · AI Configs  
  https://docs.launchdarkly.com/home/ai-configs  
- REST API  
  https://launchdarkly.com/docs/guides/api/rest-api  

## Out of scope (for now)

- `ldctl apply` / create / delete / turn on-off  
- Go / Rust / C++ instrumentation  
- Starting progressive or guarded rollouts from `plans/`  
- Replacing per-example `rest/` or `terraform/`
