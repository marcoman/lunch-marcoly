# Java (web)

Web application version of the [00-reference grid navigator](../application.md).

## Prerequisites

- Java 21+
- Maven Wrapper included in this folder (`./mvnw`) — no system Maven install required

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

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/) in a browser. Press Ctrl+C to stop the server.

## What to expect

1. Enter a username on the login screen (empty names are rejected).
2. The grid screen shows your name, current position (`m/m` initially), and previous position (`—`).
3. Use arrow keys or WASD to move; the selected cell has a green background and **X**.
4. Movement stops at grid edges (no wrap-around).
