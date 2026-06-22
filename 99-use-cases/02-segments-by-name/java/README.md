# Java (web)

Web application version of the [02-segments-by-name grid navigator](../application.md).

## Prerequisites

- Java **21+**
- LaunchDarkly segments + flag provisioned and `LD_SDK_KEY` set

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
java -jar target/02-segments-by-name.jar
```

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/).

## What to expect

Same as [python-console/02-segments-by-name.py](../python-console/02-segments-by-name.py): segment context attributes drive highlight color from `configure-grid-selection-green-highlight`. Header shows `Name: {username} ({segment-label})`.
