# 20-capstone

**Status: stub — not implemented yet.**

One equity briefing that composes the AgentControl lessons from [21](../21-agent-completion-config/) through [25](../25-agent-graph/). Those folders stay the single-idea lessons. This app is where they meet.

The graph is the spine. Tools run on the report node. A judge gates that draft. Feedback is recorded on the finished response. Later numbered lessons (`27`, `28`, …) keep their own folders, and their behavior rolls into this app. The capstone does not take their number.

Node web only. English and Spanish live here when it is built, and only here. Not in the series portal.

Outline: [application.md](application.md).

Keywords: **AgentControl** · **agent graphs** · **tools** · **judges** · **tracked completion**

| Topic | Docs |
|-------|------|
| Agent graphs | [Agent graphs](https://launchdarkly.com/docs/home/agentcontrol/agent-graphs) |
| Tools | [Tools](https://launchdarkly.com/docs/home/agentcontrol/tools) |
| Judges | [Judges](https://launchdarkly.com/docs/home/agentcontrol/judges) |
| AgentControl | [AgentControl](https://launchdarkly.com/docs/home/agentcontrol) |

## What you will see

One briefing screen. Generate runs the graph. The trace shows the nodes. The rail shows the tool call, the judge scores, and the feedback event.

A locale control chooses English or Spanish for the chrome and for the prompts the config serves. Persona names stay the targeting keys they already are.

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| *(none yet)* | — | Stub. Node web only. Port chosen at build time |
