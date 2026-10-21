# 25-agent-graph — Node.js web

LaunchDarkly **Agent Graphs**: assess → specialist → finalize with Trace.

Port **8251**. Requires Node **20+**, `LD_SDK_KEY`, a provisioned agent graph +
node configs, and local Ollama.

Keywords: **AgentControl** · **Agent graphs** · **Agents** · **Library tools** · **trackToolCall** · **handoffs**

| Topic | Docs |
|-------|------|
| Agent graphs | [Agent graphs](https://launchdarkly.com/docs/home/agentcontrol/agent-graphs) |
| Tools | [Tools](https://launchdarkly.com/docs/home/agentcontrol/tools) |
| Node AI SDK | [Node.js AI SDK](https://launchdarkly.com/docs/sdk/ai/node-js) |
| Spec | [../application.md](../application.md) |

## Prerequisites

```bash
nvm use
export LD_SDK_KEY="sdk-..."
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="test"
ollama pull llama3.2:3b

cd ../rest && ./create-all.sh
# Optional: scorer Library tools for Trace
./create-tools.sh && ./attach-tools.sh
```

## Build & run

```bash
cd 20-agent-config/25-agent-graph/node
npm install
npm start
```

Open **http://127.0.0.1:8251/** (Python twin: **8250**).

## What to click

| Button | Specialist | Stories? | Path |
|--------|------------|----------|------|
| Generate AI Report | `report` | Required | assess → report → finalize |
| Identify questions | `questions` | Required | assess → questions → finalize |
| Identify good & bad | `good` | Required | assess → good → finalize (## Good / ## Bad) |
| Tell me a joke | `joke` | Optional | assess → joke → finalize (+ humor %; higher temp for variety) |

Humor easter egg (code-only): Charlie 25% · Amelia 50% · Toby 90%.

## Scorer tools (Trace)

App-invoked Library tools after the specialist — **do not rewrite** the response:

| Tool key | Scores (0–1) | Trace name example |
|----------|--------------|---------------------|
| `score-question-gap` | `gap`, `ground` | `score-question-gap:0.82` |
| `score-joke-corny` | `corny` | `score-joke-corny:0.91` |

Joke easter egg: corny ≥ 0.80 → suggest lowering humor; ≤ 0.20 → suggest raising.

## LaunchDarkly

- Graph key: `equity-briefing-graph`
- Node configs: `equity-briefing-graph-{assess,report,questions,good,joke,finalize}`
- SDK: `aiClient.agentGraph(...)` + `aiClient.agentConfig(...)` + `tracker.trackToolCall(...)`
- Routing: the chosen specialist (and later finalize) must match an **outgoing edge**
  on the evaluated graph — `graph.getNode(key).getEdges()`. Invalid assess→specialist
  handoffs redirect to `report` when that edge exists, else the first valid child.
- Anonymous Amelia evaluates with `anonymous: true` on the context (fallthrough targeting).

## Environment

| Variable | Required | Notes |
|----------|----------|-------|
| `LD_SDK_KEY` | Yes | Server-side SDK key |
| `LD_GRAPH_KEY` | No | Default `equity-briefing-graph` |
| `LD_NODE_ASSESS` / `LD_NODE_REPORT` / `LD_NODE_QUESTIONS` / `LD_NODE_GOOD` / `LD_NODE_JOKE` / `LD_NODE_FINALIZE` | No | Override individual node keys |
| `OLLAMA_HOST` | No | Default `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | No | Default `llama3.2:3b` |
| `JOKE_TEMPERATURE` | No | Default `0.95` |
| `JOKE_CORNY_HIGH` / `JOKE_CORNY_LOW` | No | Defaults `0.80` / `0.20` |
| `PORT` | No | Default `8251` |

Parent: [../README.md](../README.md)
