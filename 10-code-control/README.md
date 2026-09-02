# 10-code-control

LaunchDarkly **feature flag** examples for the **lunch-marcoly** grid navigator —
boolean enablement, variation types, targeting rules, multi-contexts, then
flag prerequisites.

This series mirrors [20-agent-config](../20-agent-config/): a parent folder with
numbered children and an optional [portal](portal/) to run them side by side.

| Example | Folder | What it teaches |
|---------|--------|-----------------|
| **11** | [11-flag-enablement/](11-flag-enablement/) | Boolean flags, contexts, private `hostOs` |
| **12** | [12-flag-variations/](12-flag-variations/) | String, number, JSON, anonymous context |
| **13** | [13-flag-targeting-rules/](13-flag-targeting-rules/) | Web plus Python / Node / Java consoles: targeting rules on public `team` context attribute |
| **14** | [14-multi-context-targeting/](14-multi-context-targeting/) | Web plus Python / Node / Java / C++ / Go / Rust consoles: **multi-context** (user + organization) partner-badge 2×2 |
| **15** | [15-prerequisite-flags/](15-prerequisite-flags/) | Web (Python / Node / Java / .NET) plus consoles: highlight must serve `green` before move count can evaluate |

**16** (migration flags) is not in this series. Stub:
[99-use-cases/17-migration-flags](../99-use-cases/17-migration-flags/).

Baseline (no LaunchDarkly): [00-reference-code](../00-reference-code/).

## Portals

```bash
export LD_SDK_KEY="sdk-..."

# Python: portal :8100, children :8110 / :8120 / :8130 / :8140 / :8150
(cd portal/python && python portal.py)

# Node: portal :8101, children :8111 / :8121 / :8131 / :8141 / :8151
(cd portal/node && npm start)

# Java: portal :8102, children :8112 / :8122 / :8132 / :8142 / :8152
(cd portal/java && ./mvnw -q -DskipTests package && java -jar target/portal-java.jar)

# .NET: portal :8103, children :8113 / :8123 / :8133 / :8143 / :8153
(cd portal/dotnet && dotnet run)
```

See [portal/README.md](portal/README.md).

## Prerequisites

- LaunchDarkly project/environment and `LD_SDK_KEY`
- Flags provisioned per example (`rest/` or `terraform/` in each child)
- Language toolchains as in the [root README](../README.md)
