# Java (console)

Console application version of the [02-segments-by-name grid navigator](../application.md).

## Prerequisites

- Java **21+**
- macOS or Linux terminal (`stty` for raw mode)
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

## What to expect

Same flag behavior as [python-console/02-segments-by-name.py](../python-console/02-segments-by-name.py). Header shows `Name: {username} ({segment-label})` with highlight color from `configure-grid-selection-green-highlight`. Press `L` to log out or `Q` to quit.
