# 10-code-control portal

One-command series shells for **11-flag-enablement** and **12-flag-variations**.
Each portal serves a tabbed UI, spawns that language's existing web servers as
children, and embeds them in **iframes**.

| Language | Entry | Portal port | Child ports |
|----------|-------|-------------|-------------|
| **Python** | [`python/`](python/) | **8100** | 8110 (11) · 8120 (12) |
| **Node** | [`node/`](node/) | **8101** | 8111 (11) · 8121 (12) |
| **Java** | [`java/`](java/) | **8102** | 8112 (11) · 8122 (12) |
| **.NET** | [`dotnet/`](dotnet/) | **8103** | 8113 (11) · 8123 (12) |

Keywords: **feature flags** · **series portal** · **iframe tabs** · **process supervisor**

## Prerequisites

Export `LD_SDK_KEY` and provision the flags for both examples. See each language
folder's README for toolchain details and child dependency setup.

## Run

```bash
export LD_SDK_KEY="sdk-..."

# Python → http://127.0.0.1:8100/
(cd 10-code-control/portal/python && python portal.py)

# Node → http://127.0.0.1:8101/
(cd 10-code-control/portal/node && npm start)

# Java → http://127.0.0.1:8102/
(cd 10-code-control/portal/java && \
  ./mvnw -q -DskipTests package && java -jar target/portal-java.jar)

# .NET → http://127.0.0.1:8103/
(cd 10-code-control/portal/dotnet && dotnet run)
```

**Ctrl+C** stops the portal and all children. Override the listen port with
`PORTAL_PORT`.

## How it works

- Children inherit the portal environment, including `LD_SDK_KEY`.
- Each portal sets the assigned `PORT` in every child environment.
- If a child port is already in use, the portal reuses that server.
- `GET /api/status` reports whether each child port is reachable.
- Java builds a missing example jar with that example's Maven wrapper.

Standalone per-example entrypoints continue to work without a portal.
