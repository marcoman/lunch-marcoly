# REST provisioning — 16-adaptive-triggers

Creates the dedicated string flag and custom numeric metric. The adaptive
trigger itself is configured in the LaunchDarkly UI; the public **flag
triggers** API creates webhook workflows and is not the same product.

Adaptive triggers: https://launchdarkly.com/docs/home/flags/triggers

## Prerequisites

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
chmod +x *.sh
```

## Workflow

```bash
./configure-adaptive-trigger.sh
# Complete the printed UI steps.
./get-status.sh
```

| Script | Purpose |
|--------|---------|
| `create-flag.sh` | Create `enable-adaptive-grid-highlight`, off with safe `none` |
| `create-metric.sh` | Create numeric metric `adaptive-grid-nav-latency-metric` for event key `adaptive-grid-nav-latency` |
| `configure-adaptive-trigger.sh` | Provision both resources and print exact UI steps |
| `start-live.sh` | Turn on targeting and serve `green` to all contexts |
| `stop.sh` | Turn targeting off so evaluations return `none` |
| `get-status.sh` | Show flag targeting and metric metadata |

The Node app offers the same **Start live** and **Stop** operations through a
local proxy; the API access token stays in the Node process. Stop does not
remove the adaptive trigger.
