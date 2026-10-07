# Java web

Same three-column briefing as [Python](../python/). **Generate AI Report** runs AgentControl, Separate flags, and JSON flag.

There is no official Java AI SDK. This port evaluates the completion config, the judge config, and the feature flags with `jsonValueVariationDetail`, `stringVariationDetail`, and `boolVariationDetail`. The app substitutes `{{ stories }}`. The guardrail score is an Ollama JSON call. A failed AgentControl draft runs `reduce-briefing-uncertainty` when that tool is attached. Tool calls are recorded with `trackMetric` on `$ld:ai:tool:call`.

Keywords: **feature flags** · **JSON variations** · **AgentControl** · **server SDK** · **judges** · **Library tools**

| Topic | Docs |
|-------|------|
| Java server SDK | [Java SDK](https://launchdarkly.com/docs/sdk/server-side/java) |
| Evaluation reasons | [Evaluation reasons](https://launchdarkly.com/docs/sdk/features/evaluation-reasons) |
| Judges | [Judges](https://launchdarkly.com/docs/home/agentcontrol/judges) |
| Tools | [Tools](https://launchdarkly.com/docs/home/agentcontrol/tools) |

## Run

```bash
export LD_SDK_KEY="sdk-..."
cd 20-agent-config/26-flags-vs-agent-control/java
./mvnw -q package
java -jar target/26-flags-vs-agent-control.jar
```

Open **http://127.0.0.1:8262/**. Provision first with [../rest/README.md](../rest/README.md). Requires Java 21.

Port **8262**. Python is **8260**. Node is **8261**.
