# Reference Agent Application Specification

This document defines the behavior of the **01-reference-agent** application — a single-screen agent demo used as the baseline for LLM / persona examples.

Repository layout and README format are in [project.md](../project.md). Later variations may add LaunchDarkly AgentControl / AI Config; this reference uses **config and environment variables only**.

## Overview

A **single-screen** application (no login):

1. Select a **persona** from a fixed list (Previous / Next)
2. Show the shared **canned user input**
3. **Generate** an AI response (automatic on persona change; Refresh re-runs)
4. Stream the response into the UI
5. Show **provider**, **model**, and **LLM metrics**
6. Show errors and safety messages in a **status** panel

All implementations must produce equivalent behavior. Differences are limited to platform-appropriate presentation (browser vs terminal).

## Personas

Fixed ordered list (wraps on Previous / Next):

| Order | Display name | Profile type |
|-------|--------------|--------------|
| 0 | Conservative Charlie | `conservative` |
| 1 | Neutral Nancy | `neutral` |
| 2 | Thoughtless Toby | `risk-taker` |

- The **canned user prompt is shared** across personas.
- Profile type drives response style (system / instruction text), not a different user message in v1.
- Selecting a persona (including landing on the first persona at load) **starts generation automatically**.

## Shared canned input (v1)

One shared user message for all personas (placeholder until product copy is finalized):

```text
Should we launch the new feature to all customers this week?
```

Later versions may add multiple canned inputs; v1 has exactly one.

## Controls

| Control | Behavior |
|---------|----------|
| **Previous** | Move to the previous persona (wrap). Show that persona’s name. Auto-generate. |
| **Next** | Move to the next persona (wrap). Show that persona’s name. Auto-generate. |
| **Refresh** | Re-run generation for the **current** persona and the same canned input. |

While a generation is in flight, controls should be disabled or ignore duplicate clicks until the stream completes or fails.

## Primary presentation

| Region | Content |
|--------|---------|
| Persona | Current display name (and optionally profile type) |
| Input | The shared canned user message |
| Response | Streamed model output (append tokens as they arrive) |
| Provider / model | e.g. `stub` / `default-no-llm`, or `ollama` / `llama3.1:8b` |
| Metrics | Industry-standard LLM metrics (see below) |
| Status | Idle, generating, success, or error / safety messages |

## LLM modes

Provider is selected by environment (not LaunchDarkly in this reference).

| Mode (`AGENT_LLM_MODE`) | Behavior |
|---------------------------|----------|
| `stub` (default) | No network LLM call. Streams a boilerplate response labeled for UI testing (`default-no-llm`). |
| `ollama` | Call a local Ollama server. |
| `bedrock` | Call AWS Bedrock (expected first cloud provider). |
| `anthropic` | Call Anthropic Messages API (optional second cloud provider). |

### Stub behavior

- Provider display: `stub`
- Model display: `default-no-llm`
- Response: short boilerplate that includes the persona name and profile type so UI wiring is obvious
- Metrics: populated with plausible stub values (tokens may be estimated from character counts)
- Streaming: emit the boilerplate in small chunks so the UI path matches real providers

### Refresh semantics

Refresh (and persona change) call the model again with the **same** inputs. Responses should be similar for deterministic stub mode; live models may vary.

## Streaming

- Responses **stream** into the response region (SSE or equivalent).
- Metrics that are only known at the end (e.g. total tokens, total latency) update when the stream finishes.
- Time-to-first-token may update when the first chunk arrives.

## Metrics (v1)

Show at least:

| Metric | Meaning |
|--------|---------|
| `latency_ms` | End-to-end generation time |
| `ttft_ms` | Time to first token (optional until first chunk) |
| `prompt_tokens` | Input token count when available |
| `completion_tokens` | Output token count when available |
| `total_tokens` | Sum when available |
| `finish_reason` | e.g. `stop`, `length`, `error` |

Unavailable values render as `—`.

## Status / errors / safety

The status panel shows:

- Idle / Generating / Complete
- Provider errors (auth, network, timeout, rate limit)
- Safety or content-policy messages from the provider when present
- Clear, user-visible text (no silent failure)

## Configuration (environment variables)

### Mode and display

| Variable | Default | Purpose |
|----------|---------|---------|
| `AGENT_LLM_MODE` | `stub` | `stub` \| `ollama` \| `bedrock` \| `anthropic` |
| `AGENT_LLM_MODEL` | *(mode-specific)* | Override model id / name when applicable |

### Ollama

| Variable | Default | Purpose |
|----------|---------|---------|
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama base URL |
| `OLLAMA_MODEL` | `llama3.1:8b` | Model tag (7B/8B/14B-class tags are fine) |

### AWS Bedrock

Use standard AWS credential env vars:

| Variable | Purpose |
|----------|---------|
| `AWS_ACCESS_KEY_ID` | Access key |
| `AWS_SECRET_ACCESS_KEY` | Secret key |
| `AWS_SESSION_TOKEN` | Optional session token |
| `AWS_REGION` or `AWS_DEFAULT_REGION` | Region (e.g. `us-east-1`) |
| `AGENT_BEDROCK_MODEL_ID` | Bedrock model id |

### Anthropic

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | API key |
| `ANTHROPIC_MODEL` | Model id (optional override) |

## Out of scope (this reference)

- Login / multi-screen flows
- LaunchDarkly AgentControl / AI Config (deferred to later examples)
- C++ implementation (optional; may be omitted)
- Multiple canned inputs (deferred)

## Language matrix

Same conventions as [00-reference-code](../00-reference-code/):

| Language | Planned |
|----------|---------|
| Python web | First |
| Python console | Second |
| Node.js web / console | Later |
| Java web / console | Later |
| Go console | Later |
| Rust console | Later (HTTP/REST to providers) |
| C++ | Likely omitted |

## Acceptance criteria

1. App loads to a single screen with persona **Conservative Charlie** and auto-starts generation
2. Previous / Next cycle Charlie → Nancy → Toby → Charlie (and reverse)
3. Default `AGENT_LLM_MODE=stub` works with **no API keys**
4. Refresh re-runs generation for the current persona
5. Response streams into the response region
6. Provider and model are visible
7. Metrics panel shows the v1 fields (or `—`)
8. Errors appear in the status panel
9. Shared canned input is identical for all personas; profile type changes response style

## Related

- [00-reference-code/application.md](../00-reference-code/application.md) — grid navigator reference (no LLM)
- Later: LaunchDarkly AgentControl / AI Config variations of this agent UI
