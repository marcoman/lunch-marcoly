# Python (web)

Web application for [12-flag-variations](../application.md) with an in-app **LaunchDarkly lab** (Controls / Context / About) and bottom **Trace** dock — same permanent layout as [11-flag-enablement/python](../../11-flag-enablement/python/).

## Prerequisites

- Python 3.12+ with repository virtual environment activated
- Provisioned flags and `LD_SDK_KEY`
- For **Controls** (REST on/off + fallthrough): `LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, `LD_ENVIRONMENT_KEY`

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_SDK_KEY` | Yes | Server-side SDK key |
| `LD_API_ACCESS_TOKEN` | For lab Controls | REST API token (`turnFlagOn` / `turnFlagOff` / fallthrough) |
| `LD_PROJECT_KEY` | For Controls | Project key |
| `LD_ENVIRONMENT_KEY` | For Controls | Environment key |
| `PORT` | No | Listen port (default `8080`; portal often uses `8120`) |

## Build

No compile step.

## Run

```bash
python 12-flag-variations.py
```

Open http://127.0.0.1:8080/

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
