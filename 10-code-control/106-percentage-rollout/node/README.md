# 16-percentage-rollout — Node web

Static LaunchDarkly **percentage rollout** on the grid highlight.

Keywords: **percentage rollout** · **context key** · **sticky bucketing**

Docs: [Percentage rollouts](https://launchdarkly.com/docs/home/flags/rollouts)

## Prerequisites

- Node.js **20+**
- `LD_SDK_KEY` for the environment provisioned by [REST](../rest/) or
  [Terraform](../terraform/)

## Run

```bash
export LD_SDK_KEY="sdk-..."
cd 10-code-control/16-percentage-rollout/node
npm install
npm start
```

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/). `PORT` overrides the
default. The Node portal tab 16 uses **:8161**.

## What to expect

Same contract as [Python](../python/): username is the `user` context key,
`enable-grid-selection-highlight-pct` is evaluated with `variationDetail`, and
the UI explores generated names plus unique-key observed percent. Assignment
lives in LaunchDarkly, not in this process.
