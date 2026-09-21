# 16-percentage-rollout — Java web

Java 21 web implementation of [16-percentage-rollout](../application.md).

Keywords: **percentage rollout** · **context key** · **sticky bucketing**

Docs: [Percentage rollouts](https://launchdarkly.com/docs/home/flags/rollouts)

## Run

```bash
export LD_SDK_KEY="sdk-..."
cd 10-code-control/16-percentage-rollout/java
./mvnw -q -DskipTests package
java -jar target/16-percentage-rollout.jar
```

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/). `PORT` overrides the
default. The Java portal tab 16 uses **:8162**.

Provision the dedicated `pct` flag with the sibling [REST](../rest/) example.
