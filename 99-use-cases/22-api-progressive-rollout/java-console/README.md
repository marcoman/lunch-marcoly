# Java (console)

Console grid navigator for [22-api-progressive-rollout](../application.md).

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
java -jar target/22-api-progressive-rollout.jar
```

With the flag **off** (default after provisioning), the selected cell shows plain `X` and the header label is `(no-color)`.

Single evaluation:

```bash
java -jar target/22-api-progressive-rollout.jar --evaluate-once alice
```

The app re-evaluates every 500 ms. Start the release from the web grid or `rest/start-progressive-release.sh`. This process only reads the variation.

Press `L` to log out or `Q` to quit.
