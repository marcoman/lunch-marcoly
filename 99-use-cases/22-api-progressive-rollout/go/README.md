# Go

Console application for [22-api-progressive-rollout](../application.md).

## Build

```bash
go mod tidy
go build -o 22-api-progressive-rollout .
```

## Run

```bash
go run .
./22-api-progressive-rollout --evaluate-once alice
```

Re-evaluates every 500 ms. Start the release from the web grid or `rest/start-progressive-release.sh`. This process only reads the variation.
