# 20-agent-config portal — .NET

One-command **.NET** shell for the AgentControl series examples **201–206**.

Twin of the [Python](../python/), [Node](../node/), and [Java](../java/) portals.
This portal serves a tabbed UI on **:8203**, spawns each example’s
`dotnet run`, and embeds those pages in **iframes**.

Keywords: **AgentControl** · **series portal** · **iframe tabs** · **process supervisor**

## Prerequisites

```bash
export LD_SDK_KEY="sdk-..."
export PATH="/usr/local/share/dotnet:$PATH"   # if needed
dotnet --list-sdks   # SDK 10+
```

Provision configs as usual — see [../../README.md](../../README.md).

First portal start can take longer while children restore/build.

## Run

```bash
cd 20-agent-config/portal/dotnet
dotnet run
```

Open **http://127.0.0.1:8203/**

| Tab | Example | Child port |
|-----|---------|------------|
| 201 | Completion | **8213** |
| 202 | Tracked + feedback | **8223** |
| 203 | Tools | **8233** |
| 204 | Judges | **8243** |
| 205 | Graph | **8253** |
| 206 | Flag compare | **8263** |

**Ctrl+C** stops the portal **and** all child servers.

Override the portal listen port with `PORTAL_PORT` (default `8203`).

## How it works

```text
dotnet run
  ├─ HTTP :8203  → portal/dotnet/wwwroot/index.html (tabs)
  ├─ child 201   → …/201-…/dotnet 21-….csproj :8213  ← iframe
  ├─ child 202   → …/202-…/dotnet 22-….csproj :8223
  ├─ child 203   → …/203-…/dotnet 23-….csproj :8233
  ├─ child 204   → …/204-…/dotnet 24-….csproj :8243
  ├─ child 205   → …/205-…/dotnet 25-….csproj :8253
  └─ child 206   → …/206-…/dotnet 26-….csproj :8263
```

- Children inherit the portal’s environment (`LD_SDK_KEY`, Ollama, etc.).
- If a child port is already in use, the portal **does not** spawn a second
  process (it reuses whatever is listening).
- `GET /api/status` reports whether each child port is reachable (tab dots).

Headlines use the **series** cache at [`../../stories/`](../../stories/).
Standalone `dotnet run` in each example’s `dotnet/` still works without the portal.

## Related

- Series portal index: [../README.md](../README.md)
- Series setup: [../../README.md](../../README.md)
