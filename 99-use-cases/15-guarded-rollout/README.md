# 15-guarded-rollout

Gradually release a **green grid highlight** using a **guarded rollout** on one LaunchDarkly flag — `configure-grid-selection-green-highlight`.

> In this example, we have a guarded rollout over **12 minutes** in **four equal stages**: **10%**, **20%**, **30%**, and **50%** of users receive the green highlight. Each stage lasts **3 minutes**.

See [application.md](application.md) for the full specification.

## What you are seeing

A guarded rollout is a progressive rollout with monitoring and automated safety checks built in. It still ramps traffic up gradually, but it also watches selected metrics while the rollout is happening and can pause or roll back if the new variation performs worse.

You already understand progressive rollout as “release to 10%, then 20%, then 30%, then 50%.” A guarded rollout adds feedback control to that process. Instead of a human watching dashboards and deciding whether to continue, LaunchDarkly monitors metrics like error rate, latency, and movement during each step and looks for regressions compared to the original variation.

This example applies that pattern to the **grid highlight color**:

```text
Username → SDK variation() → green or none → colored X or plain X
```

When the flag serves **`green`**, the application simulates real-world release risk:

| Guardrail | Simulated behavior | Failure threshold |
|-----------|-------------------|-------------------|
| **Latency** | Random 0–1000 ms delay on each navigation | >10% of moves exceed **200 ms** |
| **Error rate** | 5% chance of incorrect highlight color | **0%** — any wrong color fails |
| **Movement** | Test harness performs **5 navigations** per user | **≥1** navigation required; 5% of tests skip navigation |

| Rollout stage | Green traffic | What most users see |
|---------------|---------------|---------------------|
| Stage 1 (0–3 min) | 10% | ~1 in 10 usernames get green + guardrails |
| Stage 2 (3–6 min) | 20% | ~1 in 5 get green |
| Stage 3 (6–9 min) | 30% | ~3 in 10 get green |
| Stage 4 (9–12 min) | 50% | Half get green |

LaunchDarkly assigns each username (context key) to a bucket. As the percentage increases, more buckets receive `green`. Users who already have green keep it.

The header shows **`Flag value:`** — the raw string the SDK returned (`green` or `none`).

> **Same flag key, different examples:** [10-flag-enablement](../10-flag-enablement/) uses this key as a **boolean**. [02-segments-by-name](02-segments-by-name/) uses segment targeting. Use a dedicated environment if you run multiple examples in one project.

## Prerequisites

```bash
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"   # must match your LD_SDK_KEY environment
export LD_SDK_KEY="sdk-..."
export LD_API_ACCESS_TOKEN="api-..."     # rest/ scripts
export LD_ACCESS_TOKEN="api-..."         # terraform/
```

## Quick start

```bash
# 1. Create the flag and guardrail metrics (off by default)
cd rest && chmod +x *.sh && ./create-flag.sh && ./create-metrics.sh && cd ..

# 2. Terminal A — run the monitor (exercises guardrails every 30s)
python3 15-guarded-rollout-monitor.py

# 3. Terminal B — prepare metrics and configure guarded rollout in the UI
cd rest && ./configure-guarded-rollout.sh
# Then complete Default rule → Guarded rollout in LaunchDarkly (see below)

# 4. Terminal C — run the app and navigate with arrow keys / WASD
cd python-console && python 15-guarded-rollout.py
```

Exercise one user session (5 navigations, guardrail metrics):

```bash
python python-console/15-guarded-rollout.py --exercise-once guard-probe-001-00
# {"navigations": 5, "latencyMs": [...], "latencyFailure": false, "colorErrors": 0, ...}

python python-console/15-guarded-rollout.py --exercise-once guard-probe-001-00 --skip-navigation
# {"navigations": 0, "movementFailure": true, ...}
```

## Monitor script

[15-guarded-rollout-monitor.py](15-guarded-rollout-monitor.py) exercises guardrails and reports batch metrics:

