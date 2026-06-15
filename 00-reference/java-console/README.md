# Java (console)

Console application version of the [00-reference grid navigator](../application.md).

## Prerequisites

- Java 21+
- Maven Wrapper included in this folder (`./mvnw`) — no system Maven install required
- macOS or Linux terminal (`stty` used for raw keyboard input)

## Environment variables

None — this example does not use LaunchDarkly yet.

## Build

From this directory:

```bash
./mvnw clean install
```

## Run

From this directory, after a successful build:

```bash
java -jar target/00-reference.jar
```

Press `q` to quit the grid screen.

## What to expect

1. Enter a username at the login prompt (empty names are rejected).
2. The grid screen shows your name, current position (`m/m` initially), and previous position (`—`).
3. Use arrow keys or WASD to move; the selected cell has a green outline and **X**.
4. Movement stops at grid edges (no wrap-around).
