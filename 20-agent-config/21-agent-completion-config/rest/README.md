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
| `LD_MODEL_CONFIG_KEY` | No | Default `Custom.llama3.2-3b` |
| `LD_MODEL_ID` | No | Default `llama3.2:3b` (Ollama tag) |
| `LD_MODEL_PROVIDER` | No | Default `Custom` |

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"   # or your project
export LD_ENVIRONMENT_KEY="test"        # must match your LD_SDK_KEY environment
```

## How to run

```bash
cd 20-agent-config/21-agent-completion-config/rest
chmod +x *.sh
./create-config.sh
./get-config.sh
```

### What `create-config.sh` does

1. **Model config** — creates `Custom.llama3.2-3b` (Ollama `llama3.2:3b`) if missing
2. **AI config** — `equity-briefing-completion`, mode **completion**, tags `lunch-marcoly`
3. **Variation** `baseline-analyst` — system + user messages (user includes `{{ stories }}`)
4. **Variation** `concise-skeptic` — shorter skeptical voice for change-without-deploy demos
5. **Targeting** — when `LD_ENVIRONMENT_KEY` is set, fallthrough → `baseline-analyst`

> **Why step 5 matters:** a new config’s fallthrough points at an auto-generated **disabled** variation. Until you flip fallthrough, the AI SDK returns `enabled=false`. Do **not** use `turnTargetingOn` — use `updateFallthroughVariationOrRollout` (see `update-targeting.sh`).

### Scripts

| Script | Method | Endpoint | Result |
|--------|--------|----------|--------|
| `create-model-config.sh` | `POST` | `/projects/{p}/ai-configs/model-configs` | Custom Ollama model |
| `create-config.sh` | `POST` (+ targeting `PATCH`) | `/projects/{p}/ai-configs` … | Full demo config |
| `create-variation-reckless-hype.sh` | `POST` | `…/variations` | Thoughtless Toby voice |
| `get-config.sh` | `GET` | config + optional targeting | Summary JSON |
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

Serve different variations from the persona **name** attribute (set by the Python app):

| Context `name` | Variation |
|----------------|-----------|
| `Conservative Charlie` | `concise-skeptic` |
| `Neutral Nancy` | `baseline-analyst` |
| `Thoughtless Toby` | `reckless-hype` |
| (everyone else) | `baseline-analyst` (fallthrough) |

```bash
./create-variation-reckless-hype.sh   # once, if missing
./update-name-targeting.sh
```

In the UI: Charlie (skeptical) vs Nancy (baseline) vs Toby (reckless hype / Pets.com energy).

### Delete and recreate

```bash
./delete-config.sh
./create-config.sh
```

Deletion removes the AI config only. The model config `Custom.llama3.2-3b` is left in place for reuse.

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
| SDK `enabled=false` | Fallthrough still on disabled variation — run `./update-targeting.sh baseline-analyst` |
| 409 / already exists | `./delete-config.sh` then recreate, or `./get-config.sh` to inspect |
| Model picker / “NO MODEL” | `LD_MODEL_CONFIG_KEY` must exist; format `Provider.model-id` (e.g. `Custom.llama3.2-3b`) |
| Wrong environment | `LD_ENVIRONMENT_KEY` must match the environment of `LD_SDK_KEY` |
| Ollama errors later | Daemon up; `ollama pull llama3.2:3b`; model **id** matches the tag |

## Further reading

- [PROVISIONING.md](../PROVISIONING.md) — UI fallback checklist
- [application.md](../application.md) — app behavior when generate uses this config
- [10-flag-enablement/rest](../../../10-flag-enablement/rest/) — same REST script pattern for feature flags
