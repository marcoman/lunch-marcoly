# 20-agent-config portal — Java

One-command **Java** shell for the AgentControl series examples **201–206**.

Twin of the [Python](../python/), [Node](../node/), and [.NET](../dotnet/) portals.
This portal serves a tabbed UI on **:8202**, spawns each example’s shaded jar,
and embeds those pages in **iframes**.

Keywords: **AgentControl** · **series portal** · **iframe tabs** · **process supervisor**

## Prerequisites

```bash
export LD_SDK_KEY="sdk-..."
# Java 21+ on PATH
```

Provision configs as usual — see [../../README.md](../../README.md).

If an example jar is missing under `…/java/target/`, the portal runs
`./mvnw -q -DskipTests package` in that example once before spawning.

## Run

```bash
cd 20-agent-config/portal/java
./mvnw -q -DskipTests package
java -jar target/portal-java.jar
```

Open **http://127.0.0.1:8202/**

| Tab | Example | Child port |
|-----|---------|------------|
| 201 | Completion | **8212** |
| 202 | Tracked + feedback | **8222** |
| 203 | Tools | **8232** |
| 204 | Judges | **8242** |
| 205 | Graph | **8252** |
| 206 | Flag compare | **8262** |

**Ctrl+C** stops the portal **and** all child servers.

Override the portal listen port with `PORTAL_PORT` (default `8202`).

## How it works

```text
java -jar target/portal-java.jar
  ├─ HTTP :8202  → portal/java/index.html (tabs)
  ├─ child 201   → …/201-…/java/target/21-….jar :8212  ← iframe
  ├─ child 202   → …/202-…/java/target/22-….jar :8222
  ├─ child 203   → …/203-…/java/target/23-….jar :8232
  ├─ child 204   → …/204-…/java/target/24-….jar :8242
  ├─ child 205   → …/205-…/java/target/25-….jar :8252
  └─ child 206   → …/206-…/java/target/26-….jar :8262
```

- Children inherit the portal’s environment (`LD_SDK_KEY`, Ollama, etc.).
- If a child port is already in use, the portal **does not** spawn a second
  process (it reuses whatever is listening).
- `GET /api/status` reports whether each child port is reachable (tab dots).

Headlines use the **series** cache at [`../../stories/`](../../stories/).
Standalone `java -jar` in each example’s `java/` still works without the portal.

## Related

- Series portal index: [../README.md](../README.md)
- Series setup: [../../README.md](../../README.md)
