# Java (console)

Console application for [15-prerequisite-flags](../application.md). The
LaunchDarkly Java server SDK evaluates parent and child flags independently so
an unmet [prerequisite](https://launchdarkly.com/docs/home/flags/prereqs)
shows up as `PREREQUISITE_FAILED`.

## Prerequisites

- Java 21+
- macOS or Linux terminal (`stty` provides raw mode)
- Provisioned `-prereq` flags and `LD_SDK_KEY`

This console app evaluates the flags but has no web lab or REST Controls UI.

## Build and run

```bash
./mvnw -q -DskipTests package
java -jar target/15-prerequisite-flags.jar
```

Login with a username. Flag changes refresh about every 500 ms. Count appears
only when the child variation is `true`. Press `L` to log out or `Q` to quit.
