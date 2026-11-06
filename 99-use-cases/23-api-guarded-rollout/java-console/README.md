# Java (console)

Console grid navigator for [23-api-guarded-rollout](../application.md).

## Prerequisites

- Java **21+**
- macOS or Linux terminal (`stty` for raw mode)
- `LD_SDK_KEY` for the target environment

## Build

```bash
./mvnw clean package
```

## Run

```bash
java -jar target/23-api-guarded-rollout.jar
```

With the flag **off** (default after provisioning), the selected cell shows plain `X` and the header label is `(no-color)`.

Single evaluation:

```bash
java -jar target/23-api-guarded-rollout.jar --evaluate-once alice
```

The app re-evaluates every 500 ms. Start the guarded release from a web grid. This process only reads the variation.

Press `L` to log out or `Q` to quit.
