# 20-capstone-1 — Node.js web

One equity briefing that walks an Agent Graph, then forces the checked tools, then finalizes.

Port **8291**. Requires Node **20+**, `LD_SDK_KEY`, the capstone graph and node configs, and local Ollama.

Keywords: **AgentControl** · **agent graphs** · **Library tools** · **judges** · **trackToolCall** · **feedback** · **locale**

| Topic | Docs |
|-------|------|
| Agent graphs | [Agent graphs](https://launchdarkly.com/docs/home/agentcontrol/agent-graphs) |
| Tools | [Tools](https://launchdarkly.com/docs/home/agentcontrol/tools) |
| Judges | [Judges](https://launchdarkly.com/docs/home/agentcontrol/judges) |
| AI metrics / feedback | [Tracking AI metrics](https://launchdarkly.com/docs/sdk/features/ai-metrics) |
| Node AI SDK | [Node.js AI SDK](https://launchdarkly.com/docs/sdk/ai/node-js) |
| Spec | [../application.md](../application.md) |

## Prerequisites

```bash
export LD_SDK_KEY="sdk-..."
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="your-project"
export LD_ENVIRONMENT_KEY="test"
ollama pull llama3.2:3b
ollama pull llama3.2:1b

cd ../rest && ./create-all.sh
```

## Build and run

```bash
cd 20-agent-config/20-capstone-1/node
npm install
npm start
```

Open **http://127.0.0.1:8291/**.

## What to click

| Control | What runs |
|---------|-----------|
| Generate AI Report | assess → report → judges → checked tools → finalize |
| Identify questions | assess → questions → judges → checked tools → finalize |
| Identify good & bad | assess → good → judges → checked tools → finalize |
| Tool checkboxes | Pig Latin, then ROT13, then joke tagline. None checked by default |
| ROT13 back | Shown beside the final response only after a run that used ROT13. Checking it applies ROT13 again to the whole response, including the tagline |
| Locale | English or Spanish. Sent as context attribute `locale` |
| Thumbs | Feedback on the specialist draft, using that run's resumption token |
| Agent graph | Box-and-edge topology matching the LaunchDarkly graph; the active path lights as it runs |
| Trace | Fixed-width, color-coded console for nodes, judges, tools, finalize, and feedback |
| Run status | Judge score cards plus draft feedback status |
| LD details | Sent / Received / About drawer for the latest graph evaluation |

Humor line (code-only, when the joke tagline runs): Charlie 25% · Amelia 50% · Toby 90%.

## Story persistence

Successful headline pairs are written to the shared
`20-agent-config/stories/stories_cache.json` file. `/api/bootstrap` restores the
last usable pair into the page, so restarting Node does not require another live
news request. The story status identifies a restored pair as `disk cache`.

## LaunchDarkly

The insertion points are in `agentCore.js`:

- `aiClient.agentGraph` then `agentConfig` per node
- `judgeConfig` on the specialist draft, before tools
- `tracker.trackToolCall` for each checked tool, on the specialist tracker
- `tracker.trackFeedback` rebuilt from that specialist resumption token

Graph edges stay assess → specialist → finalize. Tool names on the screen are the teaching diagram. They are not extra graph nodes.

A run with no trace, no judge score, and no feedback event fails the lesson. Unchecked tools can still pass. A checked tool missing from the trace fails the lesson.

## Environment

| Variable | Required | Notes |
|----------|----------|-------|
| `LD_SDK_KEY` | Yes | Server-side SDK key |
| `PORT` | No | Default `8291` |
| `LD_GRAPH_KEY` | No | Default `equity-briefing-capstone` |
| `LD_NODE_ASSESS` / `LD_NODE_REPORT` / `LD_NODE_QUESTIONS` / `LD_NODE_GOOD` / `LD_NODE_FINALIZE` | No | Override a node key |
| `LD_JUDGE_FIDELITY_KEY` / `LD_JUDGE_DISCIPLINE_KEY` | No | Override a judge key |
| `OLLAMA_HOST` | No | Default `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | No | Default `llama3.2:3b` |
| `JUDGE_PASS_THRESHOLD` | No | Default `0.65` |
