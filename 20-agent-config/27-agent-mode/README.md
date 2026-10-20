# 27-agent-mode

**Status: stub — not implemented yet.**

One **agent mode** config: a single **instructions** value, then a generate.
No graph, no library tools, no judges.

[21-agent-completion-config](../21-agent-completion-config/) stays **completion
mode** (system message, user message, model). This lesson does not roll into
[20-capstone](../20-capstone/).

Keywords: **AgentControl** · **agent mode** · **instructions** · **AI SDK**

Docs: [Agents](https://launchdarkly.com/docs/home/agentcontrol/agents)

## Intended aha

Agent mode is one instructions block, not the completion-mode message list.
The screen shows the instructions that were served and the reply. Changing the
variation changes those instructions without a redeploy.

## Direction

- One config, agent mode only.
- A few variations are enough (a cautious voice and a short voice).
- Do not add tools, judges, or a graph to make it look like the capstone.
- Not in the series portal until the app exists. Intended ports **:8270–:8273**
  (the capstone left these free).

## When implementing

1. `application.md` with a new config key. Do not reuse
   `equity-briefing-completion` or the capstone graph.
2. Python web first, on the equity briefing surface from
   [01-reference-agent](../../01-reference-agent/).
3. The rail shows mode `agent` and the instructions text that was served.

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| *(none yet)* | — | Stub |
