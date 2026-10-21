# 36-client-track-events

Browser **custom events**: the client SDK `track()` sends `login_completed` and
`grid_move` for the logged-in context. After `flush()`, those events show up
in the LaunchDarkly **Live events** page.

This is the client SDK. It is not Twilio Segment `track()`
([34](../34-synced-segments-twilio/)). It is not a server metric
([16-adaptive-triggers](../../99-use-cases/16-adaptive-triggers/)).

Baseline UI: [02-reference-client-code](../../02-reference-client-code/).
Behavior spec: [application.md](application.md).

Keywords: **track** · **custom events** · **flush** · **client-side SDK**

Docs: [Sending custom events](https://launchdarkly.com/docs/sdk/features/events) ·
[JavaScript SDK](https://launchdarkly.com/docs/sdk/client-side/javascript) ·
[React Web SDK](https://launchdarkly.com/docs/sdk/client-side/react/react-web) ·
[Vue SDK](https://launchdarkly.com/docs/sdk/client-side/vue)

## What you should see

Log in. The lab log records `track login_completed`. Move to a new cell. The log
records `track grid_move` with `{ from, to }`. Holding a key into the wall does
not send `grid_move`.

`flush()` sends the batch immediately, so Live events does not wait on the SDK interval.

## Seeing the events in LaunchDarkly

The lab log is the local proof that `track()` ran. To see the same events in
LaunchDarkly, open **[Live events](https://launchdarkly.com/docs/home/releases/live-events)**
for this environment while you log in and move. Restrict the list to **Custom**
events. `login_completed` and `grid_move` appear on the row for that username.

There is no public API that returns those events to a script. `rest/` only
provisions the flags. A live feed of the events is outside this exercise.

## Events

| Event key | When | Data |
|-----------|------|------|
| `login_completed` | Client is ready after login | none |
| `grid_move` | The selected cell changes | `{ from, to }` such as `m/m` → `t/m` |

No metric value. Numeric metrics belong to Experimentation, not this example.

## Flags

The grid still evaluates two dedicated flags so 31 stays independent. Both must
be available to client-side SDKs.

| Flag key | Type | Code default |
|----------|------|--------------|
| `enable-client-track-highlight` | string | `none` |
| `show-client-track-move-count` | boolean | `false` |

## Prerequisites

1. `LD_CLIENT_SIDE_ID` for the environment (not `LD_SDK_KEY`).
2. Provision the two flags ([rest/](rest/) or [terraform/](terraform/)).
3. For in-page Controls: `LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, `LD_ENVIRONMENT_KEY`.

```bash
export LD_CLIENT_SIDE_ID="..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
export LD_API_ACCESS_TOKEN="api-..."
```

## Language implementations

| Language | Directory | Run | URL |
|----------|-----------|-----|-----|
| JavaScript | [javascript/](javascript/) | `npm start` | [http://127.0.0.1:8360/](http://127.0.0.1:8360/) |
| React Web | [react/](react/) | `npm start` | [http://127.0.0.1:8361/](http://127.0.0.1:8361/) |
| Vue | [vue/](vue/) | `npm start` | [http://127.0.0.1:8362/](http://127.0.0.1:8362/) |

Portal tabs: [../portal/](../portal/) (**36** on :8360 / :8361 / :8362).
