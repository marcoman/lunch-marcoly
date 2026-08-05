# 20-agent-config

Parent folder for LaunchDarkly **AgentControl** examples built on the [01-reference-agent](../01-reference-agent/) equity briefing UI.

Examples here keep the same news → generate product shape. What changes is **where** model and prompts come from: LaunchDarkly AgentControl configs instead of local files and env-only mode.

## Examples in this series

| # | Directory | What it adds |
|---|-----------|--------------|
| 21 | [21-agent-completion-config](21-agent-completion-config/) | **Completion config**: runtime **model**, **system prompt**, and **user prompt** |

More AgentControl patterns (targeting, agent mode, rollouts, …) can land as `22-…`, `23-…` siblings under this folder.

## Common setup

Do this once before running any example under `20-agent-config/`.

### 1. Repository basics

From the repo root:

```bash
# Python (when a language folder uses the root venv)
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt    # if not already installed

# Node (when needed)
nvm use                            # see root .nvmrc
```

See [project.md](../project.md) and the root [README.md](../README.md) for OS / toolchain conventions.

### 2. LaunchDarkly

Every example in this series expects a LaunchDarkly project and environment plus a **server-side SDK key**.

```bash
export LD_PROJECT_KEY="default"
export LD_ENVIRONMENT_KEY="test"
export LD_SDK_KEY="sdk-..."
```

You also need permission to create **AgentControl** configs. Per-example config keys and variations are documented in each child `application.md`.

| Topic | Docs |
|-------|------|
| AgentControl | [AgentControl](https://launchdarkly.com/docs/home/agentcontrol) |
| Quickstart | [Quickstart for AgentControl](https://launchdarkly.com/docs/home/agentcontrol/quickstart) |
| AI SDKs | [AI SDKs](https://launchdarkly.com/docs/sdk/ai) |

### 3. LLM providers (start here)

AgentControl **names** the model in the config variation. Your machine or cloud account must still be able to **call** that model. Use the paths below for local learning; point the LaunchDarkly variation at a matching model id.

#### Ollama (recommended first path)

Local, no cloud keys. Good default for classroom and laptop demos.

1. Install and start [Ollama](https://ollama.com).
2. Pull a small chat model:

```bash
ollama pull llama3.2:3b
```

3. Confirm the daemon:

```bash
curl -s http://127.0.0.1:11434/api/tags | head
```

4. In the AgentControl variation (or while iterating), use a model name your app maps to Ollama (e.g. `llama3.2:3b`). Language READMEs document exact mapping.

| Variable | Default | Purpose |
|----------|---------|---------|
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama base URL |
| `OLLAMA_MODEL` | `llama3.2:3b` | Fallback / local tag when the app still reads env |

Baseline behavior without LaunchDarkly: [01-reference-agent](../01-reference-agent/) with `AGENT_LLM_MODE=ollama`.

#### AWS Bedrock (optional cloud path)

Use when a variation targets a Bedrock model (e.g. Nova Lite). This series expects **IAM Identity Center (SSO)** with a named profile—not long-lived access keys in the shell for day-to-day demos.

**Expectations**

1. AWS CLI v2 installed and configured for SSO.
2. A profile named **`Administrator`** in `~/.aws/config` (same convention as `01-reference-agent`), or set `AWS_PROFILE` to your profile.
3. Permission to invoke the Bedrock model in the target region (default **`us-east-1`**).
4. You have run SSO login recently enough that credentials are valid:

```bash
aws sso login --profile Administrator
export AWS_PROFILE=Administrator
export AWS_REGION=us-east-1
```

| Variable | Default | Purpose |
|----------|---------|---------|
| `AWS_PROFILE` | `Administrator` | SSO / named profile |
| `AWS_REGION` / `AWS_DEFAULT_REGION` | `us-east-1` | Bedrock region |
| `AGENT_BEDROCK_MODEL_ID` | Nova Lite id (see 01 docs) | Local fallback model id when used |

Ambient `AWS_ACCESS_KEY_ID` / secret / session tokens in the environment can confuse SSO-based apps; prefer a clean shell after `aws sso login`.

Details and model notes: [01-reference-agent/application.md — AWS Bedrock](../01-reference-agent/application.md#aws-bedrock).

#### Stub / other providers

- **Stub**: useful for UI-only checks; AgentControl examples should still document whether stub is an explicit offline fallback.
- **Anthropic / OpenAI / etc.**: add provider API keys only when a variation (or language README) requires them. Do not commit secrets.

### 4. Baseline agent (optional)

If you have not run the non-LD agent yet:

```bash
cd 01-reference-agent/python
AGENT_LLM_MODE=ollama python 01-reference-agent.py
# open http://127.0.0.1:8090/
```

That confirms Yahoo stories, streaming UI, and Ollama before you add AgentControl.

## How to navigate

1. Read this page (shared LD + LLM setup).
2. Open the child example README + `application.md` (config key, variations, acceptance criteria).
3. Provision the AgentControl config (UI checklist and/or `terraform/` / `rest/` when present).
4. Run the language implementation under that example.

## Related

- [01-reference-agent](../01-reference-agent/) — baseline agent (file prompt + env model; no LaunchDarkly)
- [project.md](../project.md) — repository conventions
- [21-agent-completion-config](21-agent-completion-config/) — first AgentControl example in this series
