# REST API provisioning

Creates segments, string highlight flag, and segment targeting for [02-segments-by-name](../application.md).

## Environment variables

| Variable | Required |
|----------|----------|
| `LD_API_ACCESS_TOKEN` | Yes |
| `LD_PROJECT_KEY` | Yes |
| `LD_ENVIRONMENT_KEY` | Yes | Environment **key** (e.g. `production`). If you use an environment id, the script resolves it to the key. |

## Run

```bash
chmod +x *.sh
./create-all.sh
./get-flag.sh
```

**Note:** This use case defines `configure-grid-selection-green-highlight` as a **string** flag. If you already provisioned it as boolean from [10-flag-enablement](../../../10-flag-enablement/), `create-all.sh` replaces it automatically.

`create-all.sh` ensures each segment has a targeting rule. If segments already exist but have empty rules (a common symptom: every user gets `highlightColor: "none"` with reason `FALLTHROUGH`), re-run the script to add the rules.

The targeting patch uses each variation's `_id` (`variationId`) as required by the semantic patch API.
