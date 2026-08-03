# REST API provisioning

Creates segments, string highlight flag, VIP boolean flag, and segment targeting for [02-segments-by-name](../application.md).

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

`create-all.sh` also creates the **`VIP`** boolean flag (default **off** / `false`) with targeting for segment `seg-by-name-vip` (`name` contains `vip`, case-insensitive).

All segments are created as **standard rule-based** segments (`unbounded: false`). Do not create them as **big segments** (larger list-based / synced): big segments cannot use targeting rules, which produces an invalid configuration in the UI.

If a segment was created as a big segment by mistake, delete it and recreate it. Example for VIP:

```bash
# Delete (big segments cannot be converted to rule-based)
curl -sS -X DELETE \
  -H "Authorization: ${LD_API_ACCESS_TOKEN:-$LD_ACCESS_TOKEN}" \
  -H "LD-API-Version: 20240415" \
  "${LD_API_HOST:-https://app.launchdarkly.com}/api/v2/segments/${LD_PROJECT_KEY}/${LD_ENVIRONMENT_KEY}/seg-by-name-vip"

# Recreate as standard rule-based
curl -sS -X POST \
  -H "Authorization: ${LD_API_ACCESS_TOKEN:-$LD_ACCESS_TOKEN}" \
  -H "LD-API-Version: 20240415" \
  -H "Content-Type: application/json" \
  "${LD_API_HOST:-https://app.launchdarkly.com}/api/v2/segments/${LD_PROJECT_KEY}/${LD_ENVIRONMENT_KEY}" \
  -d '{
    "key": "seg-by-name-vip",
    "name": "By name: VIP",
    "unbounded": false,
    "tags": ["grid-navigator", "use-case", "segments-by-name"],
    "rules": [{
      "description": "name contains vip (case-insensitive)",
      "clauses": [{
        "contextKind": "user",
        "attribute": "name",
        "op": "matches",
        "values": ["(?i).*vip.*"],
        "negate": false
      }]
    }]
  }' | jq '{key, unbounded, rules}'
```

Then ensure the `VIP` flag still targets `seg-by-name-vip` (re-run `./create-all.sh` if needed).

`create-all.sh` ensures each segment has a targeting rule. If segments already exist but have empty rules (a common symptom: every user gets `highlightColor: "none"` with reason `FALLTHROUGH`), re-run the script to add the rules.

The targeting patch uses each variation's `_id` (`variationId`) as required by the semantic patch API.