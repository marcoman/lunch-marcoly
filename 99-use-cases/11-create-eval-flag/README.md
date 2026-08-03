# 11-create-eval-flag

Create **one LaunchDarkly flag**, evaluate it in the grid navigator, and change what users see by toggling the flag — in the **LaunchDarkly UI** or with a **curl** REST call.

This is the simplest use case in the repository. It teaches flag **on/off** state and **string variation** values without segments, rollouts, or experiment utilities.

See [application.md](application.md) for the full specification.

## What you are seeing

The app evaluates a single string flag — `configure-grid-selection-green-highlight` — and uses the returned value as the **highlight color** for the selected grid cell and the username in the header.

```text
Username → SDK variation() → highlight color → colored X on selected cell
```

| Flag state | Fallthrough variation | Selected cell | Header |
|------------|----------------------|---------------|--------|
| **Off** | (ignored) | Plain `X`, no color | `Name: alice (no-color)` |
| **On** | `green` | Green `X` | `Name: alice (green)` |
| **On** | `red` | Red `X` | `Name: alice (red)` |
| **On** | `yellow` | Yellow `X` | `Name: alice (yellow)` |

The header also shows **`Flag value:`** — the raw string the SDK received. When the flag is off, that value is always `none` (the off variation), even though LaunchDarkly considers the flag disabled.

The console app **re-evaluates every 500 ms**. Leave it running, toggle the flag in LaunchDarkly, and watch the highlight change within about a second — no restart required.

> **Same flag key, different examples:** [10-flag-enablement](../10-flag-enablement/) uses this key as a **boolean**. [02-segments-by-name](02-segments-by-name/) uses it as a **string** with segment targeting. Use a dedicated environment if you run multiple examples in one project.

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
# 1. Create the flag (off by default)
cd rest && chmod +x *.sh && ./create-flag.sh && cd ..

# Node.js: install shared deps for highlight-eval.js, then the app folder
cd node && npm install .. && npm install && cd ..

# 2. Run the app — plain X, no colors
cd python-console && python 11-create-eval-flag.py

# 3. Turn the flag on (green highlight)
cd ../rest && ./turn-flag-on.sh green

# 4. Log in again — selected cell and username are green

# 5. Try another color while the app is running
./set-highlight-color.sh red

# 6. Turn the flag off — back to plain X
./turn-flag-off.sh
```

Single evaluation without the interactive grid:

```bash
python 11-create-eval-flag.py --evaluate-once alice
# {"username": "alice", "flagValue": "none", "highlightColor": "none", "colorLabel": "(no-color)"}

./rest/turn-flag-on.sh blue
python 11-create-eval-flag.py --evaluate-once alice
# {"username": "alice", "flagValue": "blue", "highlightColor": "blue", "colorLabel": "(blue)"}
```

## Provisioning

| Approach | Directory |
|----------|-----------|
| REST API | [rest/](rest/) |
| Terraform | [terraform/](terraform/) |

Both create the string flag with variations `none`, `green`, `yellow`, `red`, `blue`, `purple`, and leave the flag **off** in the target environment.

## Toggle the flag in the LaunchDarkly UI

These steps mirror what the REST scripts do programmatically.

### Turn the flag **on** (green highlight)

1. Open your project in [LaunchDarkly](https://app.launchdarkly.com).
2. Go to **Flags** → **`configure-grid-selection-green-highlight`**.
3. Select the target environment (e.g. **Production**).
4. Flip the toggle to **On**.
5. Under **Default rule** (fallthrough), set the variation to **Green**.
6. **Save** targeting changes.
7. In the running console app, the selected cell and username turn **green** within ~1 second.

### Change the highlight color

1. With the flag still **On**, edit the **Default rule** fallthrough.
2. Change the variation to **Red** (or Yellow, Blue, Purple).
3. **Save**.
4. The app updates to the new color without restarting.

### Turn the flag **off** (no highlight)

1. Flip the toggle to **Off**.
2. **Save**.
3. The app returns to plain `X` with `(no-color)` — matching [00-reference-code](../00-reference-code/) styling.

When a flag is **off**, LaunchDarkly serves the **off variation** (`none`) to every context. The on-rule fallthrough is ignored.

## Toggle the flag with curl (REST API)

The [rest/](rest/) scripts wrap these calls. Below are the underlying **curl** commands so you can see exactly what LaunchDarkly receives.

Set shared variables:

```bash
export LD_API_HOST="https://app.launchdarkly.com"
export LD_API_VERSION="20240415"
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
# export LD_API_ACCESS_TOKEN="api-..."
```

### Check current state

```bash
curl -sS "${LD_API_HOST}/api/v2/flags/${LD_PROJECT_KEY}/configure-grid-selection-green-highlight" \
  -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
  -H "LD-API-Version: ${LD_API_VERSION}" \
  | jq '{
      on: .environments[env].on,
      offVariation: .variations[.environments[env].offVariation].value,
      fallthrough: .variations[.environments[env].fallthrough.variation].value
    }' --arg env "${LD_ENVIRONMENT_KEY}"
