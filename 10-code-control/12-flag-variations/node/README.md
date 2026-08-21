# Node.js (web)

Web application for [12-flag-variations](../application.md) with an in-app **LaunchDarkly lab** (Controls / Context / About) and bottom **Trace** dock — same permanent layout as [11-flag-enablement/node](../../11-flag-enablement/node/).

## Prerequisites

- Node.js **20 LTS+** via [nvm](https://github.com/nvm-sh/nvm) (see [root README](../../../README.md#building-code))
- Provisioned flags and `LD_SDK_KEY`
- For **Controls** (REST on/off + fallthrough): `LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, `LD_ENVIRONMENT_KEY`

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_SDK_KEY` | Yes | Server-side SDK key |
| `LD_API_ACCESS_TOKEN` | For lab Controls | REST API token (`turnFlagOn` / `turnFlagOff` / fallthrough) |
| `LD_PROJECT_KEY` | For Controls | Project key |
| `LD_ENVIRONMENT_KEY` | For Controls | Environment key |
| `LD_API_HOST` | No | LaunchDarkly API host (default `https://app.launchdarkly.com`) |
| `PORT` | No | Listen port (default `8080`; portal often uses `8120`) |

## Build

```bash
npm install
```

## Run

```bash
node 12-flag-variations.js
# or
npm start
```

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/).

## What to expect

1. Dark shell matching 11: grid left, **LD lab** right, **Trace** full-width bottom (always visible after login).
2. `/api/flags` returns `countLabel`, `luckyNumber`, `maxMoves`, `osEmoji`, plus `ldContext` for the Context tab.
3. **Controls** lists all four flags with on/off toggles. String / number / JSON flags also get a **Fallthrough** selector (existing variations only).
4. Trace appends full REST sentences and SDK evaluation updates.

Flag keys (unchanged):

```text
show-anonymous-host-os-emoji
configure-navigation-count-label
configure-lucky-number
configure-max-navigation-moves
```
