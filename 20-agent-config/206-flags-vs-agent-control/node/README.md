# Node web

Same three-column briefing as [Python](../python/). **Generate AI Report** runs AgentControl, Separate flags, and JSON flag.

Completion uses AI SDK `completionConfig`, which substitutes `{{ stories }}`. Flags use `variationDetail`. The guardrail uses `judgeConfig`, then a local Ollama JSON score. Python uses `create_judge`; this port stays on AI SDK 2.x.

Keywords: **feature flags** · **JSON variations** · **AgentControl** · **completion config** · **judges** · **Library tools**

| Topic | Docs |
|-------|------|
| Node AI SDK | [Node.js AI SDK](https://launchdarkly.com/docs/sdk/ai/node-js) |
| Flag types | [Flag types](https://launchdarkly.com/docs/sdk/features/flag-types) |
| Judges | [Judges](https://launchdarkly.com/docs/home/agentcontrol/judges) |
| Tools | [Tools](https://launchdarkly.com/docs/home/agentcontrol/tools) |

## Run

```bash
export LD_SDK_KEY="sdk-..."
cd 20-agent-config/26-flags-vs-agent-control/node
npm install
npm start
```

Open **http://127.0.0.1:8261/**. Provision first with [../rest/README.md](../rest/README.md).

Port **8261**. Python is **8260**. Java is **8262**.
