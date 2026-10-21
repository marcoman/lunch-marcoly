# 20-capstone REST

Creates only the capstone keys. It does not change `equity-briefing-completion` or `equity-briefing-graph`.

Keywords: **AgentControl** · **agent graphs** · **Library tools** · **judges** · **contexts**

| Topic | Docs |
|-------|------|
| Agent graphs | [Agent graphs](https://launchdarkly.com/docs/home/agentcontrol/agent-graphs) |
| Tools | [Tools](https://launchdarkly.com/docs/home/agentcontrol/tools) |
| Judges | [Judges](https://launchdarkly.com/docs/home/agentcontrol/judges) |
| Create an AI Config | [POST AI Config](https://launchdarkly.com/docs/api/agent-control/post-ai-config) |
| Targeting | [Patch AI Config targeting](https://launchdarkly.com/docs/api/agent-control/patch-ai-config-targeting) |

## What it creates

| Resource | Key |
|----------|-----|
| Graph | `equity-briefing-capstone` |
| Nodes | `equity-briefing-capstone-{assess,report,questions,good,finalize}` |
| Tools | `pig-latin`, `rot13`, `joke-tagline` |
| Judges | `equity-briefing-capstone-source-fidelity`, `equity-briefing-capstone-recommendation-discipline` |

Report variations: `baseline-analyst` (Amelia fallthrough), `concise-skeptic` (Charlie), `reckless-hype` (Toby, `llama3.2:1b`).

Spanish variations (`spanish`) exist on assess, questions, good, and finalize. A `locale` = `es` rule serves them. The report node keeps the name rules. Spanish there comes from `{{ locale }}` inside each persona variation, so the name rules stay intact.

## Run

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="your-project"
export LD_ENVIRONMENT_KEY="test"
cd 20-agent-config/20-capstone/rest
./create-all.sh
```

`create-all.sh` order: tools, nodes (including both targeting scripts when `LD_ENVIRONMENT_KEY` is set), graph, judges.

Delete the graph with `./delete-graph.sh`. Add `--nodes` to also delete the node configs and judges, and `--tools` to delete the three Library tools.
