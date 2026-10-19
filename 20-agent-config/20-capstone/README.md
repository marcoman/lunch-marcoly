# 20-capstone

**Status: Node app built on port 8291. Not in the series portal.**

One equity briefing that composes [21](../21-agent-completion-config/) through [25](../25-agent-graph/). Those folders stay the single-idea lessons. This app is where they meet. [26](../26-flags-vs-agent-control/) stays the flag comparison.

The graph is assess → specialist → finalize. There is no joke specialist. Pig Latin, ROT13, and a joke tagline are checkboxes, none checked by default. The app runs the checked tools after the specialist and before finalize, in that order. The model cannot skip them. Judges score the specialist draft, and thumbs record that same draft. The response panel shows the text after tools and finalize.

Node web on **8291**. English and Spanish live here, and only here. The series portal stays on `21`–`26`.

Spec: [application.md](application.md).

Keywords: **AgentControl** · **agent graphs** · **Library tools** · **judges** · **tracked completion**

| Topic | Docs |
|-------|------|
| Agent graphs | [Agent graphs](https://launchdarkly.com/docs/home/agentcontrol/agent-graphs) |
| Tools | [Tools](https://launchdarkly.com/docs/home/agentcontrol/tools) |
| Judges | [Judges](https://launchdarkly.com/docs/home/agentcontrol/judges) |
| AgentControl | [AgentControl](https://launchdarkly.com/docs/home/agentcontrol) |

## What you will see

Generate runs the graph. The tool row adds each checked name to the on-screen graph immediately, and the trace shows that step when it runs. The rail shows the judge scores and the feedback event for the specialist draft.

A locale control chooses English or Spanish for the chrome and for the prompts the config serves. Persona names stay `Charlie`, `Amelia`, and `Toby`.

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| Node web | `node/` | Built. Port **8291** |