```

Or use the helper: `./rest/get-flag.sh`

### Turn the flag **on** with green fallthrough

Semantic patches require each variation's `_id` (UUID), not its index or string value. Fetch it first:

```bash
FLAG_JSON=$(curl -sS "${LD_API_HOST}/api/v2/flags/${LD_PROJECT_KEY}/configure-grid-selection-green-highlight" \
  -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
  -H "LD-API-Version: ${LD_API_VERSION}")

GREEN_ID=$(echo "${FLAG_JSON}" | jq -r '.variations[] | select(.value == "green") | ._id')

curl -sS -X PATCH "${LD_API_HOST}/api/v2/flags/${LD_PROJECT_KEY}/configure-grid-selection-green-highlight" \
  -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
  -H "LD-API-Version: ${LD_API_VERSION}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "{
    \"environmentKey\": \"${LD_ENVIRONMENT_KEY}\",
    \"comment\": \"Turn highlight flag on\",
    \"instructions\": [
      {\"kind\": \"turnFlagOn\"},
      {\"kind\": \"updateFallthroughVariationOrRollout\", \"variationId\": \"${GREEN_ID}\"}
    ]
  }" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, fallthrough}"
```

Or: `./rest/turn-flag-on.sh green`

### Change fallthrough to **red** (flag stays on)

```bash
RED_ID=$(echo "${FLAG_JSON}" | jq -r '.variations[] | select(.value == "red") | ._id')

curl -sS -X PATCH "${LD_API_HOST}/api/v2/flags/${LD_PROJECT_KEY}/configure-grid-selection-green-highlight" \
  -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
  -H "LD-API-Version: ${LD_API_VERSION}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "{
    \"environmentKey\": \"${LD_ENVIRONMENT_KEY}\",
    \"comment\": \"Change highlight to red\",
    \"instructions\": [
      {\"kind\": \"updateFallthroughVariationOrRollout\", \"variationId\": \"${RED_ID}\"}
    ]
  }" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, fallthrough}"
```

Or: `./rest/set-highlight-color.sh red`

### Turn the flag **off**

```bash
curl -sS -X PATCH "${LD_API_HOST}/api/v2/flags/${LD_PROJECT_KEY}/configure-grid-selection-green-highlight" \
  -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
  -H "LD-API-Version: ${LD_API_VERSION}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "{
    \"environmentKey\": \"${LD_ENVIRONMENT_KEY}\",
    \"comment\": \"Turn highlight flag off\",
    \"instructions\": [{\"kind\": \"turnFlagOff\"}]
  }" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, offVariation}"
```

Or: `./rest/turn-flag-off.sh`

After each curl, run `--evaluate-once` or watch the interactive app to confirm the SDK picked up the change.

## Flag key

```text
configure-grid-selection-green-highlight
```

String variations: `none`, `green`, `yellow`, `red`, `blue`, `purple`.

## Implementation

| Component | Location |
|-----------|----------|
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

All console and web apps support `--evaluate-once <username>`. Console apps re-evaluate the flag every 500 ms so UI toggles in LaunchDarkly appear without restarting.

## LaunchDarkly capabilities highlighted

- **Create a multivariate string flag** — one key, multiple color outcomes
- **Flag on/off** — off variation vs. on fallthrough
- **Server-side SDK evaluation** — `variation()` returns the resolved string for a user context
- **Live updates** — streaming SDK picks up targeting changes without redeploying the app
- **REST semantic patch** — `turnFlagOn`, `turnFlagOff`, `updateFallthroughVariationOrRollout`

## Further reading

- [application.md](application.md) — specification and acceptance criteria
- [02-segments-by-name](02-segments-by-name/) — same flag with segment-based color targeting
- [10-flag-enablement](../10-flag-enablement/) — boolean highlight flag reference
- [Flag targeting](https://launchdarkly.com/docs/home/flags/targeting-rules)
- [REST API semantic patch](https://launchdarkly.com/docs/api#updates-using-semantic-patch)
