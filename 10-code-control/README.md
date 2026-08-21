# 10-code-control

LaunchDarkly **feature flag** examples for the **lunch-marcoly** grid navigator —
boolean enablement first, then variation types.

This series mirrors [20-agent-config](../20-agent-config/): a parent folder with
numbered children and an optional [portal](portal/) to run them side by side.

| Example | Folder | What it teaches |
|---------|--------|-----------------|
| **11** | [11-flag-enablement/](11-flag-enablement/) | Boolean flags, contexts, private `hostOs` |
| **12** | [12-flag-variations/](12-flag-variations/) | String, number, JSON, anonymous context |

Baseline (no LaunchDarkly): [00-reference-code](../00-reference-code/).

## Portal (Python)

```bash
export LD_SDK_KEY="sdk-..."
cd portal/python && python portal.py
# → http://127.0.0.1:8100/  (tabs: 11 on :8110 · 12 on :8120)
```

See [portal/README.md](portal/README.md).

## Prerequisites

- LaunchDarkly project/environment and `LD_SDK_KEY`
- Flags provisioned per example (`rest/` or `terraform/` in each child)
- Language toolchains as in the [root README](../README.md)
