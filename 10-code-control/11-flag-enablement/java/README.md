# Java (web)

Web application version of the [10-flag-enablement grid navigator](../application.md).

## Prerequisites

- Java **21+**
- LaunchDarkly flags provisioned and `LD_SDK_KEY` set

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_SDK_KEY` | Yes | Server-side SDK key for flag evaluation |

## Build

```bash
./mvnw clean package
```

## Run

```bash
java -jar target/10-flag-enablement.jar
```

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/).

## What to expect

Same as [python/README.md](../python/README.md).
