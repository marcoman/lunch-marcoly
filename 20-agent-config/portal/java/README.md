# 20-agent-config portal — Java

One-command **Java** shell for the AgentControl series examples **21–25**.

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
| 21 | Completion | **8212** |
| 22 | Tracked + feedback | **8222** |
| 23 | Tools | **8232** |
| 24 | Judges | **8242** |
| 25 | Graph | **8252** |

**Ctrl+C** stops the portal **and** all child servers.

Override the portal listen port with `PORTAL_PORT` (default `8202`).

## How it works

```text
java -jar target/portal-java.jar
  ├─ HTTP :8202  → portal/java/index.html (tabs)
  ├─ child 21    → …/21-…/java/target/….jar :8212  ← iframe
  ├─ child 22    → …/22-…/java/target/….jar :8222
  ├─ child 23    → …/23-…/java/target/….jar :8232
  ├─ child 24    → …/24-…/java/target/….jar :8242
  └─ child 25    → …/25-…/java/target/….jar :8252
```

- Children inherit the portal’s environment (`LD_SDK_KEY`, Ollama, etc.).
- If a child port is already in use, the portal **does not** spawn a second
  process (it reuses whatever is listening).
- `GET /api/status` reports whether each child port is reachable (tab dots).

Yahoo headlines use the **series** cache at [`../../stories/`](../../stories/).
Standalone `java -jar` in each example’s `java/` still works without the portal.

## Related

- Series portal index: [../README.md](../README.md)
- Series setup: [../../README.md](../../README.md)
