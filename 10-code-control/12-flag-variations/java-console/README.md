# Java (console)

Console application version of the [11-flag-variations grid navigator](../application.md).

## Prerequisites

- Java **21+**
- macOS or Linux terminal (`stty` for raw mode)
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
java -jar target/11-flag-variations.jar
```

## What to expect

Same flag behavior as [python-console/11-flag-variations.py](../python-console/11-flag-variations.py). Press `L` to log out or `Q` to quit.
