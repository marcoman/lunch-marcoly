# Java (web)

Web application version of the [101-flag-enablement grid navigator](../application.md).

## Prerequisites

- Java **21+**
- LaunchDarkly flags provisioned and `LD_SDK_KEY` set

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_SDK_KEY` | Yes | Server-side SDK key for flag evaluation |
| `PORT` | No | Listen port (default `8080`; Java portal uses `8112`) |

## Build

```bash
./mvnw clean package
```

## Run

```bash
java -jar target/101-flag-enablement.jar
```

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/).

## What to expect

Same grid as [python/README.md](../python/README.md). After login, the lab drawer
opens on **Code Example**: the trimmed context, flag evaluation, and grid
response from `FlagEvaluator` and `HostOs`. **About** explains the flags.

Feature flags — evaluating variations:
<https://launchdarkly.com/docs/sdk/features/evaluating>
