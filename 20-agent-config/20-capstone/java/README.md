# 20-capstone — Java web

Same capstone as the Node app: assess → specialist → judges → checked tools → finalize.

Port **8292**. Requires Java 21, `LD_SDK_KEY`, the capstone graph and node configs, and local Ollama.

There is no official Java AI SDK. The app evaluates each config with `jsonValueVariationDetail` and sends the `$ld:ai:*` metric events itself. Feedback tokens are minted by the app and mapped back to the draft context.

Keywords: **AgentControl** · **agent graphs** · **Library tools** · **judges** · **jsonValueVariationDetail** · **locale**

| Topic | Docs |
|-------|------|
| Agent graphs | [Agent graphs](https://launchdarkly.com/docs/home/agentcontrol/agent-graphs) |
| Tools | [Tools](https://launchdarkly.com/docs/home/agentcontrol/tools) |
| Judges | [Judges](https://launchdarkly.com/docs/home/agentcontrol/judges) |
| Java server SDK | [Java server SDK](https://launchdarkly.com/docs/sdk/server-side/java) |
| Spec | [../application.md](../application.md) |

## Run

```bash
export LD_SDK_KEY="sdk-..."
ollama pull llama3.2:3b

cd 20-agent-config/20-capstone/java
./mvnw -q -DskipTests package
java -jar target/20-capstone.jar
```

Open **http://127.0.0.1:8292/**.

The screen matches the Node app. Provision the graph once from `../rest`. This app is not a portal tab.
