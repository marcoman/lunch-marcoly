# 26-flags-vs-agent-control

**Status: Python app on :8260.** AgentControl, Separate flags, and JSON flag run side by side. Node, Java, and .NET are not started. Not in the series portal.

The [21](../21-agent-completion-config/) briefing, with a source control. The same four settings come from an AgentControl completion config, from four feature flags, or from one JSON flag.

Settings: **model**, **system prompt**, **user prompt**, and **whether a judge scores the draft**. The judge reports a pass or fail on the screen. It does not rewrite the draft. That rewrite stays in [24](../24-agent-judges/).

Two personas: **Conservative Charlie** and **Thoughtless Toby**. One targeting rule plus a fallthrough. The flag sources repeat that rule. The completion config holds it once.

Outline: [application.md](application.md).

Web only. Python first, then Node, Java, and .NET. Not in the series portal until it ships.

## Setup

Do this once before Generate. Series SDK key, Ollama, and news keys: [20-agent-config README](../README.md).

**AgentControl.** [`rest/create-original.sh`](rest/create-original.sh) creates the completion config and the judge. The Python app calls these two. It does not create feature flags.

| Resource | Key |
|----------|-----|
| Completion config | `equity-briefing-flag-compare` |
| Judge | `equity-briefing-flag-compare-judge` |

Charlie’s name rule serves `concise-skeptic` (`llama3.2:3b`). Toby is the fallthrough, `reckless-hype` (`llama3.2:1b`). The screen shows Toby. [`attach-repair-tool.sh`](rest/attach-repair-tool.sh) attaches `reduce-briefing-uncertainty` to `reckless-hype` only. The app runs that tool after a failed judge. The flag sources have no tool to run.

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="test"
cd 20-agent-config/26-flags-vs-agent-control/rest
./create-original.sh
./attach-repair-tool.sh

ollama pull llama3.2:3b
ollama pull llama3.2:1b
```

Details, including delete: [rest/README.md](rest/README.md).

**Flags.** [`rest/create-flags.sh`](rest/create-flags.sh) creates the four separate flags and the JSON flag. Charlie’s name rule and Toby’s fallthrough are copied onto each one. `enable-briefing-judge` is on for both personas; turn that variation off in LaunchDarkly to leave the draft undecorated.

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="test"
cd 20-agent-config/26-flags-vs-agent-control/rest
./create-flags.sh
```

| Source | Keys |
|--------|------|
| Separate flags | `configure-briefing-model`, `configure-briefing-system-prompt`, `configure-briefing-user-prompt`, `enable-briefing-judge` |
| JSON flag | `configure-briefing-json` |

Restart the Python app after either script so it picks up the new code. The server does not reload files on its own.

**Run the app** after the script succeeds and `LD_SDK_KEY` is set for that same environment:

```bash
cd 20-agent-config/26-flags-vs-agent-control/python
python 26-flags-vs-agent-control.py
```

Open **http://127.0.0.1:8260/**. Use the repo virtualenv (`../../.venv/bin/python`) if `python` cannot import `ldai`.

Keywords: **feature flags** · **JSON variations** · **AgentControl** · **completion config** · **judges**

| Topic | Docs |
|-------|------|
| Flag types | [Flag types](https://launchdarkly.com/docs/sdk/features/flag-types) |
| AgentControl | [AgentControl](https://launchdarkly.com/docs/home/agentcontrol) |
| Judges | [Judges](https://launchdarkly.com/docs/home/agentcontrol/judges) |
| Library tools | [Tools](https://launchdarkly.com/docs/home/agentcontrol/tools) |
| AI SDK | [AI SDKs](https://launchdarkly.com/docs/sdk/ai) |

## What you will see

One **Generate AI Report** runs all three sources on the same headlines and the same user. The drafts stay side by side. **LD details** on a column opens that evaluation; the drawer switches among the three without another run.

| Source | LaunchDarkly calls inside that column |
|--------|--------------------------------------|
| AgentControl | One completion config (model + both prompts), one judge config, and on a guardrail fail the repair tool |
| Separate flags | Four flags: model, system prompt, user prompt, judge on/off. No tool |
| JSON flag | One JSON body with those four fields. No tool |

Toby’s draft should fail the guardrail. AgentControl then shows the tool output under the draft. The other two columns stay on the failed draft.

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| Python web | [python/](python/) | **:8260**. AgentControl, Separate flags, and JSON flag |
| Node, Java, .NET | — | Not started |
