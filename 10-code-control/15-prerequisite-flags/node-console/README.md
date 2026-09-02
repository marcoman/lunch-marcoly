# Node.js (console)

Console application for [15-prerequisite-flags](../application.md). The SDK
evaluates parent and child flags independently so an unmet
[prerequisite](https://launchdarkly.com/docs/home/flags/prereqs) shows up as
`PREREQUISITE_FAILED`.

## Prerequisites

- Node.js 20+
- Provisioned `-prereq` flags and `LD_SDK_KEY`

## Run

```bash
npm install
node 15-prerequisite-flags.js
```

Login with a username. Flag changes refresh about every 500 ms. Count appears
only when the child variation is `true`. Press `L` to log out or `Q` to quit.
