# 20-agent-config portal

One-command series shells for AgentControl examples **201–206**. Each portal serves
a tabbed UI, spawns that language’s existing web servers as children, and embeds
them in **iframes**.

| Language | Entry | Portal port | Child ports |
|----------|-------|-------------|-------------|
| **Python** | [`python/`](python/) | **8200** | 8210 · 8220 · 8230 · 8240 · 8250 · 8260 |
| **Node** | [`node/`](node/) | **8201** | 8211 · 8221 · 8231 · 8241 · 8251 · 8261 |
| **Java** | [`java/`](java/) | **8202** | 8212 · 8222 · 8232 · 8242 · 8252 · 8262 |
| **.NET** | [`dotnet/`](dotnet/) | **8203** | 8213 · 8223 · 8233 · 8243 · 8253 · 8263 |

Keywords: **AgentControl** · **series portal** · **iframe tabs** · **process supervisor**

## Prerequisites

Same as the series landing page: `LD_SDK_KEY`, Ollama models, and provisioned
configs. See each language folder’s README for toolchain notes (venv, `nvm`,
Java 21+ / `./mvnw`, .NET 10+).

```bash
# From repo root
export LD_SDK_KEY="sdk-..."
# Optional: provision per-example rest/ scripts first — see ../README.md
```

## Run

```bash
# Python
cd 20-agent-config/portal/python && python portal.py
# → http://127.0.0.1:8200/

# Node
cd 20-agent-config/portal/node && npm start
# → http://127.0.0.1:8201/

# Java
cd 20-agent-config/portal/java && ./mvnw -q -DskipTests package && java -jar target/portal-java.jar
# → http://127.0.0.1:8202/

# .NET
cd 20-agent-config/portal/dotnet && dotnet run
# → http://127.0.0.1:8203/
```

**Ctrl+C** stops the portal **and** all child servers.

Override listen port with `PORTAL_PORT`.

A shim at [`portal.py`](portal.py) still forwards to [`python/portal.py`](python/portal.py).

## How it works

```text
python portal.py   (or node / java / dotnet twin)
  ├─ HTTP :820x  → language/index.html (tabs 201–206)
  ├─ child 201   → …/201-…/<lang>/… :821x
  ├─ child 202   → …/202-…/<lang>/… :822x
  ├─ child 203   → …/203-…/<lang>/… :823x
  ├─ child 204   → …/204-…/<lang>/… :824x
  ├─ child 205   → …/205-…/<lang>/… :825x
  └─ child 206   → …/206-…/<lang>/… :826x
```

Each language launches `201-…` through `206-…` entrypoints: Python `.py`, Node `.js`, Java jars, and .NET `.csproj`.

- Children inherit the portal’s environment (`LD_SDK_KEY`, Ollama, etc.).
- If a child port is already in use, the portal **does not** spawn a second
  process (it reuses whatever is listening).
- `GET /api/status` reports whether each child port is reachable (tab dots).
- Java builds a missing example jar with that example’s `./mvnw` before spawn.
- .NET uses `dotnet run` per example (first start may restore/build).

Headlines use the **series** cache at [`../stories/`](../stories/).
Standalone per-example entrypoints still work without the portal.

## Non-goals

- Single shared process / shared LaunchDarkly client for all lessons
- Reverse-proxy under one origin

## Related

- Series setup: [../README.md](../README.md)
- [python/README.md](python/README.md) · [node/README.md](node/README.md) ·
  [java/README.md](java/README.md) · [dotnet/README.md](dotnet/README.md)
- [201-agent-completion-config](../201-agent-completion-config/)
- [202-config-outside-code](../202-config-outside-code/)
- [203-agent-tools](../203-agent-tools/)
- [204-agent-judges](../204-agent-judges/)
- [205-agent-graph](../205-agent-graph/)
- [206-flags-vs-agent-control](../206-flags-vs-agent-control/)
