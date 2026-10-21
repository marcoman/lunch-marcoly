# 25-agent-graph — REST provisioning

LaunchDarkly: **AgentControl** · **Agent graphs** · **Agents** (mode=`agent`)

| Topic | Docs |
|-------|------|
| Agent graphs | https://launchdarkly.com/docs/home/agentcontrol/agent-graphs |
| Create graph API | https://launchdarkly.com/docs/api/ai-configs/post-agent-graph |
| Create AI Config | https://launchdarkly.com/docs/api/agent-control/post-ai-config |

## Keys

| Resource | Key |
|----------|-----|
| Graph | `equity-briefing-graph` |
| Assess | `equity-briefing-graph-assess` |
| Report | `equity-briefing-graph-report` |
| Questions | `equity-briefing-graph-questions` |
| Good | `equity-briefing-graph-good` |
| Joke | `equity-briefing-graph-joke` |
| Finalize | `equity-briefing-graph-finalize` |

## Provision

```bash
export LD_API_ACCESS_TOKEN=api-...
export LD_PROJECT_KEY=lunch-marcoly   # or your project
export LD_ENVIRONMENT_KEY=test

cd 20-agent-config/25-agent-graph/rest
chmod +x *.sh
./create-all.sh
```

Or stepwise: `./create-nodes.sh` then `./create-graph.sh`.

Cleanup: `./delete-graph.sh` (add `--nodes` to remove the six agent configs too).

## Scorer tools

```bash
./create-tools.sh
./attach-tools.sh   # questions ← score-question-gap; joke ← score-joke-corny
```

Scores are decimals in **[0, 1]**. Trace shows the score in the tool name
(`score-question-gap:0.74`). Outcomes are unchanged — teaching visibility only.
