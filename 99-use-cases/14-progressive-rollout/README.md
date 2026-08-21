# 14-progressive-rollout

Gradually release a **grid selection highlight** using a **progressive rollout** on one LaunchDarkly flag — `enable-grid-selection-highlight`.

> In this example, we have a progressive rollout over **15 minutes** in **five equal stages**: **10%**, **20%**, **40%**, **60%**, and **100%** of users receive the green highlight. Each stage lasts **3 minutes**.

See [application.md](application.md) for the full specification.

## What you are seeing

A progressive rollout is shipping code to production for everyone, but turning the new behavior on for only a small slice of users at first, then automatically expanding that slice over time.

You already deploy code continuously, but **deployment** and **release** are different concerns. A feature flag lets the code path for a new feature exist in production without being active for everyone. A progressive rollout is the release strategy on top of that flag: start at something like 10%, watch error rates and user impact, then increase to 20%, 40%, 60%, and eventually 100% if things look healthy.

This example applies that pattern to the **grid highlight color**:

```text
Username → SDK variation() → green or none → colored X or plain X
```

| Rollout stage | Green traffic | What most users see |
|---------------|---------------|---------------------|
| Stage 1 (0–3 min) | 10% | ~1 in 10 usernames get green highlight |
| Stage 2 (3–6 min) | 20% | ~1 in 5 get green |
| Stage 3 (6–9 min) | 40% | ~2 in 5 get green |
| Stage 4 (9–12 min) | 60% | ~3 in 5 get green |
| Stage 5 (12–15 min) | 100% | Everyone gets green |

LaunchDarkly assigns each username (context key) to a bucket. As the percentage increases, more buckets receive `green`. Users who already have green keep it — they do not flip back to `none`.

The header shows **`Flag value:`** — the raw string the SDK returned (`green` or `none`). The selected grid cell and username use that color.

The console app **re-evaluates every 500 ms**. Leave it running during the rollout and log in with different usernames to see who receives green.

> **Same flag key, different examples:** [10-code-control/11-flag-enablement](../../10-code-control/11-flag-enablement/) uses this key as a **boolean**. [02-segments-by-name](02-segments-by-name/) uses segment targeting. Use a dedicated environment if you run multiple examples in one project.

## Prerequisites

```bash
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"   # must match your LD_SDK_KEY environment
export LD_SDK_KEY="sdk-..."
export LD_API_ACCESS_TOKEN="api-..."     # rest/ scripts
export LD_ACCESS_TOKEN="api-..."         # terraform/
```

## Quick start

**True progressive rollout (LaunchDarkly UI — auto-advances stages):**

```bash
# 1. Create the flag (off by default)
cd rest && chmod +x *.sh && ./create-flag.sh && cd ..

# 2. Terminal A — run the monitor (samples every 30s)
python3 14-progressive-rollout-monitor.py

# 3. Terminal B — prepare targeting JSON and complete rollout in the UI
cd rest && ./configure-progressive-rollout.sh
# Default rule → Progressive rollout in LaunchDarkly (see below)
./get-progressive-rollout.sh   # verify progressiveRollout / progressiveRolloutConfig

# 4. Terminal C — run the app and try different usernames
cd python-console && python 14-progressive-rollout.py
```

**Simulate stage timing via REST (manual percentage updates — not a UI progressive rollout):**

```bash
cd rest && ./start-progressive-rollout.sh   # 10→20→40→60→100%, 3 min each
```

LaunchDarkly's public REST API does **not** start progressive rollouts programmatically — `progressiveRolloutConfig` is ignored on semantic patch. The monitor detects the difference: `progressive stage N` (UI) vs `simulated stage N — REST percentage`.

Single evaluation without the interactive grid:

```bash
python python-console/14-progressive-rollout.py --evaluate-once rollout-probe-001-00
# {"username": "rollout-probe-001-00", "flagValue": "none", "highlightColor": "none", ...}

./rest/set-rollout-percent.sh 40
python python-console/14-progressive-rollout.py --evaluate-once rollout-probe-001-00
# may return green or none depending on bucket
```

## Monitor script

[14-progressive-rollout-monitor.py](14-progressive-rollout-monitor.py) exercises the application and reports what the SDK returns:

