# Node.js (console)

Console application version of the [12-flag-variations grid navigator](../application.md).

## Prerequisites

- Node.js **20 LTS+** via [nvm](https://github.com/nvm-sh/nvm)
- LaunchDarkly flags provisioned and `LD_SDK_KEY` set

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_SDK_KEY` | Yes | Server-side SDK key for flag evaluation |

## Flags

- `show-anonymous-host-os-emoji` — **Boolean**, evaluated with an anonymous context and private `hostOs`; gates the OS emoji.
- `configure-navigation-count-label` — **String**; supplies the always-visible move counter label.
- `configure-lucky-number` — **Number**; supplies `Lucky Number is: N`.
- `configure-max-navigation-moves` — **JSON** (`{"maxMoves": N}`); caps successful moves per session.

This is a console app; it evaluates flags but does not include the web lab or REST Controls UI.

## Build

```bash
npm install
```

## Run

```bash
node 12-flag-variations.js
```

## What to expect

Same flag behavior as [python-console/12-flag-variations.py](../python-console/12-flag-variations.py). Press `L` to log out or `Q` to quit.
