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

- **In repo, not in inventory** — declare candidates  
- **In inventory, not in repo** — unused inventory or non-scanned languages (go/rust/cpp)

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
| `--json` | Machine-readable |

### `instrument`

- Default: dry-run plan of comment inserts.
- `--write`: insert comments above evaluation key definitions; **merge** missing keys into inventory (never delete; do not overwrite non-empty `name` / `notes`).
- Languages: Python, Node, Java only.
- Idempotent: skips if a nearby `LaunchDarkly:` line already has the same `key=`.

### Comment contract

```text
# LaunchDarkly: flag key=configure-lucky-number name="Configure: lucky number" kind=number
# https://app.launchdarkly.com/projects/{project}/features/configure-lucky-number
```

```text
# LaunchDarkly: ai-config key=equity-briefing-completion name="Equity briefing completion" mode=completion
# https://app.launchdarkly.com/projects/{project}/ai-configs/equity-briefing-completion
```

Include **key**, **name**, and **kind** (or `mode` for AI Config). Do not list variation values in comments.

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
