# Portal (Java)

Series shell for **10-code-control**: tabbed UI that embeds **11–17** side by side.

| | Port |
|--|------|
| **Portal** | **8102** |
| **11 Flag enablement** | 8112 |
| **12 Flag variations** | 8122 |
| **13 Flag targeting rules** | 8132 |
| **14 Multi-context targeting** | 8142 |
| **15 Prerequisite flags** | 8152 |
| **16 Percentage rollout** | 8162 |
| **17 Scheduled changes** | 8172 |

Keywords: **feature flags** · **targeting rules** · **contexts** · **series portal**

## Prerequisites

- Java 21+
- `LD_SDK_KEY` (flags provisioned under each example)
- For tab 17 controls: `LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, and
  `LD_ENVIRONMENT_KEY`

```bash
export LD_SDK_KEY="sdk-..."
```

Missing child jars are built in their example folders with
`./mvnw -q -DskipTests package` before spawn.

## Run

```bash
cd 10-code-control/portal/java
./mvnw -q -DskipTests package
java -jar target/portal-java.jar
```

Open [http://127.0.0.1:8102/](http://127.0.0.1:8102/). **Ctrl+C** stops the portal and all children.

Override with `PORTAL_PORT`. The portal passes `PORT` to each shaded child jar;
solo apps use the standalone default documented in their own README.

Twins: [Python](../python/) · [Node](../node/) · [.NET](../dotnet/). Series index: [../README.md](../README.md).
