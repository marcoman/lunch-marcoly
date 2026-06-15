# REST API provisioning

Create, read, update, and delete the grid navigator feature flags using the [LaunchDarkly REST API](https://launchdarkly.com/docs/guides/api/rest-api).

## Prerequisites

- `curl` and `jq`
- LaunchDarkly API access token with flag management permissions

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_API_ACCESS_TOKEN` | Yes | Passed as the `Authorization` header |
| `LD_PROJECT_KEY` | Yes | Project that owns the flags |
| `LD_ENVIRONMENT_KEY` | For create/update defaults | Environment where flags default to **off** |
| `LD_API_HOST` | No | API base URL (defaults to `https://app.launchdarkly.com`) |
| `LD_API_VERSION` | No | `LD-API-Version` header (defaults to `20240415`) |

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="default"
export LD_ENVIRONMENT_KEY="test"
```

## How to run

Make scripts executable once:

```bash
chmod +x *.sh
```

### Create both flags

```bash
./create-flags.sh
```

Creates `configure-grid-selection-green-highlight`, `configure-grid-selection-context-highlight`, and `show-navigation-move-count`. When `LD_ENVIRONMENT_KEY` is set, all three flags are turned **off** in that environment.

### Retrieve a flag

```bash
./get-flag.sh show-navigation-move-count
./get-flag.sh configure-grid-selection-green-highlight
./get-flag.sh configure-grid-selection-context-highlight
```

Equivalent curl:
  -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
  -H "LD-API-Version: ${LD_API_VERSION:-20240415}"
```

### Update a flag

```bash
./update-flag.sh show-navigation-move-count
```

This script demonstrates two update styles:

1. **JSON Patch** — replaces the flag `description` ([Updates using JSON Patch](https://launchdarkly.com/docs/api#updates-using-json-patch))
2. **Semantic patch** — turns the flag **on** in `LD_ENVIRONMENT_KEY` ([Updates using semantic patch](https://launchdarkly.com/docs/api#updates-using-semantic-patch))

To turn a flag off again:

```bash
curl -X PATCH "${LD_API_HOST:-https://app.launchdarkly.com}/api/v2/flags/${LD_PROJECT_KEY}/show-navigation-move-count" \
  -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
  -H "LD-API-Version: ${LD_API_VERSION:-20240415}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "{
    \"environmentKey\": \"${LD_ENVIRONMENT_KEY}\",
    \"instructions\": [{\"kind\": \"turnFlagOff\"}]
  }"
```

### Delete a flag

```bash
./delete-flag.sh show-navigation-move-count
```

Deletion is permanent. Re-create flags with `./create-flags.sh` or Terraform.

## What to expect

| Script | HTTP method | Endpoint | Result |
|--------|-------------|----------|--------|
| `create-flags.sh` | `POST` | `/api/v2/flags/{projectKey}` | `201` — two new boolean flags |
| `get-flag.sh` | `GET` | `/api/v2/flags/{projectKey}/{flagKey}` | `200` — flag JSON |
| `update-flag.sh` | `PATCH` | `/api/v2/flags/{projectKey}/{flagKey}` | `200` — updated flag |
| `delete-flag.sh` | `DELETE` | `/api/v2/flags/{projectKey}/{flagKey}` | `204` — flag removed |

Verify flags in the LaunchDarkly UI under **Feature flags**, or list them:

```bash
curl -s "${LD_API_HOST:-https://app.launchdarkly.com}/api/v2/flags/${LD_PROJECT_KEY}?filter=tags:grid-navigator" \
  -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
  -H "LD-API-Version: ${LD_API_VERSION:-20240415}" | jq '.items[] | {key, name, tags}'
```

## Further reading

- [Using the LaunchDarkly REST API](https://launchdarkly.com/docs/guides/api/rest-api)
- [Create a feature flag](https://launchdarkly.com/docs/api/feature-flags/post-feature-flag)
- [Update feature flag](https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag)
- [Delete feature flag](https://launchdarkly.com/docs/api/feature-flags/delete-feature-flag)
