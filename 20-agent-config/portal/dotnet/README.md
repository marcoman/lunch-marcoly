# 20-agent-config portal — .NET

One-command **.NET** shell for the AgentControl series examples **21–25**.

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
| 21 | Completion | **8213** |
| 22 | Tracked + feedback | **8223** |
| 23 | Tools | **8233** |
| 24 | Judges | **8243** |
| 25 | Graph | **8253** |

**Ctrl+C** stops the portal **and** all child servers.

Override the portal listen port with `PORTAL_PORT` (default `8203`).

## How it works

```text
dotnet run
  ├─ HTTP :8203  → portal/dotnet/wwwroot/index.html (tabs)
  ├─ child 21    → …/21-…/dotnet run :8213  ← iframe
  ├─ child 22    → …/22-…/dotnet run :8223
  ├─ child 23    → …/23-…/dotnet run :8233
  ├─ child 24    → …/24-…/dotnet run :8243
  └─ child 25    → …/25-…/dotnet run :8253
```

- Children inherit the portal’s environment (`LD_SDK_KEY`, Ollama, etc.).
- If a child port is already in use, the portal **does not** spawn a second
  process (it reuses whatever is listening).
- `GET /api/status` reports whether each child port is reachable (tab dots).

Yahoo headlines use the **series** cache at [`../../stories/`](../../stories/).
Standalone `dotnet run` in each example’s `dotnet/` still works without the portal.

## Related

- Series portal index: [../README.md](../README.md)
- Series setup: [../../README.md](../../README.md)