- Prints the **start timestamp** when monitoring begins (e.g. `[14:45:34]`)
- Runs a batch of **20 evaluations** every **30 seconds**
- Each batch line includes **elapsed time** since start (e.g. `[14:45:54 - 00m20s]`)
- Queries LaunchDarkly for the **current rollout stage** via REST
- Distinguishes **UI progressive rollout** (`progressiveRollout`), **REST-simulated** percentage stages, and **guarded rollout** (`measuredRollout` — wrong use case)
- Shows an **inline countdown** between batches to conserve terminal space

Example output:

```text
Test: 14-progressive-rollout-monitor
Flag: enable-grid-selection-highlight

Progressive rollout: 15 minutes, 5 equal stages (3 min each)
  ...

Monitoring every 30s — 20 evaluations per batch (green highlight vs none).
Press Ctrl+C to stop.
[14:45:34]

[14:45:37 - 00m03s] batch   1: green=2, none=18, observed 10% (progressive stage 1, target 10%, current 10%)
[14:46:07 - 00m33s] batch   2: green=4, none=16, observed 20% (progressive stage 2, target 20%, current 20%)

# When using ./start-progressive-rollout.sh instead:
[14:45:37 - 00m03s] batch   1: green=2, none=18, observed 10% (simulated stage 1, target 10%, configured 10% — REST percentage, not UI progressive)
```

```bash
python3 14-progressive-rollout-monitor.py

# Custom app command (e.g. Go binary)
python3 14-progressive-rollout-monitor.py --app-cmd ./go/14-progressive-rollout

# Run exactly 5 batches then exit
python3 14-progressive-rollout-monitor.py --batches 5
```

## Provisioning

| Approach | Directory |
|----------|-----------|
| REST API | [rest/](rest/) |
| Terraform | [terraform/](terraform/) |

Both create the string flag with variations `none`, `green`, and other colors, and leave the flag **off** in the target environment.

## Configure progressive rollout in the LaunchDarkly UI

LaunchDarkly's public REST API does **not** start progressive rollouts programmatically. Use `./configure-progressive-rollout.sh` to prepare the flag and emit targeting JSON — then finish in the UI:

```bash
cd rest && ./configure-progressive-rollout.sh
./get-progressive-rollout.sh   # verify progressive-rollout state
```

The script turns the flag on with off variation `none` and writes `progressive-rollout-targeting.json` for the JSON targeting editor. Complete the progressive rollout in the UI:

| Setting | Value |
|---------|-------|
| From | `none` (no highlight — fallback for users not yet in rollout) |
| To | `green` |
| Context kind | `user` |
| Duration | 15 minutes (5 stages × 3 minutes) |
| Stages | 10%, 20%, 40%, 60%, 100% |

Or configure manually in the UI:

