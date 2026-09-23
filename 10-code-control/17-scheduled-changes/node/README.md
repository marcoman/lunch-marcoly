# 17-scheduled-changes — Node web

Schedule a LaunchDarkly flag to turn the grid highlight on after a short delay.

Keywords: **scheduled changes** · **detailed evaluation** · **semantic patch**

Docs: [Scheduled changes](https://launchdarkly.com/docs/home/flags/scheduled-changes)

## Prerequisites

- Node.js **20+**
- A LaunchDarkly Enterprise plan
- Flag provisioned by [REST](../rest/) or [Terraform](../terraform/)
- `LD_SDK_KEY` for SDK evaluation
- `LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, and `LD_ENVIRONMENT_KEY` for the
  schedule controls

## Run

```bash
export LD_SDK_KEY="sdk-..."
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"

cd 10-code-control/17-scheduled-changes/node
npm install
npm start
```

Open [http://127.0.0.1:8171/](http://127.0.0.1:8171/). `PORT` overrides the
default.

Choose a delay (one minute minimum) and start. Starting again deletes every
pending change for `enable-grid-selection-highlight-sched`, turns the flag off
with a semantic patch, and schedules `turnFlagOn`.

The second button reads **Stop schedule** while a change is pending and
**Turn flag off** after it applies. Both states delete pending changes and turn
the flag off. The elapsed clock then freezes until another schedule starts.

## Why the highlight can lag

LaunchDarkly executes close to the requested time rather than at an exact
second. The change must then reach the server SDK stream, and the page polls
the detailed evaluation every two seconds. The panel reports when `green` was
first observed so that mismatch remains visible.
