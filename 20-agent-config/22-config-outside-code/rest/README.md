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
| `get-feedback-status.sh` | Thumbs +/− counts/rates; `--verbose` adds LD links |

### Feedback snapshot (before / after generate)

```bash
./get-feedback-status.sh
# … Generate AI Report + 👍/👎 in the UI …
# wait ~1 min if needed (Monitoring lag)
./get-feedback-status.sh --verbose
```

Example output:

```text
Agent Config Key: equity-briefing-tracked-completion
Environment: production  (last 24h)
Thumbs Up: 1  (positiveRate=50%)
Thumbs Down: 1  (negativeRate=50%)
count=2  (Thumbs Up + Thumbs Down)
generationSuccessCount=3  generationErrorCount=0
```

With `--verbose`, also prints:

```text
Event key → Event name
  $ld:ai:feedback:user:positive  →  Positive AI feedback (thumbs up)
  …

Related autogen metrics (Experiments / Guarded rollouts):
  Positive AI feedback count   (event: $ld:ai:feedback:user:positive)
  Positive AI feedback rate    (event: $ld:ai:feedback:user:positive)
  …
```

Plus Agent Config / Monitoring URLs and docs links. Use `--json` (and optionally `--verbose`) for machine-readable output. Window: `LD_METRICS_LOOKBACK_HOURS` (default 24).

Requires `jq`. AgentControl API version: `beta` (see `common.sh`).