1. Open your project in [LaunchDarkly](https://app.launchdarkly.com).
2. Go to **Flags** → **`enable-grid-selection-highlight`**.
3. Select the target environment (e.g. **Production**).
4. Flip the toggle to **On**.
5. Under **Default rule**, select **Progressive rollout**.
6. Configure:
   - **From:** `none` (No highlight)
   - **To:** `green` (Green)
   - **Context kind:** `user`
   - **Custom duration:** 15 minutes
   - **5 stages:** 10%, 20%, 40%, 60%, 100%
7. **Save** targeting changes.
8. Watch the monitor script or log in with different usernames as LaunchDarkly auto-advances the percentage.

The monitor and `./get-progressive-rollout.sh` detect an active UI progressive rollout via `fallthrough.rollout.experimentAllocation.type == "progressiveRollout"` or `fallthrough.progressiveRolloutConfig`.

To stop early: click **Stop** on the progressive rollout and choose which variation all traffic should receive (`none` or `green`).

> **Not guarded rollout:** If the monitor reports `guarded rollout detected`, you configured [15-guarded-rollout](../15-guarded-rollout/) (`measuredRollout`) instead of progressive rollout.

## REST scripts (simulation and inspection)

The [rest/](rest/) scripts inspect rollout state and can **simulate** stage timing with manual percentage updates. Use `configure-progressive-rollout.sh` to prepare for a UI progressive rollout, or `start-progressive-rollout.sh` to step through percentages without LaunchDarkly auto-advance.

Set shared variables:

```bash
export LD_API_HOST="https://app.launchdarkly.com"
export LD_API_VERSION="20240415"
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
# export LD_API_ACCESS_TOKEN="api-..."
```

### Prepare progressive rollout (targeting JSON)

```bash
./rest/configure-progressive-rollout.sh
./rest/get-progressive-rollout.sh
```

### Simulate percentage stages (not a UI progressive rollout)

```bash
./rest/start-progressive-rollout.sh
```

This turns the flag on and advances through 10% → 20% → 40% → 60% → 100%, waiting 3 minutes between stages. LaunchDarkly does **not** auto-advance these stages — the script updates `rolloutWeights` manually.

### Set a specific rollout percentage

```bash
./rest/set-rollout-percent.sh 40   # 40% green, 60% none
./rest/get-flag.sh                 # inspect current state
./rest/stop-rollout.sh             # turn flag off
```

### Set 40% green via curl directly

Semantic patches require variation `_id` UUIDs:

```bash
FLAG_JSON=$(curl -sS "${LD_API_HOST}/api/v2/flags/${LD_PROJECT_KEY}/enable-grid-selection-highlight" \
  -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
  -H "LD-API-Version: ${LD_API_VERSION}")

GREEN_ID=$(echo "${FLAG_JSON}" | jq -r '.variations[] | select(.value == "green") | ._id')
NONE_ID=$(echo "${FLAG_JSON}" | jq -r '.variations[] | select(.value == "none") | ._id')

curl -sS -X PATCH "${LD_API_HOST}/api/v2/flags/${LD_PROJECT_KEY}/enable-grid-selection-highlight" \
  -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
  -H "LD-API-Version: ${LD_API_VERSION}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "{
    \"environmentKey\": \"${LD_ENVIRONMENT_KEY}\",
    \"comment\": \"Progressive rollout: 40% green\",
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

Weights are in **thousandths of a percent** (40000 = 40%).

Or: `./rest/set-rollout-percent.sh 40`

After each curl, run `--evaluate-once` or watch the monitor script to confirm the SDK picked up the change.

## Flag key

```text
enable-grid-selection-highlight
```

Rollout uses `none` (no highlight) and `green` (green highlight).

## Implementation

| Component | Location |
|-----------|----------|
| Rollout config + REST helpers | [progressive_rollout_common.py](progressive_rollout_common.py) |
| Monitor script | [14-progressive-rollout-monitor.py](14-progressive-rollout-monitor.py) |
| Evaluation logic | [highlight_eval.py](highlight_eval.py), [highlight-eval.js](highlight-eval.js) |
| REST scripts | [rest/](rest/) |
| Terraform | [terraform/](terraform/) |

## Language implementations

| Language | Directory | Application type |
|----------|-----------|------------------|
| Python | [python-console/](python-console/) | Console |
| Python | [python/](python/) | Web |
| Node.js | [node-console/](node-console/) | Console |
| Node.js | [node/](node/) | Web |
| Java | [java-console/](java-console/) | Console |
| Java | [java/](java/) | Web |
| Go | [go/](go/) | Console |
| Rust | [rust/](rust/) | Console |
| C++ | [cpp/](cpp/) | Console |

All console and web apps support `--evaluate-once <username>`. Console apps re-evaluate the flag every 500 ms.

## LaunchDarkly capabilities highlighted

- **Progressive rollout** — gradually increase traffic to a new variation over time
- **Percentage rollout** — bucket users by context key; weights in thousandths of a percent
- **String flag evaluation** — `variation()` returns `green` or `none` per user
- **Live updates** — streaming SDK picks up rollout changes without redeploying
- **REST semantic patch** — `turnFlagOn`, `updateFallthroughVariationOrRollout` with `rolloutWeights`

## Further reading

- [application.md](application.md) — specification and acceptance criteria
- [11-create-eval-flag](11-create-eval-flag/) — same flag with single-variation fallthrough
- [01-abcd-test](01-abcd-test/) — static percentage rollout across four label variations
- [Progressive rollouts](https://launchdarkly.com/docs/home/releases/progressive-rollouts)
- [REST API semantic patch](https://launchdarkly.com/docs/api#updates-using-semantic-patch)
