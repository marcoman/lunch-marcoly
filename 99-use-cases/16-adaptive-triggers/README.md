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
| Trigger default | Constant, Above 200 ms, shortest window offered, switch to `none` |

In the **Add adaptive trigger** dialog you set only two fields — the source
metric and the alert threshold — then verify **Switch variation to** is
`Safe: no highlight` and pick the shortest **alert window** available. Latency
must stay above the threshold for that full window, so prefer 1 minute over 30.

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
| Python | [python/](python/) | Web application | Implemented |
| Java | [java/](java/) | Web application | Implemented |
| .NET | [dotnet/](dotnet/) | Web application | Implemented |

The browser sends only username, slider value, and control requests to the
local language host. SDK and API credentials remain server-side. Each web twin
uses port `8161`, so run one at a time.

## Demo sequence

1. Log in.
2. Click **Start live (green)**.
3. Move below the 200 ms threshold.
4. Raise the slider above 200 ms and enable **Auto-report once per second** so
   the metric has data for the whole alert window.
5. Observe `Flag value` and the grid switch to `none`, and the **Default rule**
   card record the `green → none` switch with its attribution.
6. Click **Stop** to turn the flag off. Remove the adaptive trigger in the UI
   separately.

This is a variation switch, not use of the SDK fallback value.

The app rail deep-links to the flag's Targeting and Monitoring tabs and reports
whether `LD_SDK_KEY` and `LD_ENVIRONMENT_KEY` resolve to the same environment —
a mismatch is the most common reason a correctly configured trigger never fires.
See the selected language README for build instructions. The
[Node README](node/README.md) contains the full troubleshooting table shared by
all three implementations.
