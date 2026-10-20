# REST API provisioning

Create, read, update, and delete the flag-variations feature flags using the [LaunchDarkly REST API](https://launchdarkly.com/docs/guides/api/rest-api).

## Prerequisites

- `curl` and `jq`
- LaunchDarkly API access token with flag management permissions

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_API_ACCESS_TOKEN` | Yes | Passed as the `Authorization` header |
| `LD_PROJECT_KEY` | Yes | Project that owns the flags |
| `LD_ENVIRONMENT_KEY` | For create defaults | Environment where flags get default targeting |
| `LD_API_HOST` | No | API base URL (defaults to `https://app.launchdarkly.com`) |
| `LD_API_VERSION` | No | `LD-API-Version` header (defaults to `20240415`) |

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="default"
export LD_ENVIRONMENT_KEY="test"
```

## How to run

```bash
chmod +x *.sh
./create-flags.sh
```

Creates all four flags. When `LD_ENVIRONMENT_KEY` is set:

- `show-anonymous-host-os-emoji` → **off**
- `configure-navigation-count-label` → **on** (default `"Count"`)
- `configure-lucky-number` → **on** (default `0`)
- `configure-max-navigation-moves` → **on** (default `{"maxMoves": 100}`)

### Retrieve a flag

```bash
./get-flag.sh configure-navigation-count-label
./get-flag.sh configure-lucky-number
./get-flag.sh configure-max-navigation-moves
./get-flag.sh show-anonymous-host-os-emoji
```

### Delete a flag

```bash
./delete-flag.sh configure-navigation-count-label
```

## Further reading

- [Using the LaunchDarkly REST API](https://launchdarkly.com/docs/guides/api/rest-api)
- [application.md](../application.md) — flag specification
