# Java (console)

Console grid navigator for [15-guarded-rollout](../application.md).

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
java -jar target/15-guarded-rollout.jar
```

With the flag **off** (default after provisioning), the selected cell shows plain `X` and the header label is `(no-color)`.

Single evaluation:

```bash
java -jar target/15-guarded-rollout.jar --evaluate-once alice
```

The app re-evaluates the flag every 500 ms — toggle it in LaunchDarkly while the grid is open to see changes without restarting.

Press `L` to log out or `Q` to quit.
