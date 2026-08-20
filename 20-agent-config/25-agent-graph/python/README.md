# 25-agent-graph — Python web

LaunchDarkly **Agent Graphs**: assess → specialist → finalize with Trace.

Port: **8250**

## Run

```bash
# Series venv + keys — see ../../README.md
export LD_SDK_KEY=sdk-...
ollama pull llama3.2:3b

# Provision graph + node configs once
cd ../rest && ./create-all.sh

cd ../python
python 25-agent-graph.py
# → http://127.0.0.1:8250/
```

## What to click

| Button | Stories? | Path |
|--------|----------|------|
| Generate AI Report | Required | assess → report → finalize |
| Identify questions | Required | assess → questions → finalize |
| Identify good & bad | Required | assess → good → finalize (## Good / ## Bad) |
| Tell me a joke | Optional | assess → joke → finalize (+ humor %; higher temp for variety) |

Humor easter egg (code-only): Charlie 25% · Amelia 50% · Toby 90%.

## Scorer tools (Trace)

App-invoked Library tools after the specialist — **do not rewrite** the response:

| Tool key | Scores (0–1) | Trace name example |
|----------|--------------|--------------------|
| `score-question-gap` | `gap`, `ground` | `score-question-gap:0.82` |
| `score-joke-corny` | `corny` | `score-joke-corny:0.91` |

Joke easter egg: corny ≥ 0.80 → suggest lowering humor; ≤ 0.20 → suggest raising.

```bash
cd ../rest && ./create-tools.sh && ./attach-tools.sh
```

## LaunchDarkly

- Graph key: `equity-briefing-graph` (create with `./create-graph.sh` when ready)
- Node configs: `equity-briefing-graph-{assess,report,questions,good,joke,finalize}`
- SDK: `agent_graph` + `agent_config` + `track_tool_call`
- Routing: specialist (and finalize) must match an **outgoing edge** on the evaluated graph; invalid assess→specialist redirects to report when that edge exists

Keywords: **AgentControl** · **Agent graphs** · **Library tools** · **track_tool_call** · **handoffs**

Docs: https://launchdarkly.com/docs/home/agentcontrol/agent-graphs · https://launchdarkly.com/docs/home/agentcontrol/tools
