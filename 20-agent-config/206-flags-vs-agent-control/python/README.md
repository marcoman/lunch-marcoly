# Python web

One **Generate AI Report** runs AgentControl, Separate flags, and JSON flag on the same headlines. Each column streams its draft and keeps its own LaunchDarkly evaluation for the drawer.

Keywords: **feature flags** · **JSON variations** · **AgentControl** · **completion config** · **judges**

| Topic | Docs |
|-------|------|
| Python AI SDK | [Python AI SDK reference](https://launchdarkly.com/docs/sdk/ai/python) |
| Judges | [Judges](https://launchdarkly.com/docs/home/agentcontrol/judges) |
| Provision | [../rest/README.md](../rest/README.md) |

## Run

```bash
export LD_SDK_KEY="sdk-..."
# optional: export LD_AGENT_CONFIG_KEY="equity-briefing-flag-compare"
# optional: export LD_JUDGE_KEY="equity-briefing-flag-compare-judge"
# optional: export ANTHROPIC_API_KEY="sk-ant-..."  # enables Claude Sonnet in the Model override
ollama pull llama3.2:3b    # Charlie, and the judge
ollama pull llama3.2:1b    # Toby
cd 20-agent-config/26-flags-vs-agent-control/python
python 26-flags-vs-agent-control.py
```

Open **http://127.0.0.1:8260/**.

Provision first: [../rest/create-original.sh](../rest/create-original.sh), [../rest/attach-repair-tool.sh](../rest/attach-repair-tool.sh), and [../rest/create-flags.sh](../rest/create-flags.sh).

## What you should see

1. **Get Stories**. The user starts as **Thoughtless Toby**.
2. **Generate AI Report**. AgentControl runs, then Separate flags, then JSON flag.
3. Toby’s draft should fail the guardrail. AgentControl then runs `reduce-briefing-uncertainty` and shows that text under the draft. The flag columns stay on the failed draft.
4. **LD details** on AgentControl lists the attached tool. The flag tabs do not.
5. **Previous/Next User** switches to **Conservative Charlie**, whose draft should pass.
6. The **Model override** above the persona panel can force every source to call `llama3.2:1b`, `llama3.2:3b`, or Claude Sonnet for one Generate, independent of what each source served — useful for comparing models within one outcome. It needs `ANTHROPIC_API_KEY` for Sonnet. It does not flip Toby's guardrail: his prompt fails under any model.

## Files

| File | Role |
|------|------|
| `26-flags-vs-agent-control.py` | HTTP + SSE on **:8260** |
| `agent_core.py` | `completion_config`, then `create_judge` / `evaluate` |
| `index.html` | Three response columns and the LD details drawer |
| `yahoo_news.py` | Headlines. Cache is the shared `20-agent-config/stories/` file |