- Prints **Test:** `15-guarded-rollout-monitor` and **Flag:** `configure-grid-selection-green-highlight`
- Runs **20 exercises** per batch every **30 seconds**
- Each exercise performs **5 navigations** (5% randomly skip navigation)
- Reports `latencyFail`, `errorFail`, `movementFail` counts per batch
- Queries LaunchDarkly for the **current guarded-rollout stage** via REST (`expand=guardedRollout`)

Example output:

```text
Test: 15-guarded-rollout-monitor
Flag: configure-grid-selection-green-highlight

Guarded rollout: 12 minutes, 4 equal stages (3 min each)
  ...

Monitoring every 30s — 20 exercises per batch.
Press Ctrl+C to stop.
[15:01:34]

[15:01:58 - 00m24s] batch   1: green=2, latencyFail=0/20, errorFail=1/20, movementFail=1/20, skippedNav=1/20 (guarded stage 1, target 10%, current 10%, status monitoring)
```

```bash
python3 15-guarded-rollout-monitor.py
python3 15-guarded-rollout-monitor.py --batches 5
```

## Provisioning

| Approach | Directory |
|----------|-----------|
| REST API | [rest/](rest/) |
| Terraform | [terraform/](terraform/) |

Both create the string flag with variations `none`, `green`, and other colors, and leave the flag **off** in the target environment. Terraform also creates the three guardrail metrics.

## Configure guarded rollout in the LaunchDarkly UI

LaunchDarkly's public REST API does **not** start guarded rollouts programmatically. Use `./configure-guarded-rollout.sh` to create metrics, prepare the flag, and emit targeting JSON — then finish in the UI:

```bash
cd rest && ./configure-guarded-rollout.sh
./get-guarded-rollout.sh   # verify guarded-rollout state
```

The script creates the three guardrail metrics (if needed), turns the flag on with off variation `none`, and writes `guarded-rollout-targeting.json` for the JSON targeting editor. Complete the guarded rollout in the UI:

| Setting | Value |
|---------|-------|
| From | `none` (no highlight — fallback for users not yet in rollout) |
| To | `green` |
| Context kind | `user` |
| Duration | 12 minutes (4 stages × 3 minutes) |
| Stages | 10%, 20%, 30%, 50% |
| Metrics | `grid-nav-latency`, `grid-highlight-error-rate`, `grid-nav-movement` |
| Auto-rollback | enabled |

Or configure manually in the UI:

