# Node.js (console)

Console grid navigator for [22-api-progressive-rollout](../application.md).

## Run

```bash
npm install
npm start
```

Re-evaluates every 500 ms. Start the release from the web grid or `rest/start-progressive-release.sh`. This process only reads the variation.

```bash
node 22-api-progressive-rollout.js --evaluate-once alice
```
