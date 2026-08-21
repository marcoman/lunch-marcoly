# Portal (Java)

Series shell for **10-code-control**: tabbed UI that embeds **11**, **12**, and **13**
side by side.

| | Port |
|--|------|
| **Portal** | **8102** |
| **11 Flag enablement** | 8112 |
| **12 Flag variations** | 8122 |
| **13 Flag targeting rules** | 8132 |

Keywords: **feature flags** · **targeting rules** · **contexts** · **series portal**

## Prerequisites

- Java 21+
- `LD_SDK_KEY` (flags provisioned under each example)

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
solo apps still default to `:8080` when run from their own folders.

Twins: [Python](../python/) · [Node](../node/) · [.NET](../dotnet/). Series index: [../README.md](../README.md).
