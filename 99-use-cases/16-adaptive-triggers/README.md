# 16-adaptive-triggers

Automatically switch a live grid highlight to a safe variation when a custom
numeric latency metric crosses a threshold.

Unlike [14-progressive-rollout](../14-progressive-rollout/) and
[15-guarded-rollout](../15-guarded-rollout/), this use case has no percentage
ramp. The app serves `green`, reports numeric latency events, and an
**adaptive trigger** changes the flag's default variation to `none`.

Full behavior: [application.md](application.md).

Keywords: **adaptive triggers** · **custom numeric metric** · **track** ·
**constant threshold** · **alert window** · **switch variation**

Docs: [Adaptive triggers](https://launchdarkly.com/docs/home/flags/triggers) ·
[Custom numeric metrics](https://launchdarkly.com/docs/home/observability/custom-numeric) ·
[Sending custom events](https://launchdarkly.com/docs/sdk/features/events)

## Resources

| Resource | Key |
|----------|-----|
| String flag | `enable-adaptive-grid-highlight` |
| Live variation | `green` |
| Safe variation | `none` |
| Metric key | `adaptive-grid-nav-latency-metric` |
| Custom event key | `adaptive-grid-nav-latency` |
| Trigger default | Constant, Above 200 ms, 1 minute, switch to `none` |

Adaptive triggers are available on select plans, are environment-specific, and
do not run while the flag has an active experiment.

## Quick start

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
export LD_SDK_KEY="sdk-..."

cd rest
chmod +x *.sh
./configure-adaptive-trigger.sh
# Complete the printed adaptive-trigger steps in the LaunchDarkly UI.

cd ../node
npm install
npm start
```

Open [http://127.0.0.1:8161/](http://127.0.0.1:8161/).

## Implementation

| Language | Directory | Application type | Status |
|----------|-----------|------------------|--------|
| Node.js | [node/](node/) | Web application | Implemented |

The browser sends only username, slider value, and control requests to the
local Node host. SDK and API credentials remain server-side.

## Demo sequence

1. Log in.
2. Click **Start live (green)**.
3. Move below the 200 ms threshold.
4. Raise the slider above 200 ms and continue moving for the alert window.
5. Observe `Flag value` and the grid switch to `none`.

This is a variation switch, not use of the SDK fallback value.
