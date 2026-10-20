# Node.js (console)

Console application for [14-multi-context-targeting](../application.md). It
evaluates `show-partner-org-badge` against a
[multi-context](https://launchdarkly.com/docs/home/flags/multi-contexts)
(`user` + `organization`).

## Prerequisites

- Node.js 20 LTS+
- Provisioned flag and `LD_SDK_KEY`

This console app evaluates the flag but has no web lab or REST Controls UI.

## Build and run

```bash
npm install
npm start
```

Choose Alice/Bob and Acme/Globex at login. On the grid, `1`/`2` switch user and
`3`/`4` switch org without logging out. The badge refreshes about every 500 ms.
Press `L` to log out or `Q` to quit.
