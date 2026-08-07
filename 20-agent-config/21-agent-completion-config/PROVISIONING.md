# Provisioning — AgentControl completion config

Create the LaunchDarkly **AgentControl** resources for [21-agent-completion-config](README.md).

**Prefer REST scripts** (no MCP required):

→ **[rest/README.md](rest/README.md)** — `./create-config.sh`

This page is the **UI fallback** if you would rather click through the dashboard.

Keywords: **AgentControl** · **completion config** · **completion mode** · **config variations** · **model configuration** · **message variables** · **config targeting**

| Topic | Docs |
|-------|------|
| Create configs | [Quickstart for AgentControl](https://launchdarkly.com/docs/home/agentcontrol/quickstart) |
| Custom models | [Create and manage AI model configurations](https://launchdarkly.com/docs/home/agentcontrol/create-model-config) |
| Message variables | [Customizing AgentControl configs](https://launchdarkly.com/docs/sdk/features/agentcontrol-config) |
| Targeting | [Config targeting](https://launchdarkly.com/docs/home/agentcontrol/target) |
| REST API | [AgentControl API](https://launchdarkly.com/docs/api/agent-control) |

Series setup (SDK key, Ollama, AWS): [20-agent-config README](../README.md).

---

## Recommended — REST

```bash
export LD_API_ACCESS_TOKEN="api-..."   # API token, not SDK key
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="test"       # same env as LD_SDK_KEY

cd rest
chmod +x *.sh
./create-config.sh
./get-config.sh
```

That creates:

| Resource | Key / name |
|----------|------------|
| Model configs | `Custom.llama3.2-3b` (best), `Custom.gemma2-2b` (default), `Custom.llama3.2-1b` (simple) |
| Completion config | `equity-briefing-completion` |
| Variations | `baseline-analyst` → `gemma2:2b`, `concise-skeptic` → `llama3.2:3b`, `reckless-hype` → `llama3.2:1b` |

Then set the app SDK key and skip to [§7 What the app will do](#7-what-the-app-will-do-for-implementers).

---

## Before you start (UI path)

- [ ] LaunchDarkly project + environment exist (e.g. project `lunch-marcoly`, environment `test`)
- [ ] Your role can create AgentControl configs ([role actions](https://launchdarkly.com/docs/home/account/roles/role-actions#agentcontrol-config-actions))
- [ ] You have a **server-side SDK key** for that environment (`LD_SDK_KEY`)
- [ ] **Ollama is running** and you have pulled **all three required** demo tags (see below)—required for the persona → model demo to succeed without a cloud LLM account
- [ ] Optional later: Bedrock / cloud credentials if you retarget a variation for enhanced results

**Required Ollama installs** (do this before generate):

| Tier | Tag | Persona |
|------|-----|---------|
| Best | `llama3.2:3b` | Conservative Charlie |
| Default | `gemma2:2b` | Neutral Nancy / Anonymous Amelia |
| Simple | `llama3.2:1b` | Thoughtless Toby |

```bash
ollama pull llama3.2:3b    # required — Charlie (best)
ollama pull gemma2:2b      # required — Nancy / Amelia (default)
ollama pull llama3.2:1b    # required — Toby (simple)
ollama list
curl -s http://127.0.0.1:11434/api/tags | head
export LD_SDK_KEY="sdk-..."
export LD_AGENT_CONFIG_KEY="equity-briefing-completion"   # optional; this is the default key
```

Why three models, and how cloud fits in: [README.md#required-ollama-models](README.md#required-ollama-models) · [series setup](../README.md#3-llm-providers-start-here).

---

## 1. Register custom models (Ollama)

The demo Ollama tags are usually **not** in LaunchDarkly’s stock model picker—register them as Custom AI model configurations. This step is part of the happy path (REST does it for you).

**REST:** `./rest/create-config.sh` registers all three (or `./rest/create-model-config.sh [key] [id] [name]` one at a time).

**UI:** For each row, **+ Add a model** under Project settings → AI / model configuration ([docs](https://launchdarkly.com/docs/home/agentcontrol/create-model-config)):

| Tier | Persona / variation | Display name | Key | Model id |
|------|---------------------|--------------|-----|----------|
| Best | Charlie → `concise-skeptic` | `Ollama llama3.2:3b (best)` | `Custom.llama3.2-3b` | `llama3.2:3b` |
| Default | Nancy / Amelia → `baseline-analyst` | `Ollama gemma2:2b (default)` | `Custom.gemma2-2b` | `gemma2:2b` |
| Simple | Toby → `reckless-hype` | `Ollama llama3.2:1b (simple)` | `Custom.llama3.2-1b` | `llama3.2:1b` |

Provider: Custom / Ollama (as the UI labels it). Select the matching model on each variation below.

For Bedrock demos (optional enhanced path), pick a Nova / Claude model already listed, or add one with the Bedrock model id you use in [01-reference-agent](../../01-reference-agent/application.md#aws-bedrock). Complete `aws sso login` first ([20-agent-config README](../README.md#aws-bedrock-optional-cloud-path)).

---

## 2. Create the completion config

1. In the left sidebar: **Agents** → **Configs**.
2. **Create config**.
3. Keep mode **Completion** (not Agent).
4. Set:

| Field | Value |
|-------|-------|
| **Name** | `Equity briefing completion` |
| **Key** | `equity-briefing-completion` |

5. Copy the **key** now — the Python app will call `completion_config("equity-briefing-completion", …)` (or `LD_AGENT_CONFIG_KEY`).
6. **Create**.

Docs: [Quickstart — create an agent-based config](https://launchdarkly.com/docs/home/agentcontrol/quickstart).

---

## 3. Variation A — `baseline-analyst`

On the **Variations** tab:

1. Name the first variation **`baseline-analyst`**.
2. **Select a model** → `gemma2:2b` (default tier; or `Custom.gemma2-2b` from step 1).
3. Add a **system** message. Paste:

```text
You are an expert institutional equity research analyst with expertise in:
- Fundamental equity analysis
- Industry analysis
- Valuation

Never fabricate financial values.

Your guidance must be direct, succinct, and based entirely on the information you are presented.

When you respond, include all of the following:

1. Your conclusion based on the news stories.
2. Whether one or more of the cited companies appear to be a good investment option, and why—cite the specific factors from the information provided.
3. Your confidence as a percentage from 0% to 100%, scored only from the information in the news stories.
4. If more than one company is presented, state which one you recommend as the better option and briefly why.
```

4. Add a **user** message. Paste exactly (the `{{ stories }}` variable is filled by the app at generate time):

```text
Using only the recent Yahoo Finance headlines below, write a short market briefing that compares the two tickers. Cite story titles where helpful. Do not invent facts beyond what the headlines imply.

{{ stories }}
```

5. **Review and save**.

| Runtime variable | Filled by app | Meaning |
|------------------|---------------|---------|
| `stories` | Yes | Formatted headline block for the two tickers (same spirit as 01’s in-code user prompt) |

Optional later: `{{ ldctx.name }}` for the persona display name ([customizing configs](https://launchdarkly.com/docs/sdk/features/agentcontrol-config)).

---

## 4. Variation B — `concise-skeptic` (change without deploy)

1. **Add variation** → name **`concise-skeptic`**.
2. Model: `llama3.2:3b` (best tier; or `Custom.llama3.2-3b`) — Conservative Charlie gets the strongest model of this lot.
3. **System** message:

```text
You are a skeptical equity analyst. Be brief. Doubt unsupported claims. Never invent numbers.

Respond with:
1. One-sentence conclusion.
2. Best ticker (if any) and why, citing only the given headlines.
3. Confidence 0–100% from the headlines alone.
4. One risk or missing-information caveat.
```

4. **User** message:

```text
Compare these tickers using only the headlines. Prefer uncertainty over speculation.

{{ stories }}
```

5. **Review and save**.

---

## 5. Targeting

1. Open the config **Targeting** tab.
2. Confirm the **Default rule** serves **`baseline-analyst`** in your demo environment.
3. **Review and save** if you changed anything.

**REST equivalent:** `./rest/update-targeting.sh baseline-analyst`

Fresh configs often fall through to a **disabled** variation until you set fallthrough — the SDK then returns `enabled=false`. The REST script uses `updateFallthroughVariationOrRollout` (not `turnTargetingOn`).

### Name-based persona rules (optional demo)

Target variations by the context **`name`** attribute (the Python app sets `name` from the selected persona):

| Context `name` | Serves | Model |
|----------------|--------|-------|
| `Conservative Charlie` | `concise-skeptic` | `llama3.2:3b` (best) |
| `Neutral Nancy` | `baseline-analyst` | `gemma2:2b` (default) |
| `Thoughtless Toby` | `reckless-hype` | `llama3.2:1b` (simple) |
| Default rule | `baseline-analyst` (e.g. **Anonymous Amelia** — anonymous context, no name rule) | `gemma2:2b` |

```bash
./rest/create-variation-reckless-hype.sh   # if the variation is missing
./rest/update-name-targeting.sh
```

`reckless-hype` is the Thoughtless Toby voice (simple model): no caution, fabricates freely, sweeping claims, and cheerfully recommends defunct companies (e.g. Pets.com).

**Anonymous Amelia** is not in targeting: the app builds an **anonymous** user context (`anonymous=true`, key `anonymous-amelia`). Name rules do not match → fallthrough → `baseline-analyst`.

To demo “change without deploy” later (no code change):

- Either edit `baseline-analyst` messages/model in place, **or**
- Point the default rule at `concise-skeptic`, save, and regenerate in the app (`./rest/update-targeting.sh concise-skeptic`), **or**
- Use name targeting above and switch personas in the UI.

Docs: [Config targeting](https://launchdarkly.com/docs/home/agentcontrol/target).

---

## 6. Smoke-check in the UI

- [ ] Config key is exactly `equity-briefing-completion`
- [ ] Mode is **Completion**
- [ ] Variations include `baseline-analyst`, `concise-skeptic`, and `reckless-hype`
- [ ] User messages include `{{ stories }}`
- [ ] Default rule serves `baseline-analyst`
- [ ] Model on variations matches a provider you can reach (Ollama or Bedrock)

---

## 7. What the app will do (for implementers)

When Python (and later languages) wire generate:

1. Build a LaunchDarkly **context** from the selected persona (`key` = persona id, `name` = display name).
2. Call the AI SDK **`completion_config`** with key `equity-briefing-completion`, that context, a disabled/fallback default, and variables `{"stories": <formatted headlines>}`.
3. Use returned **model** + **messages** for the LLM call; stream tokens to the UI.
4. Show the **served** model in status chrome.

Spec detail: [application.md](application.md).

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| SDK returns disabled / fallback | Config key typo; wrong environment SDK key; fallthrough still on disabled variation — run `./rest/update-targeting.sh baseline-analyst` |
| Empty or unsubstituted `{{ stories }}` | App must pass `stories` into `completion_config` variables |
| Model errors from Ollama | Daemon up; tag pulled; custom model id matches `ollama list` |
| Bedrock auth errors | `aws sso login --profile Administrator`; region; model access |

---

## Related

- [rest/README.md](rest/README.md) — REST scripts (preferred)
- [application.md](application.md) — behavior specification
- [README.md](README.md) — example overview
- [../README.md](../README.md) — series LLM / AWS / LD setup
