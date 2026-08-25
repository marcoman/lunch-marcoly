# REST API provisioning

Create the **31-client-evaluation** flags with **client-side SDK availability**.

Keywords: **REST API** · **clientSideAvailability** · **usingEnvironmentId**

- [Using the LaunchDarkly REST API](https://launchdarkly.com/docs/guides/api/rest-api)
- [Create a feature flag](https://launchdarkly.com/docs/api/feature-flags/post-feature-flag)

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_API_ACCESS_TOKEN` | Yes | Authorization header |
| `LD_PROJECT_KEY` | Yes | Project that owns the flags |
| `LD_ENVIRONMENT_KEY` | For defaults | Turn flags **off** after create |
| `LD_API_HOST` | No | Defaults to `https://app.launchdarkly.com` |

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
chmod +x *.sh
./create-flags.sh
./get-flag-status.sh
```

| Script | Purpose |
|--------|---------|
| `create-flags.sh` | Both flags, client-side available, off in `LD_ENVIRONMENT_KEY` |
| `get-flag-status.sh` | Demo snapshot: exists, client-side availability, on/off (`--json` / `--verbose`) |
| `get-flag.sh <key>` | Compact JSON for one flag |
| `update-flag.sh <key>` | JSON Patch description + turn on |
| `delete-flag.sh <key>` | Permanent delete |

Flag keys: `enable-client-grid-highlight`, `show-client-move-count`.
