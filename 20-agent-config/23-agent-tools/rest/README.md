# REST API provisioning — AgentControl tools

Create Library tools + the **`equity-briefing-tools`** completion config, attach tools, set fallthrough.

| Script | Purpose |
|--------|---------|
| `create-tools.sh` | `analyze-ticker-stories` + `compare-ticker-analyses` |
| `create-config.sh` | Config + Anthropic variation + targeting + attach |
| `attach-tools.sh` | PATCH tools onto `tools-anthropic` only |
| `update-messages.sh` | Refresh system/user messages from `messages/` |
| `update-targeting.sh` | Fallthrough variation |
| `get-config.sh` | Raw config summary (includes `tools`) |
| `get-tools-status.sh` | Demo status: Library · attach · targeting · generations |
| `delete-config.sh` | Delete config (tools left in Library) |

```bash
export LD_API_ACCESS_TOKEN=...
export LD_PROJECT_KEY=lunch-marcoly
export LD_ENVIRONMENT_KEY=test

./create-config.sh
./get-tools-status.sh
# … Generate AI Report in the UI (tool loop) …
# wait ~1 min if needed (Monitoring lag)
./get-tools-status.sh --verbose
```

Example output:

```text
Agent Config Key: equity-briefing-tools
Environment: test  (last 24h)
Healthy: yes

Library tools:
  ✓ analyze-ticker-stories  (v1)
  ✓ compare-ticker-analyses  (v1)

Variation tools-anthropic:
  found=true  model=claude-sonnet-5
  attached: compare-ticker-analyses, analyze-ticker-stories
  ✓ analyze-ticker-stories
  ✓ compare-ticker-analyses

Targeting:
  on=true  fallthrough=tools-anthropic (matches)

Metrics (last 24h):
  generationSuccessCount=3  generationErrorCount=0
```

`get-config.sh` remains the raw inspector; `get-tools-status.sh` is the before/after demo check
(sibling idea to 22’s `get-feedback-status.sh`, without thumbs).

Docs: [Tools](https://launchdarkly.com/docs/home/agentcontrol/tools) ·
[Create AI tool API](https://launchdarkly.com/docs/api/agent-control/post-ai-tool) ·
[Monitor](https://launchdarkly.com/docs/home/agentcontrol/monitor)
