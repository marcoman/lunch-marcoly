# REST API provisioning — AgentControl completion config

Create, read, retarget, and delete the **`equity-briefing-completion`** AgentControl config with the [LaunchDarkly REST API](https://launchdarkly.com/docs/guides/api/rest-api).

This is the **primary** provisioning path for [21-agent-completion-config](../README.md). Use the [UI checklist](../PROVISIONING.md) only if you prefer the dashboard.

Keywords: **AgentControl** · **completion config** · **AI model config** · **config variations** · **config targeting** · **semantic patch**

| Topic | Docs |
|-------|------|
| Create config | [Create new AI Config](https://launchdarkly.com/docs/api/agent-control/post-ai-config) |
| Create variation | [Create AI Config variation](https://launchdarkly.com/docs/api/agent-control/post-ai-config-variation) |
| Custom model | [Create an AI model config](https://launchdarkly.com/docs/api/agent-control/post-model-config) |
| Targeting | [Update AI Config targeting](https://launchdarkly.com/docs/api/agent-control/patch-ai-config-targeting) |
| Product guide | [Quickstart for AgentControl](https://launchdarkly.com/docs/home/agentcontrol/quickstart) |

## Prerequisites

- `curl` and `jq`
- LaunchDarkly **API access token** (not the SDK key) with AgentControl permissions
- Project + environment that match the SDK key your app will use

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_API_ACCESS_TOKEN` | Yes | `Authorization` header (`api-…`) |
| `LD_PROJECT_KEY` | Yes | Project that owns the config |
| `LD_ENVIRONMENT_KEY` | For targeting | Environment whose fallthrough serves `baseline-analyst` |
| `LD_API_HOST` | No | Default `https://app.launchdarkly.com` |
| `LD_API_VERSION` | No | Default `beta` (AgentControl) |
| `LD_CONFIG_KEY` | No | Default `equity-briefing-completion` |
| `LD_MODEL_BEST_*` | No | Charlie / `concise-skeptic` → `Custom.llama3.2-3b` / `llama3.2:3b` |
| `LD_MODEL_DEFAULT_*` | No | Nancy+Amelia / `baseline-analyst` → `Custom.gemma2-2b` / `gemma2:2b` |
| `LD_MODEL_SIMPLE_*` | No | Toby / `reckless-hype` → `Custom.llama3.2-1b` / `llama3.2:1b` |
| `LD_MODEL_PROVIDER` | No | Default `Custom` |

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"   # or your project
export LD_ENVIRONMENT_KEY="test"        # must match your LD_SDK_KEY environment
```

## Required: pull the three Ollama models

REST provisioning registers **Custom** model configs that point at local Ollama tags. The apps call those tags at generate time. **Pull all three before you demo**—otherwise Charlie, Nancy/Amelia, or Toby will fail when their variation is served.

Local models are how anyone succeeds without a cloud LLM account. Cloud (e.g. Bedrock) remains optional for enhanced results once you retarget a variation. Full narrative: [../README.md#required-ollama-models](../README.md#required-ollama-models).

| Tier | Tag | Persona |
|------|-----|---------|
| Best | `llama3.2:3b` | Conservative Charlie |
| Default | `gemma2:2b` | Neutral Nancy / Anonymous Amelia |
| Simple | `llama3.2:1b` | Thoughtless Toby |

```bash
ollama pull llama3.2:3b    # required — Charlie (best)
ollama pull gemma2:2b      # required — Nancy / Amelia (default)
ollama pull llama3.2:1b    # required — Toby (simple)
ollama list                # confirm all three appear
```

## How to run

```bash
cd 20-agent-config/21-agent-completion-config/rest
chmod +x *.sh
./create-config.sh
./update-name-targeting.sh
./get-targeting-status.sh
```

If the AI config already exists from an older single-model setup:

```bash
./delete-config.sh
./create-config.sh
./update-name-targeting.sh   # Charlie / Nancy / Toby name rules
```

Model configs are left in place across deletes; recreate is idempotent for them.

### What `create-config.sh` does

1. **Model configs** — creates best / default / simple Custom Ollama models if missing
2. **AI config** — `equity-briefing-completion`, mode **completion**, tags `lunch-marcoly`
3. **Variation** `baseline-analyst` — middle model (`gemma2:2b`) + baseline messages (`{{ stories }}`)
4. **Variation** `concise-skeptic` — best model (`llama3.2:3b`) + skeptical voice (Charlie)
5. **Variation** `reckless-hype` — simple model (`llama3.2:1b`) + reckless voice (Toby)
6. **Targeting** — when `LD_ENVIRONMENT_KEY` is set, fallthrough → `baseline-analyst`

| Persona | Variation | Model tier | Ollama id |
|---------|-----------|------------|-----------|
| Conservative Charlie | `concise-skeptic` | Best | `llama3.2:3b` |
| Neutral Nancy | `baseline-analyst` | Default | `gemma2:2b` |
| Thoughtless Toby | `reckless-hype` | Simple | `llama3.2:1b` |
| Anonymous Amelia | fallthrough → `baseline-analyst` | Default | `gemma2:2b` |

> **Why step 6 matters:** a new config’s fallthrough points at an auto-generated **disabled** variation. Until you flip fallthrough, the AI SDK returns `enabled=false`. Do **not** use `turnTargetingOn` — use `updateFallthroughVariationOrRollout` (see `update-targeting.sh`).

### Scripts

| Script | Method | Endpoint | Result |
|--------|--------|----------|--------|
| `create-model-config.sh [key] [id] [name]` | `POST` | `/projects/{p}/ai-configs/model-configs` | Custom Ollama model (idempotent) |
| `create-config.sh` | `POST` (+ targeting `PATCH`) | `/projects/{p}/ai-configs` … | Full demo config + three models |
| `create-variation-reckless-hype.sh` | `POST` | `…/variations` | Thoughtless Toby voice (simple model) |
| `get-config.sh` | `GET` | config + optional targeting | Summary JSON |
| `get-targeting-status.sh` | `GET` | config + targeting (+ metrics) | Demo status: variations · name rules · fallthrough |
| `update-targeting.sh [variation]` | `PATCH` | `…/ai-configs/{key}/targeting` | Fallthrough → variation |
| `update-name-targeting.sh` | `PATCH` | `…/ai-configs/{key}/targeting` | Name rules + fallthrough |
| `delete-config.sh [key]` | `DELETE` | `…/ai-configs/{key}` | Config removed |

Messages live under `messages/` (same text as the UI checklist).

### Demo: change without deploy

Point fallthrough at the skeptic variation, regenerate in the app, then flip back:

```bash
./update-targeting.sh concise-skeptic
# … generate in the app …
./update-targeting.sh baseline-analyst
```

### Demo: target by user name

Serve different **prompts and models** from the persona **name** attribute (set by the apps):

| Context `name` | Variation | Model |
|----------------|-----------|-------|
| `Conservative Charlie` | `concise-skeptic` | `llama3.2:3b` |
| `Neutral Nancy` | `baseline-analyst` | `gemma2:2b` |
| `Thoughtless Toby` | `reckless-hype` | `llama3.2:1b` |
| (everyone else, e.g. Anonymous Amelia) | `baseline-analyst` (fallthrough) | `gemma2:2b` |

```bash
./create-variation-reckless-hype.sh   # once, if missing
./update-name-targeting.sh
```

In the UI: Charlie (skeptical + best model) vs Nancy (baseline + default) vs Toby (reckless + simple) vs **Anonymous Amelia** (anonymous → fallthrough / baseline).

### Demo status check

```bash
./get-targeting-status.sh
./get-targeting-status.sh --verbose
./get-targeting-status.sh --json
```

Example output:

```text
Agent Config Key: equity-briefing-completion
Environment: test
Healthy: yes

Targeting:
  on=true  fallthrough=baseline-analyst (matches)
  name rules: 3

Variations:
  ✓ baseline-analyst  model=Custom.gemma2-2b  — Neutral Nancy / Amelia (fallthrough)
  ✓ concise-skeptic  model=Custom.llama3.2-3b  — Conservative Charlie
  ✓ reckless-hype  model=Custom.llama3.2-1b  — Thoughtless Toby

Name targeting:
  ✓ Conservative Charlie → concise-skeptic
  ✓ Neutral Nancy → baseline-analyst
  ✓ Thoughtless Toby → reckless-hype
```

`get-config.sh` remains the raw inspector; `get-targeting-status.sh` is the before/after demo check
(sibling idea to 22’s `get-feedback-status.sh` and 23’s `get-tools-status.sh`).

### Delete and recreate

```bash
./delete-config.sh
./create-config.sh
```

Deletion removes the AI config only. The three Custom model configs are left in place for reuse.

## Equivalent curl (create fallthrough)

After you know the targeting variation `_id` (from `./get-config.sh` or the targeting `GET`):

```bash
curl -X PATCH "${LD_API_HOST:-https://app.launchdarkly.com}/api/v2/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY:-equity-briefing-completion}/targeting?env=${LD_ENVIRONMENT_KEY}" \
  -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
  -H "LD-API-Version: ${LD_API_VERSION:-beta}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "{
    \"environmentKey\": \"${LD_ENVIRONMENT_KEY}\",
    \"instructions\": [{
      \"kind\": \"updateFallthroughVariationOrRollout\",
      \"variationId\": \"<targeting-variation-uuid>\"
    }]
  }"
```

## Troubleshooting

| Symptom | Check |
|---------|--------|
| SDK `enabled=false` | Fallthrough still on disabled variation — run `./update-targeting.sh baseline-analyst` (or `./get-targeting-status.sh`) |
| 409 / already exists | `./delete-config.sh` then recreate, or `./get-config.sh` to inspect |
| Model picker / “NO MODEL” | `modelConfigKey` must exist; format `Provider.model-id` (e.g. `Custom.gemma2-2b`) |
| Wrong environment | `LD_ENVIRONMENT_KEY` must match the environment of `LD_SDK_KEY` |
| Ollama errors later | Daemon up; **all three** tags pulled (`ollama list`); model **id** on the variation matches the tag |

## Further reading

- [PROVISIONING.md](../PROVISIONING.md) — UI fallback checklist
- [application.md](../application.md) — app behavior when generate uses this config
- [10-flag-enablement/rest](../../../10-flag-enablement/rest/) — same REST script pattern for feature flags