1. Open your project in [LaunchDarkly](https://app.launchdarkly.com).
2. Go to **Flags** → **`configure-grid-selection-green-highlight`**.
3. Select the target environment (e.g. **Production**).
4. Flip the toggle to **On**.
5. Under **Default rule**, select **Guarded rollout**.
6. Configure:
   - **From:** `none` (No highlight)
   - **To:** `green` (Green)
   - **Context kind:** `user`
   - **Custom duration:** 12 minutes
   - **4 stages:** 10%, 20%, 30%, 50%
7. Add **guardrail metrics** (create with `./rest/create-metrics.sh` or Terraform, then attach in the UI):

   | Metric key | Event key | Threshold |
   |------------|-----------|-----------|
   | `grid-nav-latency` | `grid-navigation-latency` | 200 ms |
   | `grid-highlight-error-rate` | `grid-highlight-color-error` | 0% errors |
   | `grid-nav-movement` | `grid-navigation-count` | 1 navigation |

8. **Save** targeting changes.

If a guardrail fails during the rollout, LaunchDarkly can pause or roll back automatically (depending on your project settings).

To stop early: click **Stop** on the guarded rollout and choose which variation all traffic should receive.

## REST scripts (metrics, simulation, inspection)

The [rest/](rest/) scripts create metrics and inspect rollout state. Use `configure-guarded-rollout.sh` to prepare for a UI guarded rollout, or `start-guarded-rollout.sh` to simulate percentage stages without LaunchDarkly monitoring.

Set shared variables:

```bash
export LD_API_HOST="https://app.launchdarkly.com"
export LD_API_VERSION="20240415"
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
# export LD_API_ACCESS_TOKEN="api-..."
```

### Prepare guarded rollout (metrics + targeting JSON)

```bash
./rest/configure-guarded-rollout.sh
./rest/get-guarded-rollout.sh
```

### Simulate percentage stages (not a real guarded rollout)

```bash
./rest/start-guarded-rollout.sh
```

### Set a specific rollout percentage

```bash
./rest/set-rollout-percent.sh 40   # 40% green, 60% none
./rest/get-flag.sh                 # inspect current state
./rest/stop-rollout.sh             # turn flag off
```

### Set 40% green via curl directly

```bash
FLAG_JSON=$(curl -sS "${LD_API_HOST}/api/v2/flags/${LD_PROJECT_KEY}/configure-grid-selection-green-highlight" \
  -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
  -H "LD-API-Version: ${LD_API_VERSION}")

GREEN_ID=$(echo "${FLAG_JSON}" | jq -r '.variations[] | select(.value == "green") | ._id')
NONE_ID=$(echo "${FLAG_JSON}" | jq -r '.variations[] | select(.value == "none") | ._id')

curl -sS -X PATCH "${LD_API_HOST}/api/v2/flags/${LD_PROJECT_KEY}/configure-grid-selection-green-highlight" \
  -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
  -H "LD-API-Version: ${LD_API_VERSION}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "{
    \"environmentKey\": \"${LD_ENVIRONMENT_KEY}\",
    \"comment\": \"Guarded rollout: 40% green\",
    \"instructions\": [
      {\"kind\": \"turnFlagOn\"},
      {
        \"kind\": \"updateFallthroughVariationOrRollout\",
        \"rolloutContextKind\": \"user\",
        \"rolloutWeights\": {
          \"${GREEN_ID}\": 40000,
          \"${NONE_ID}\": 60000
        }
      }
    ]
  }" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, fallthrough}"
```

Or: `./rest/set-rollout-percent.sh 40`

## Flag key

```text
configure-grid-selection-green-highlight
```

Rollout uses `none` (no highlight) and `green` (green highlight).

## Implementation

| Component | Location |
|-----------|----------|
| Guardrail simulation | [guarded_behavior.py](guarded_behavior.py), [guarded-behavior.js](guarded-behavior.js) |
| Metric events + tracking | [metric_events.py](metric_events.py) |
| Rollout config + REST helpers | [guarded_rollout_common.py](guarded_rollout_common.py) |
| Monitor script | [15-guarded-rollout-monitor.py](15-guarded-rollout-monitor.py) |
| Evaluation logic | [highlight_eval.py](highlight_eval.py), [highlight-eval.js](highlight-eval.js) |
| REST scripts | [rest/](rest/) |
| Terraform | [terraform/](terraform/) |

## Language implementations

| Language | Directory | Guardrails in interactive app |
|----------|-----------|------------------------------|
| Python | [python-console/](python-console/) | Yes — latency delay + color errors |
| Python | [python/](python/) | Web UI (evaluate only) |
| Node.js | [node-console/](node-console/) | Evaluate; exercise via python-console |
| Node.js | [node/](node/) | Web |
| Java | [java-console/](java-console/) | Evaluate |
| Java | [java/](java/) | Web |
| Go | [go/](go/) | Evaluate |
| Rust | [rust/](rust/) | Evaluate |
| C++ | [cpp/](cpp/) | Evaluate |

Full guardrail exercise (`--exercise-once`) is implemented in **python-console**. The monitor script uses it by default.

## LaunchDarkly capabilities highlighted

- **Guarded rollout** — progressive release with metric guardrails and auto-rollback
- **Percentage rollout** — bucket users by context key
- **String flag evaluation** — `variation()` returns `green` or `none` per user
- **REST semantic patch** — configure rollout percentages via curl

## Further reading

- [application.md](application.md) — specification and acceptance criteria
- [14-progressive-rollout](../14-progressive-rollout/) — same schedule without guardrails
- [11-create-eval-flag](../11-create-eval-flag/) — single-variation fallthrough
- [Guarded rollouts](https://launchdarkly.com/docs/home/releases/guarded-rollouts)
- [REST API semantic patch](https://launchdarkly.com/docs/api#updates-using-semantic-patch)
