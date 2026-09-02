# Node.js (web)

Web implementation of [14-multi-context-targeting](../application.md). It
evaluates `show-partner-org-badge` against a
[multi-context](https://launchdarkly.com/docs/home/flags/multi-contexts)
(`user` + `organization`) and exposes Controls for flag on/off and fallthrough
only.

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

Org is a separate context kind, not a user attribute. Provision the AND rules
with the sibling [REST](../rest/) example.

```bash
python ../collect-results.py --url http://127.0.0.1:8080
```
