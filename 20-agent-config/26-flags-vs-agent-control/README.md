# 26-flags-vs-agent-control

**Status: stub — not implemented yet.**

Same equity briefing as [21-agent-completion-config](../21-agent-completion-config/). The lesson is **where** the model, one parameter, and the prompt come from.

Customers often keep that trio in ordinary feature flags: a conditional that picks a branch, or a JSON variation that carries the values. This example puts that pattern on one side of the screen and an AgentControl **completion config** on the other.

Web only. Python first, then Node, Java, and .NET. No console ports. Not in the series portal until it ships.

Outline: [application.md](application.md).

Keywords: **feature flags** · **boolean variations** · **JSON variations** · **AgentControl** · **completion config**

| Topic | Docs |
|-------|------|
| Flag types (string, JSON) | [Flag types](https://launchdarkly.com/docs/sdk/features/flag-types) |
| AgentControl | [AgentControl](https://launchdarkly.com/docs/home/agentcontrol) |
| Completion config | [Quickstart for AgentControl](https://launchdarkly.com/docs/home/agentcontrol/quickstart) |
| AI SDK | [AI SDKs](https://launchdarkly.com/docs/sdk/ai) |

## What you will see

One briefing screen. A source control picks the path. The lab rail prints the resolved **model**, **parameter** (temperature), and **prompt**, and names which LaunchDarkly surface supplied them.

| Source | What the app does |
|--------|-------------------|
| Flag conditional | Evaluates a flag, then an `if` selects the model, temperature, or prompt baked into that branch |
| JSON flag | Evaluates one JSON variation and reads model, temperature, and prompt out of the body |
| AgentControl | Fetches a completion config. The variation already holds model, parameter, and messages |

Generate still streams a briefing. The aha is the rail, not a new product screen.

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| *(none yet)* | — | Stub. Planned web ports **:8260–:8263** |
