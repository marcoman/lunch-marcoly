# .NET web — AgentControl completion config

Same UI as [01-reference-agent/dotnet](../../../01-reference-agent/dotnet/) (no LaunchDarkly), but **Generate AI Report** loads **model**, **system**, and **user** messages from LaunchDarkly AgentControl.

This example uses the official **LaunchDarkly AI SDK for .NET** (`LaunchDarkly.ServerSdk.Ai`) — `LdAiClient.CompletionConfig(...)` returns the targeted variation's model + messages directly, and `config.CreateTracker()` reports generation success/error/duration back to LaunchDarkly. A parallel `LdClient.JsonVariationDetail(...)` call reads the raw `_ldMeta` JSON (variation key, version, enabled) for the debug panel, since those fields are internal on the typed AI SDK object in the installed package version.

Keywords: **AgentControl** · **completion config** · **AI SDK for .NET** · **CompletionConfig** · **CreateTracker**

| Topic | Docs |
|-------|------|
| .NET AI SDK | [LaunchDarkly AI SDK for .NET](https://launchdarkly.com/docs/sdk/ai/dotnet) |
| .NET server SDK | [.NET (server-side) SDK](https://launchdarkly.com/docs/sdk/server-side/dotnet) |
| AgentControl quickstart | [AgentControl quickstart](https://launchdarkly.com/docs/home/agentcontrol/quickstart) |
| Provision this config | [../rest/README.md](../rest/README.md) |

## Prerequisites

1. **.NET SDK 10** — `export PATH="/usr/local/share/dotnet:$PATH"` if it's not already on `PATH`
2. Provisioned config: `cd ../rest && ./create-config.sh`
3. `LD_SDK_KEY` for the **same environment** as `LD_ENVIRONMENT_KEY` used in targeting
4. **Required:** all three Ollama tags pulled ([parent README](../README.md#required-ollama-models))

Local models let anyone complete the demo without a cloud LLM account. Cloud (Bedrock) remains optional for enhanced results later.

```bash
export LD_SDK_KEY="sdk-..."
# optional: export LD_AGENT_CONFIG_KEY="equity-briefing-completion"
ollama pull llama3.2:3b    # required — Charlie (best)
ollama pull gemma2:2b      # required — Nancy / Amelia (default)
ollama pull llama3.2:1b    # required — Toby (simple)
ollama list
```

## Build & run

```bash
export PATH="/usr/local/share/dotnet:$PATH"
cd 20-agent-config/21-agent-completion-config/dotnet
dotnet restore
dotnet build
dotnet run
```

Open **http://127.0.0.1:8213/** (Python: 8210; Node.js: 8211; Java: 8212).

## What to try

1. **Get Stories** → headline panels fill
2. **Generate AI Report** → User Prompt shows the LD user message (with `{{ stories }}` filled); Response streams from Ollama
3. Provider/model should match the served variation (`gemma2:2b` for Nancy; `llama3.2:3b` for Charlie; `llama3.2:1b` for Toby)
4. Switch users: **Charlie** → `concise-skeptic`; **Nancy** → `baseline-analyst`; **Toby** → `reckless-hype`; **Anonymous Amelia** → fallthrough `baseline-analyst` (anonymous context)
5. Or flip fallthrough only: `../rest/update-targeting.sh concise-skeptic` → regenerate → flip back

## Architecture

| File | Role |
|------|------|
| `Program.cs` | Minimal API / Kestrel — routes + SSE bridge |
| `AgentCore.cs` | **LD insertion:** `LdAiClient.CompletionConfig` → `CreateTracker` → Ollama stream |
| `YahooNews.cs` | Yahoo headlines + `../stories/` cache |
| `JsonUtil.cs` | `JsonNode` ⇄ `Dictionary<string, object?>` helpers (mirrors the loose typing used in the Node/Python examples) |
| `wwwroot/index.html` | Browser UI (shared with Node/Python/Java) |

## Environment

| Variable | Required | Notes |
|----------|----------|-------|
| `LD_SDK_KEY` | Yes | Server-side SDK key (fails hard if missing) |
| `LD_AGENT_CONFIG_KEY` | No | Default `equity-briefing-completion` |
| `OLLAMA_HOST` | No | Default `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | No | Default `llama3.2:3b` (code baseline) |

Port is fixed at **8213** for this example (see the ports table in the [series README](../../README.md)).

## Fallback (config off)

If you **disable** the AgentControl config in LaunchDarkly, evaluation returns `_ldMeta.enabled=false` (the disabled variation)—not your SDK default. This app then uses the **in-code baseline-analyst** prompts from [`../rest/messages/baseline-*.txt`](../rest/messages/) plus local Ollama (`OLLAMA_MODEL`, default `llama3.2:3b`).

Provider/model shows `ollama / llama3.2:3b (code baseline)`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Want LD variations again | Turn the config **on** and confirm fallthrough → `baseline-analyst` |
| Missing `LD_SDK_KEY` | Export SDK key for the targeted environment |
| Ollama errors | Daemon up; model id on variation matches `ollama list` |
| Wrong voice after targeting change | Wait a few seconds for stream refresh, then Generate again |
| `dotnet: command not found` | `export PATH="/usr/local/share/dotnet:$PATH"` |

## API gaps vs. Node.js

- **Metadata access**: The installed `LaunchDarkly.ServerSdk.Ai` (0.12.0) package marks `VariationKey`/`Version` as `internal` on the typed completion-config object, unlike the Node SDK's `tracker`/config object which exposes these directly. This example calls `LdClient.JsonVariationDetail` alongside `LdAiClient.CompletionConfig` to read the same `_ldMeta` fields (`variationKey`, `version`, `enabled`) the Node UI displays.
- **Default conversion**: `LdAiCompletionConfigDefault.ToLdValue()` is internal, so the baseline fallback default used for `JsonVariationDetail` is built by hand as an `LdValue` tree instead of reusing the typed default object directly.
- Everything else (personas, name targeting, variation → model mapping, SSE event shapes, Yahoo caching) matches the Node.js implementation.

Parent: [../README.md](../README.md) · Spec: [../application.md](../application.md) · Python twin: [../python/README.md](../python/README.md) · Node twin: [../node/README.md](../node/README.md) · Java twin: [../java/README.md](../java/README.md)
