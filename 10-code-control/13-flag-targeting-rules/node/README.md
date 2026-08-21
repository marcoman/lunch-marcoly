# Node.js (web)

Web implementation of [13-flag-targeting-rules](../application.md). It evaluates
the string flag against a public `team` context attribute and exposes Controls
for flag on/off and fallthrough only.

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

The `team` attribute is omitted for **No team**. Provision targeting rules with
the sibling [Terraform](../terraform/) or [REST](../rest/) example.
