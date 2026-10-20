# 10-code-control

LaunchDarkly **feature flag** examples for the **lunch-marcoly** grid navigator —
boolean enablement, variation types, targeting rules, multi-contexts,
prerequisites, percentage rollout, then scheduled changes.

This series mirrors [20-agent-config](../20-agent-config/): a parent folder with
numbered children and an optional [portal](portal/) to run them side by side.

| Example | Folder | What it teaches |
|---------|--------|-----------------|
| **101** | [101-flag-enablement/](101-flag-enablement/) | Boolean flags, contexts, private `hostOs` |
| **102** | [102-flag-variations/](102-flag-variations/) | String, number, JSON, anonymous context |
| **103** | [103-flag-targeting-rules/](103-flag-targeting-rules/) | Web plus Python / Node / Java consoles: targeting rules on public `team` context attribute |
| **104** | [104-multi-context-targeting/](104-multi-context-targeting/) | Web plus Python / Node / Java / C++ / Go / Rust consoles: **multi-context** (user + organization) partner-badge 2×2 |
| **105** | [105-prerequisite-flags/](105-prerequisite-flags/) | Web (Python / Node / Java / .NET) plus consoles: highlight must serve `green` before move count can evaluate |
| **106** | [106-percentage-rollout/](106-percentage-rollout/) | Web (Python / Node / Java / .NET) + consoles (Python / Node / Java / Go / Rust / C++) + REST/Terraform: static percentage rollout; sticky context key (not progressive) |
| **107** | [107-scheduled-changes/](107-scheduled-changes/) | Web (Python / Node / Java / .NET **:8170–:8173**) + consoles (Python / Node / Java / Go / Rust / C++) + REST/Terraform: replaceable scheduled highlight, elapsed timer |
| **108** | [108-flag-approvals/](108-flag-approvals/) | **Stub.** Approval to turn the move-count flag on. Intended ports **:8180–:8183**. Not in the portal yet |
| **109** | [109-evaluation-reasons/](109-evaluation-reasons/) | **Stub.** On-screen `PREREQUISITE_FAILED`, `RULE_MATCH`, `FALLTHROUGH`, `ERROR`. Intended ports **:8190–:8193**. Not in the portal yet |
| — | [segment-targeting/](segment-targeting/) | **Stub.** Included-targets segment (server SDK). Still unnumbered. Read before [33-synced-segments](../30-client-sdk/33-synced-segments/) |

Migration flags are not in this series. Stub:
[99-use-cases/17-migration-flags](../99-use-cases/17-migration-flags/).

Every web example in this series keeps an **About** tab in the right drawer, under **LaunchDarkly · lab**. The grid stays visible. About explains the one idea, the steps, and one docs link. That is a requirement for later examples too. See [project.md](../project.md#about-tab).

Work order: [TODO.md](../TODO.md).

Baseline (no LaunchDarkly): [00-reference-code](../00-reference-code/).

## Portals

```bash
export LD_SDK_KEY="sdk-..."

# Python: portal :8100, children :8110 / :8120 / :8130 / :8140 / :8150 / :8160 / :8170
(cd portal/python && python portal.py)

# Node: portal :8101, children :8111 / :8121 / :8131 / :8141 / :8151 / :8161 / :8171
(cd portal/node && npm start)

# Java: portal :8102, children :8112 / :8122 / :8132 / :8142 / :8152 / :8162 / :8172
(cd portal/java && ./mvnw -q -DskipTests package && java -jar target/portal-java.jar)

# .NET: portal :8103, children :8113 / :8123 / :8133 / :8143 / :8153 / :8163 / :8173
(cd portal/dotnet && dotnet run)
```

See [portal/README.md](portal/README.md).

## Prerequisites

- LaunchDarkly project/environment and `LD_SDK_KEY`
- Flags provisioned per example (`rest/` or `terraform/` in each child)
- Language toolchains as in the [root README](../README.md)
