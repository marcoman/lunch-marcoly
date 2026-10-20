# 16-percentage-rollout — Node console

Console grid navigator for a static LaunchDarkly **percentage rollout**.

Keywords: **percentage rollout** · **context key** · **sticky bucketing**

Docs: [Percentage rollouts](https://launchdarkly.com/docs/home/flags/rollouts)

## Prerequisites

- Node.js **20+**
- `LD_SDK_KEY` for the environment provisioned by [REST](../rest/) or
  [Terraform](../terraform/)

## Run

```bash
export LD_SDK_KEY="sdk-..."
cd 10-code-control/16-percentage-rollout/node-console
npm install
npm start
```

## What to expect

Same contract as [Python console](../python-console/): **N** / **P** walk
`marco` → `marco1` → `marco2`, unique-key observed percent versus 30%, and
recent evaluations beside the grid. Assignment lives in LaunchDarkly.
