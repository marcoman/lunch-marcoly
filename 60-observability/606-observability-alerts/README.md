# 606-observability-alerts

**Status: stub — not implemented yet.**

One **Observability alert** on telemetry this series already sends. A constant
threshold fires when the runner pushes a number across a line they chose.
**604** stays free.

The first alert watches the successful-move counter from
[605-server-metrics](../605-server-metrics/). The same alert form can point at
an error count from [603-server-errors](../603-server-errors/) or at
`grid.move` span duration from [602-server-traces](../602-server-traces/).
Build the counter alert first. The other two are the same lesson on a signal
the runner cannot count by clicking.

Keywords: **Observability** · **alerts** · **constant threshold**

Docs: [Alerts](https://launchdarkly.com/docs/home/observability/alerts)

## Intended aha

Move until the counter crosses the threshold. The alert shows on
**Telemetry → Alerts**. The page names the alert and the value that crossed.
It does not switch a flag. That is
[16-adaptive-triggers](../../99-use-cases/16-adaptive-triggers/).

| Signal | Source in this series | Why it is or is not first |
|--------|----------------------|---------------------------|
| Successful-move counter | 605, Observability metrics | The runner can force it. Build this one. |
| Error count | 603, errors | One deliberate error may be too quiet for a threshold. Add it only after the counter alert works. |
| `grid.move` duration | 602, traces | Latency needs a slow move on purpose. Same alert type, later. |

Use a **constant** threshold. An anomaly alert needs a baseline this lab does
not have.

A member notification can also email the follower, and post in Slack when the
Slack app is installed. That is optional on this alert. The notification
lesson, email and Slack for a rollout, is
[29-rollout-notifications](../../99-use-cases/29-rollout-notifications/).

## Direction

- Python first. Intended port **:8660**.
- Start from 605 so the metric already has a name.
- One alert. Threshold low enough that a few moves cross it.

## When implementing

1. `application.md` with the metric name, the threshold, and where to look.
2. Confirm the alert source is Observability metrics for the 605 counter.
3. The rail shows the metric value and tells the runner the alert has fired.

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| *(none yet)* | — | Stub |
