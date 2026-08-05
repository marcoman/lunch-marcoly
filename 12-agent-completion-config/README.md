# 12-agent-completion-config

LaunchDarkly **AgentControl** for the equity briefing agent: serve **model**, **system prompt**, and **user prompt** from an AgentControl **completion config** at runtime—without redeploying.

## What this demonstrates

[01-reference-agent](../01-reference-agent/) loads the system prompt from a file and picks the model from `AGENT_LLM_MODE` / env. This example keeps the **same UI and news → generate flow**, but replaces those hardcoded sources with LaunchDarkly.

| At generate time | 01-reference-agent | This example (`12`) |
|------------------|--------------------|---------------------|
| Model | Env / mode override | AgentControl config variation |
| System prompt | `prompts/system_prompt.txt` | AgentControl **system** message |
| User prompt | Built in code from Yahoo headlines | AgentControl **user** message (with runtime variables / app-supplied content as specified) |

Keywords: **AgentControl** · **completion config** · **completion mode** · **config variations** · **model configuration** · **system/user messages** · **AI SDK**

## LaunchDarkly documentation

| Topic | Docs |
|-------|------|
| AgentControl overview | [AgentControl](https://launchdarkly.com/docs/home/agentcontrol) |
| Quickstart (completion mode) | [Quickstart for AgentControl](https://launchdarkly.com/docs/home/agentcontrol/quickstart) |
| Config outside of code | [Managing AI model configuration outside of code](https://launchdarkly.com/docs/guides/agentcontrol/config-outside-code-nodejs) |
| Best practices | [Building with AgentControl configs](https://launchdarkly.com/docs/guides/agentcontrol/best-practices) |

Full behavior, config key, variations, and acceptance criteria: [application.md](application.md).

## Prerequisites

- A LaunchDarkly account with a project and environment
- Access to create **AgentControl** configs
- `LD_SDK_KEY` (and AI SDK credentials as required by the language guide)
- Optional: Ollama / Bedrock / provider keys matching the model named in the config

```bash
export LD_PROJECT_KEY="default"
export LD_ENVIRONMENT_KEY="test"
export LD_SDK_KEY="sdk-..."
```

## Relationship to 01-reference-agent

```text
01-reference-agent          12-agent-completion-config
─────────────────────       ──────────────────────────
system_prompt.txt    →      AgentControl system message
AGENT_LLM_MODE       →      AgentControl model (+ provider)
in-code user prompt  →      AgentControl user message
Yahoo + UI chrome    →      unchanged product shape
```

Reuse the shared mental model from [01-reference-agent/README.md](../01-reference-agent/README.md); this folder is where LaunchDarkly enters the generate path.

## Provisioning

| Approach | Directory | Status |
|----------|-----------|--------|
| UI / docs checklist | [application.md](application.md) | Spec ready |
| Terraform | [terraform/](terraform/) | Planned |
| REST / scripts | [rest/](rest/) | Planned |

## Language implementations

| Language | Directory | Type | Status |
|----------|-----------|------|--------|
| Python | `python/` | Web | Planned |
| Python | `python-console/` | Console | Planned |
| Node.js / Java / Go / Rust / C++ | — | — | Later |

Start with **Python** (web or console) once provisioning is defined in [application.md](application.md).

## Further reading

- [application.md](application.md) — AgentControl completion config specification
- [01-reference-agent/application.md](../01-reference-agent/application.md) — baseline agent UI (no LaunchDarkly)
- [project.md](../project.md) — repository conventions
