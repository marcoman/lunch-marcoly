# REST — Original variation

Provisions the AgentControl side of [26-flags-vs-agent-control](../README.md). Separate flags and the JSON flag are not in this script.

| Resource | Key | Role |
|----------|-----|------|
| Completion config | `equity-briefing-flag-compare` | Model + system prompt + user prompt. Charlie name rule → `concise-skeptic` (`llama3.2:3b`). Fallthrough → `reckless-hype` (`llama3.2:1b`, Toby) |
| Judge | `equity-briefing-flag-compare-judge` | Scores the draft. Does not rewrite |
| Library tool | `reduce-briefing-uncertainty` | Attached to `reckless-hype` only. The app runs it after a failed score |

Keywords: **AgentControl** · **completion config** · **judges**

Docs: [Quickstart for AgentControl](https://launchdarkly.com/docs/home/agentcontrol/quickstart) · [Judges](https://launchdarkly.com/docs/home/agentcontrol/judges)

`21` keeps `equity-briefing-completion`. `24` keeps its judge keys.

AgentControl:

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="test"
cd 20-agent-config/26-flags-vs-agent-control/rest
./create-original.sh
./attach-repair-tool.sh
```

Flags (four separate flags and one JSON flag):

```bash
./create-flags.sh
```

`./delete-config.sh` removes the completion config. Pass the judge key to delete that too: `./delete-config.sh equity-briefing-flag-compare-judge`.
