# REST

Creates the AgentControl completion config `terraform-codegen-compare`.

Keywords: **AgentControl** · **completion config** · **model config** · **targeting**

| Topic | Docs |
|-------|------|
| Create a config | [POST AI config](https://launchdarkly.com/docs/api/agent-control/post-ai-config) |
| Add a variation | [POST variation](https://launchdarkly.com/docs/api/agent-control/post-ai-config-variation) |
| Targeting | [Patch targeting](https://launchdarkly.com/docs/api/agent-control/patch-ai-config-targeting) |

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="test"
./create-config.sh
```

| Script | What it does |
|--------|----------------|
| `create-config.sh` | Model configs if missing, the completion config, variations `local-1b`, `local-8b`, and `claude-sonnet`, then targeting |
| `add-local-8b-variation.sh` | Adds `local-8b` (`llama3.1:8b`) to a config that already exists, then retargets |
| `add-haiku-variation.sh` | Adds `claude-haiku` to a config that already exists, then retargets |
| `add-claude-variation.sh` | Adds `claude-sonnet` to a config that already exists, then retargets |
| `create-judge.sh` | Creates `terraform-codegen-judge` (Sonnet, temperature 0) and sets its fallthrough |
| `update-targeting.sh` | `codegen-1b` → `local-1b`. `codegen-8b` → `local-8b` when that variation exists. `codegen-sonnet` → `claude-sonnet`. Fallthrough → `local-3b` |
| `delete-config.sh` | Deletes `terraform-codegen-compare` only |

The prompt files are `messages/system.txt` and `messages/user.txt`. The user message contains `{{ model_name }}` and `{{ variation_key }}`.
