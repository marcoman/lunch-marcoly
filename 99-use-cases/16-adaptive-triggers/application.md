# Adaptive Triggers Use Case

This document defines **16-adaptive-triggers** under [99-use-cases](../README.md).

## Goal

Serve a **grid selection highlight** as a live variation, report a **custom numeric latency** metric from the app, and let an **adaptive trigger** **switch the served variation** to a safe one when that metric stays **above a constant threshold** for an **alert window**.

This is **not** a progressive or guarded rollout. Traffic is not ramped. LaunchDarkly does not compare treatment vs control. When the threshold is crossed, targeting **switches variation** (for example `green` → `none`).

> Lab default: live variation **`green`**, safe variation **`none`**, custom metric **`adaptive-grid-nav-latency`**, constant threshold **Above 200 ms**, alert window **1 minute** (or the shortest window the product allows).

Baseline grid navigator behavior is defined in [00-reference-code/application.md](../../00-reference-code/application.md).

Keywords: **adaptive triggers** · **custom metrics** · **track** · **threshold** · **alert window** · **switch variation**

Docs: [Adaptive triggers](https://launchdarkly.com/docs/home/flags/triggers) ·
[Custom numeric metrics](https://launchdarkly.com/docs/home/observability/custom-numeric) ·
[Sending custom events](https://launchdarkly.com/docs/sdk/features/events)

## What this is not

| Concept | This example |
|---------|----------------|
| SDK **fallback value** (last argument to `variation()`) | Unused as the observed outcome. That value is for “cannot reach LaunchDarkly,” not for a fired trigger. |
| [Flag triggers](https://launchdarkly.com/docs/home/releases/triggers) (webhook URL, turn flag on/off) | Different product. 16 uses **adaptive** triggers on the flag **Targeting** tab. |
| [14-progressive-rollout](../14-progressive-rollout/) | Time-based percentage stages. No metric switch. |
| [15-guarded-rollout](../15-guarded-rollout/) | Percentage ramp + statistical regression vs control. Different metrics and event keys. |
| AgentControl Adaptive Triggers | Later series. This lab is a **feature flag** trigger, not a model/provider failover. |
| Observability / session / error **sources** | Out of scope. Those need the observability SDK. 16 uses a **LaunchDarkly hosted custom metric**. |

Adaptive triggers are **plan-gated**, **environment-specific**, and **do not run** on a flag that has an **active experiment**. They **bypass approvals** when they fire.

A trigger evaluates its metric **across the whole environment**, not only contexts that receive this flag. Event keys and metric definitions must be unique to 16.

## Flag

| Attribute | Value |
|-----------|-------|
| **Name** | `Enable: adaptive grid highlight` |
| **Key** | `enable-adaptive-grid-highlight` |
| **Kind** | Enable |
| **Variation type** | string |
| **Temporary** | No |
| **Tags** | `grid-navigator`, `use-case`, `adaptive-triggers`, `string` |
| **Client-side** | not required (server-side examples are the default for 99-use-cases) |

| Variation | Role |
|-----------|------|
| `green` | **Live** — colored highlight (the behavior you start serving) |
| `none` | **Safe** — no highlight (the variation the trigger **switches to**) |

Do **not** reuse `enable-grid-selection-highlight` (11 / 14 / 15).

Off variation is `none`. After provisioning, the flag is **off**. The in-app **start** control turns targeting **on** and sets the default rule to serve **`green`** (100% — no percentage rollout).

When the adaptive trigger fires, LaunchDarkly changes the default rule to serve **`none`**. The application must re-evaluate (console: 500 ms poll; web: streaming / `change:`) so the grid updates without reload.

## Metric

| Attribute | Value |
|-----------|-------|
| **Name** | `Adaptive: grid navigation latency` |
| **Event key** | `adaptive-grid-nav-latency` — this is the string in `track()` |
| **Metric key** | `adaptive-grid-nav-latency-metric` — used by REST and the trigger source; do not confuse it with the event key. |
| **Kind** | Custom **numeric** |
| **Unit** | milliseconds |
| **Success / direction** | Lower is better |
| **Randomization / analysis unit** | `user` (context kind `user`) |
| **Tags** | `grid-navigator`, `use-case`, `adaptive-triggers`, `latency` |

Do **not** reuse 15’s simulated latency/error event names.

### Application: `track`

On each **successful navigation** (arrow keys / WASD), the SDK **tracks** a custom event:

- Event key: `adaptive-grid-nav-latency`
- Numeric value: current **latency slider** (milliseconds)
- Context: `{ kind: "user", key: "<username>" }`

The slider does **not** change the flag. It only changes the number reported to LaunchDarkly. Login, WASD, and `variation()` stay independent of the slider except for this `track` call.

WASD must **not** be logged as SDK `variation` spam. `track` on move is the intended metric path.

### Slider (lab control)

| Control | Range | Default | Meaning |
|---------|-------|---------|---------|
| Latency | **0–500 ms** | **50** | Value sent on each `track` |

Drag **above 200** and keep navigating so events fill the **alert window**. Stay **at or below 200** to stay under the threshold.

Optional header readout: `Reported latency: {n} ms` (the slider, not measured app delay). This lab does **not** sleep on navigation; 15 already demonstrates simulated delay.

## Adaptive trigger (dashboard)

Create on the flag **Targeting** tab → **Add adaptive trigger**. Lab defaults:

| Field | Value |
|-------|--------|
| **Source** | LaunchDarkly hosted metric `adaptive-grid-nav-latency` |
| **Type** | **Constant** (not Anomaly) |
| **Condition** | **Above** |
| **Alert threshold** | **200** (ms) |
| **Alert window** | **1 minute**, or the shortest window the UI allows |
| **Switch variation to** | **`none`** |
| **Cooldown** | Document whatever the UI default is; a second fire will not happen until cooldown elapses |
| **Notifications** | Optional |

Provisioning may create the **flag** and **metric** via [rest/](rest/) / [terraform/](terraform/). Creating the **adaptive trigger** itself may remain a **UI step** if public REST only covers webhook-style [flag triggers](https://launchdarkly.com/docs/api/flag-triggers) (`turnFlagOn` / `turnFlagOff`). Do not pretend a generic trigger URL is an adaptive trigger.

After the trigger fires, targeting **stays** on `none` until someone (or a later story) changes it back. Auto-restore on recovery is **out of scope** for this spec.

## Application behavior

1. User logs in with a username (LaunchDarkly context key `user` / `key`).
2. Application evaluates `enable-adaptive-grid-highlight` with code fallback **`none`** (safety only — not the trigger outcome).
3. Header shows `Name:`, **`Flag value:`** (raw SDK string), positions. Optional: reported latency from the slider.
4. Selected cell and username use highlight color when `Flag value:` is `green`; `X` only when `none`.
5. Lab rail (web) or equivalent (console):
   - **Start live** — targeting on, default rule serves `green`.
   - **Latency slider** — 0–500 ms, default 50.
6. Each successful move: `track('adaptive-grid-nav-latency', numericValue)`.
7. Standard 00 navigation, logout (`L`), quit (`Q`).
8. Console apps re-evaluate every **500 ms**. Web apps follow streaming flag changes.

### Start live vs provisioning

| State | Flag | Default rule | Grid |
|-------|------|--------------|------|
| Fresh provision | **Off** | n/a | `none` |
| After **Start live** | **On** | serve `green` | `green` (all users) |
| After trigger fires | **On** | serve `none` | `none` |

Turning the flag **off** also yields `none` (off variation). The lesson is the **on + switched default rule**, not kill-switch.

### Single-evaluation mode

`--evaluate-once <username>` prints JSON with `flagValue` / `highlightColor` only (no `track`, no slider).

## Context

```text
{ kind: "user", key: "<username>" }
```

No extra attributes required.

## Lab Controls (optional REST)

The page / console must not hold `LD_API_ACCESS_TOKEN`. A local host may proxy:

- Start live (on + fallthrough `green`)
- Status (on/off, current fallthrough variation)

Same pattern as other 99-use-cases hosts.

## Acceptance criteria

1. Provisioning creates **`enable-adaptive-grid-highlight`** (`none` / `green`) **off**, off variation `none`.
2. Provisioning creates a custom numeric metric whose **event key** is **`adaptive-grid-nav-latency`** (unique to 16).
3. Adaptive trigger is documented as a UI step unless a supported API is found; it **switches to `none`**, constant **Above 200 ms**, short alert window.
4. Empty username rejected; grid starts at `m/m`.
5. **Start live** serves `green` for the logged-in user without a percentage rollout.
6. Slider does not change `variation()` by itself; only `track` values change.
7. Navigating with slider **> 200** for a full alert window causes LaunchDarkly to serve **`none`**; header `Flag value:` updates without reload (or within 500 ms on console).
8. Navigating with slider **≤ 200** does not switch variation (given enough quiet time / cooldown after any prior fire).
9. Observed switch is the **dashboard variation `none`**, not the SDK fallback parameter.
10. No experiment on this flag while the trigger is in use.
11. `/api/config` (if present) never includes `LD_SDK_KEY` or API tokens.

## Further reading

- [99-use-cases](../README.md)
- [14-progressive-rollout](../14-progressive-rollout/) — time-based ramp, no metric switch
- [15-guarded-rollout](../15-guarded-rollout/) — ramp + regression guardrails (different events)
- [00-reference-code/application.md](../../00-reference-code/application.md)
- [Adaptive triggers](https://launchdarkly.com/docs/home/flags/triggers)
- [Custom numeric metrics](https://launchdarkly.com/docs/home/observability/custom-numeric)
- [Sending custom events](https://launchdarkly.com/docs/sdk/features/events)
