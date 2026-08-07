# 20-agent-config

Parent folder for LaunchDarkly **AgentControl** examples built on the [01-reference-agent](../01-reference-agent/) equity briefing UI.

Examples here keep the same news → generate product shape. What changes is **where** model and prompts come from: LaunchDarkly AgentControl configs instead of local files and env-only mode.

## Examples in this series

| # | Directory | What it adds |
|---|-----------|--------------|
| 21 | [21-agent-completion-config](21-agent-completion-config/) | **Completion config**: runtime **model**, **system prompt**, and **user prompt** — provision with [rest/](21-agent-completion-config/rest/) |

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

AgentControl **names** the model in the config variation. Your machine or cloud account must still be able to **call** that model.

**Ollama is the required local path for these examples.** Pulling the documented tags lets anyone run generate end-to-end without a cloud LLM account. Cloud providers (Bedrock and others) remain available when you want stronger models later—point a variation at a cloud model id once credentials work.

#### Ollama (required local path)

Local inference is how the series stays classroom-friendly: no AWS or OpenAI bill to smoke-test AgentControl, and every laptop can show **model + prompt** changes from LaunchDarkly.

1. Install and start [Ollama](https://ollama.com).
2. Pull the models your example documents (see below).
3. Confirm the daemon:

```bash
curl -s http://127.0.0.1:11434/api/tags | head
ollama list
```

4. Keep the LaunchDarkly variation’s model id aligned with a tag from `ollama list` (Custom provider → same string the app passes to Ollama).

| Variable | Default | Purpose |
|----------|---------|---------|
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama base URL |
| `OLLAMA_MODEL` | `llama3.2:3b` | Fallback / local tag when the app still reads env |

**[01-reference-agent](../01-reference-agent/)** (no LaunchDarkly) — one small model is enough:

```bash
ollama pull llama3.2:3b
```

Then run with `AGENT_LLM_MODE=ollama`.

**[21-agent-completion-config](21-agent-completion-config/)** — **all three tags are required.** Each demo persona is wired to a different Ollama model so switching users visibly changes provider/model in the UI (not only the system prompt). Missing a tag breaks generate for that persona.

| Tier | Ollama tag | Persona / variation | Why this tag |
|------|------------|---------------------|--------------|
| Best | `llama3.2:3b` | Conservative Charlie → `concise-skeptic` | Strongest of the local lot |
| Default | `gemma2:2b` | Neutral Nancy / Anonymous Amelia → `baseline-analyst` | Middle tier; fallthrough |
| Simple | `llama3.2:1b` | Thoughtless Toby → `reckless-hype` | Smallest / cheapest local option |

```bash
ollama pull llama3.2:3b    # required — Charlie (best)
ollama pull gemma2:2b      # required — Nancy / Amelia (default)
ollama pull llama3.2:1b    # required — Toby (simple)
```

Full narrative and verification: [21-agent-completion-config README](21-agent-completion-config/README.md#required-ollama-models).

#### AWS Bedrock (optional cloud path)

Use when you want **enhanced** results beyond the local trio—or when a variation targets a Bedrock model (e.g. Nova Lite). Local Ollama still covers the happy-path demo; Bedrock is the upgrade path, not a substitute for pulling the three tags above.

This series expects **IAM Identity Center (SSO)** with a named profile—not long-lived access keys in the shell for day-to-day demos.

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
3. Provision the AgentControl config ([rest/](21-agent-completion-config/rest/) preferred; UI checklist in [PROVISIONING.md](21-agent-completion-config/PROVISIONING.md)).
4. Run the language implementation under that example.

## Related

- [01-reference-agent](../01-reference-agent/) — baseline agent (file prompt + env model; no LaunchDarkly)
- [project.md](../project.md) — repository conventions
- [21-agent-completion-config](21-agent-completion-config/) — first AgentControl example in this series
