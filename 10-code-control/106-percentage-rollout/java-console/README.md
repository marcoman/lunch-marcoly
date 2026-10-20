# 16-percentage-rollout — Java console

Java 21 console for a static LaunchDarkly **percentage rollout**.

Keywords: **percentage rollout** · **context key** · **sticky bucketing**

Docs: [Percentage rollouts](https://launchdarkly.com/docs/home/flags/rollouts)

## Prerequisites

- Java 21+
- macOS or Linux terminal (`stty` provides raw mode)
- `LD_SDK_KEY`

## Build and run

```bash
export LD_SDK_KEY="sdk-..."
cd 10-code-control/16-percentage-rollout/java-console
./mvnw -q -DskipTests package
java -jar target/16-percentage-rollout.jar
```

**N** / **P** walk generated usernames. **L** logs out. **Q** quits.
