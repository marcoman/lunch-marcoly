# REST — provision `equity-briefing-tracked-completion`

```bash
export LD_API_ACCESS_TOKEN=...
export LD_PROJECT_KEY=lunch-marcoly
export LD_ENVIRONMENT_KEY=test

./create-config.sh
./update-name-targeting.sh
./get-config.sh
```

| Script | Purpose |
|--------|---------|
| `create-config.sh` | Config + `tracked-ollama` + `tracked-anthropic` + fallthrough |
| `update-name-targeting.sh` | Best Betty → Anthropic |
| `update-targeting.sh [variation]` | Fallthrough only |
| `get-config.sh` / `delete-config.sh` | Inspect / remove |

Requires `jq`. AgentControl API version: `beta` (see `common.sh`).
