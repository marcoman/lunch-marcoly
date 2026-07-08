# Java (web)

Web grid navigator for [15-guarded-rollout](../application.md).

## Prerequisites

- Java **21+**
- `LD_SDK_KEY` for the target environment

## Build

```bash
./mvnw clean package
```

## Run

```bash
java -jar target/15-guarded-rollout.jar
```

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/).

The page polls the flag every 500 ms — toggle it in LaunchDarkly (UI or curl) to see highlight changes without restarting.

Single evaluation:

```bash
java -jar target/15-guarded-rollout.jar --evaluate-once alice
```
