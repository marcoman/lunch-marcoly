# 20-capstone-1 — Python web

Same capstone as the Node app: assess → specialist → judges → checked tools → finalize.

Port **8290**. Requires the series virtualenv, `LD_SDK_KEY`, the capstone graph and node configs, and local Ollama.

Keywords: **AgentControl** · **agent graphs** · **Library tools** · **judges** · **track_tool_call** · **feedback** · **locale**

| Topic | Docs |
|-------|------|
| Agent graphs | [Agent graphs](https://launchdarkly.com/docs/home/agentcontrol/agent-graphs) |
| Tools | [Tools](https://launchdarkly.com/docs/home/agentcontrol/tools) |
| Judges | [Judges](https://launchdarkly.com/docs/home/agentcontrol/judges) |
| AI metrics / feedback | [Tracking AI metrics](https://launchdarkly.com/docs/sdk/features/ai-metrics) |
| Python AI SDK | [Python AI SDK](https://launchdarkly.com/docs/sdk/ai/python) |
| Spec | [../application.md](../application.md) |

## Run

```bash
export LD_SDK_KEY="sdk-..."
ollama pull llama3.2:3b

cd 20-agent-config/20-capstone-1/python
python 20-capstone-1.py
```

Open **http://127.0.0.1:8290/**.

The screen matches the Node app, including the ROT13-back checkbox, the trace, and the LD details drawer. Provision the graph once from `../rest`. This app is not a portal tab.

## LaunchDarkly

The insertion points are in `agent_core.py`:

- `LDAIClient.agent_graph` then `agent_config` per node
- `judge_config` on the specialist draft, before tools
- `tracker.track_tool_call` for each checked tool, on the specialist tracker
- `create_tracker` + `track_feedback` from that specialist resumption token
