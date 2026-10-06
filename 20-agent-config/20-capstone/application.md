# AgentControl capstone — outline

**Status: stub.** This is the outline, not the build spec. Lock keys, the graph path, and the locale variations here before writing the app.

Human overview: [README.md](README.md).  
Series setup: [20-agent-config README](../README.md).

## Goal

One Node briefing where the pieces taught separately in `21`–`25` run as one flow.

1. **Graph** ([25](../25-agent-graph/)): assess → specialist → finalize. The trace shows the path.
2. **Tools** ([23](../23-agent-tools/)): the report specialist can call a library tool.
3. **Judges** ([24](../24-agent-judges/)): a judge scores the report draft before finalize.
4. **Feedback** ([22](../22-config-outside-code/)): the finished response records a metric.

`21` is the completion-config base those four sit on. This app does not replace that lesson.

The path may grow. A later `27` or `28` stays its own numbered folder. When that lesson is accepted, its node, tool, judge, or feedback point is added here. Flow variations belong in this outline, not in a second capstone.

Keywords: **AgentControl** · **agent graphs** · **tools** · **judges** · **tracked completion** · **locale**

| Topic | Docs |
|-------|------|
| Agent graphs | [Agent graphs](https://launchdarkly.com/docs/home/agentcontrol/agent-graphs) |
| Tools | [Tools](https://launchdarkly.com/docs/home/agentcontrol/tools) |
| Judges | [Judges](https://launchdarkly.com/docs/home/agentcontrol/judges) |
| AgentControl | [AgentControl](https://launchdarkly.com/docs/home/agentcontrol) |
| AI SDK | [AI SDKs](https://launchdarkly.com/docs/sdk/ai) |

## Screen

One page, Node only.

| Surface | What the learner sees |
|---------|------------------------|
| Generate | One action runs the graph |
| Trace | Node path for that run |
| Rail | Tool call, judge scores, feedback event |
| Locale | English or Spanish. Chrome and served prompts follow the control |

Persona context keys stay English (`Charlie`, `Amelia`, `Toby`). The locale control does not rename them.

## Locale

English and Spanish are in scope for this app only. The rest of the catalog stays English.

- UI strings live in this app.
- Spanish system and user prompts are completion-config variations targeted by a `locale` attribute (`en` / `es`).
- Headlines may stay English on the first cut. The prompt tells the model which language to write.

## Keys

Dedicated keys, chosen at build time. `21`–`25` keep the configs they already use, including `equity-briefing-completion` and `equity-briefing-graph`.

## Leave in place

- [21](../21-agent-completion-config/) through [25](../25-agent-graph/) — single-idea lessons, all languages they already have.
- [26-flags-vs-agent-control](../26-flags-vs-agent-control/) — the flag-versus-config comparison.
- Series portal stays on `21`–`25` until this app exists.
- Number **27** stays free for the next single-idea lesson.

## When implementing

1. Fill this file out to the level of [25's application.md](../25-agent-graph/application.md): graph nodes, which node has tools, which node is judged, where feedback is tracked, and the `en` / `es` variations.
2. REST provisioning for this app's configs only.
3. Node web. Port chosen then.
4. A run with no trace, no judge score, and no feedback event fails the lesson.
