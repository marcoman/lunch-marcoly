# Node.js (web)

Web implementation of [15-prerequisite-flags](../application.md). The Node
server SDK evaluates parent and child flags independently so an unmet
[prerequisite](https://launchdarkly.com/docs/home/flags/prereqs) shows up as
`PREREQUISITE_FAILED`.

## Prerequisites

- Node.js 20+
- `LD_SDK_KEY`
- For Controls: `LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, `LD_ENVIRONMENT_KEY`

## Run

```bash
npm install
npm start
```

Open http://127.0.0.1:8080/. Set `PORT` to use another port.

Provision the `-prereq` flags with the sibling [REST](../rest/) example.
Controls never edit the prerequisite relationship.
