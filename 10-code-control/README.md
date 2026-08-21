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

## Portals

```bash
export LD_SDK_KEY="sdk-..."

# Python: portal :8100, children :8110 / :8120
(cd portal/python && python portal.py)

# Node: portal :8101, children :8111 / :8121
(cd portal/node && npm start)

# Java: portal :8102, children :8112 / :8122
(cd portal/java && ./mvnw -q -DskipTests package && java -jar target/portal-java.jar)

# .NET: portal :8103, children :8113 / :8123
(cd portal/dotnet && dotnet run)
```

See [portal/README.md](portal/README.md).

## Prerequisites

- LaunchDarkly project/environment and `LD_SDK_KEY`
- Flags provisioned per example (`rest/` or `terraform/` in each child)
- Language toolchains as in the [root README](../README.md)
