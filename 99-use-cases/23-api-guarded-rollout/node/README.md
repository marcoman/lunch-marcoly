# Node web — 23-api-guarded-rollout

Grid navigator for [23-api-guarded-rollout](../application.md).

The page evaluates `api-guarded-grid-highlight`. **Start guarded release** POSTs the environment release with the three guardrail metrics. The latency slider is the value sent for a `RULE_MATCH` green username.

```bash
npm install
npm start
```

Open http://127.0.0.1:8785/ . `PORT` overrides the listen port.

```bash
node 23-api-guarded-rollout.js --evaluate-once alice
```

[Environment releases (beta)](https://launchdarkly.com/docs/api/environment-releases)
