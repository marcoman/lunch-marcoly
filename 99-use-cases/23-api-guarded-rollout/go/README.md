# Go

Console application for [23-api-guarded-rollout](../application.md).

## Build

```bash
go mod tidy
go build -o 23-api-guarded-rollout .
```

## Run

```bash
go run .
./23-api-guarded-rollout --evaluate-once alice
```

Re-evaluates every 500 ms. Start the guarded release from a web grid. This process only reads the variation.
