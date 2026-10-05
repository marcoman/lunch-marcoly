# Flags vs AgentControl — outline

**Status: stub.** This is the outline, not the build spec. Lock keys, copy, and acceptance criteria here before writing the app.

Human overview: [README.md](README.md).  
Series setup: [20-agent-config README](../README.md).  
Working completion-config lesson: [21-agent-completion-config](../21-agent-completion-config/).

## Goal

Show the same three briefing fields supplied two ways customers already ship, and one way AgentControl ships them.

1. **Flag conditional.** A feature flag variation chooses a branch. The branch hardcodes a model, a temperature, or a prompt.
2. **JSON flag.** One JSON variation holds `model`, `temperature`, and `prompt` in the flag body. The app parses that body.
3. **AgentControl.** A completion config variation holds the model, the parameter, and the messages. The app evaluates the config and uses what came back.

Same UI as `21`: stories, persona, Generate AI Report. The new surface is the source control and the lab rail.

Keywords: **feature flags** · **JSON variations** · **AgentControl** · **completion config** · **AI SDK**

| Topic | Docs |
|-------|------|
| Flag types | [Flag types](https://launchdarkly.com/docs/sdk/features/flag-types) |
| AgentControl | [AgentControl](https://launchdarkly.com/docs/home/agentcontrol) |
| Completion config | [Quickstart for AgentControl](https://launchdarkly.com/docs/home/agentcontrol/quickstart) |
| AI SDK | [AI SDKs](https://launchdarkly.com/docs/sdk/ai) |

## Screen

One page. Source control:

| Control | LaunchDarkly surface |
|---------|----------------------|
| Flag conditional | String or boolean flag. App `if` picks the baked-in model, temperature, or prompt |
| JSON flag | One multivariate flag, JSON variation |
| AgentControl | Completion config (`model`, parameter, system and user messages) |

Lab rail, always visible after a fetch:

| Field | Shown for every source |
|-------|------------------------|
| Model | The id that will be called |
| Parameter | Temperature |
| Prompt | The system prompt text, truncated in the rail |
| Surface | `flag-conditional`, `json-flag`, or `completion-config` |

Generate uses whichever source is selected. Flipping the control and generating again should change the rail without a redeploy.

## Scope

- Web twins only: Python **:8260**, Node **:8261**, Java **:8262**, .NET **:8263**.
- Python first.
- Dedicated keys. `21` keeps `equity-briefing-completion`.
- Proposed keys, to confirm at build time: `configure-briefing-branch` (conditional), `configure-briefing-json` (JSON body), `equity-briefing-flag-compare` (completion config).

## Leave in place

- [21-agent-completion-config](../21-agent-completion-config/) — the completion-config lesson, including its Go console.
- [40-dont-do-this](../../40-dont-do-this/) — SDK misuse labs. This example is an AgentControl comparison.
- [99-use-cases](../../99-use-cases/) — grid navigator patterns.
- Series portal stays on 21–25 until this app exists.

## When implementing

1. Fill this file out to the level of [21's application.md](../21-agent-completion-config/application.md): exact variations, context, and acceptance criteria.
2. REST provisioning for the two flags and the completion config.
3. Python web, then the other web twins.
4. Rail must name the surface. A green briefing with no source label fails the lesson.
