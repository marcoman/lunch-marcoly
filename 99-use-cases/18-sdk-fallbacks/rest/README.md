# REST provisioning — 18-sdk-fallbacks

Creates `enable-sdk-fallback-grid-highlight` as a string flag with:

- `none` — off variation and application code default
- `green` — on fallthrough
- targeting **on**

The distinct values make `DEFAULT` visibly different from `STREAM` and
`LAST_KNOWN`.

## Run

Requires `curl` and `jq`:

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
./create-flag.sh
```

Use an SDK key from that same environment when running the Python app.

LaunchDarkly feature flag API:
https://launchdarkly.com/docs/api/feature-flags
