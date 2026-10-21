# 20-agent-config portal — Python

One-command **Python** shell for the AgentControl series examples **201–206**.

Twin of the [Node](../node/), [Java](../java/), and [.NET](../dotnet/) portals.
This portal serves a tabbed UI on **:8200**, spawns each example’s existing
Python web server, and embeds those pages in **iframes**.

Keywords: **AgentControl** · **series portal** · **iframe tabs** · **process supervisor**

## Prerequisites

```bash
# From repo root
source .venv/bin/activate
export LD_SDK_KEY="sdk-..."
```

Provision configs as usual — see [../../README.md](../../README.md).

## Run

```bash
cd 20-agent-config/portal/python
python portal.py
```

Open **http://127.0.0.1:8200/**

| Tab | Example | Child port |
|-----|---------|------------|
| 201 | Completion | **8210** |
| 202 | Tracked + feedback | **8220** |
| 203 | Tools | **8230** |
| 204 | Judges | **8240** |
| 205 | Graph | **8250** |
| 206 | Flag compare | **8260** |

**Ctrl+C** stops the portal **and** all child servers.

Override the portal listen port with `PORTAL_PORT` (default `8200`).

A shim at [`../portal.py`](../portal.py) still forwards to this entrypoint.

## How it works

```text
python portal.py
  ├─ HTTP :8200  → portal/python/index.html (tabs)
  ├─ child 201   → …/201-…/python/201-….py :8210  ← iframe
  ├─ child 202   → …/202-…/python/202-….py :8220
  ├─ child 203   → …/203-…/python/203-….py :8230
  ├─ child 204   → …/204-…/python/204-….py :8240
  ├─ child 205   → …/205-…/python/205-….py :8250
  └─ child 206   → …/206-…/python/206-….py :8260
```

- Children inherit the portal’s environment (`LD_SDK_KEY`, Ollama, etc.).
- If a child port is already in use, the portal **does not** spawn a second
  process (it reuses whatever is listening).
- `GET /api/status` reports whether each child port is reachable (tab dots).

Headlines use the **series** cache at [`../../stories/`](../../stories/).
Standalone `python …/python/*.py` still works without the portal.

## Related

- Series portal index: [../README.md](../README.md)
- Series setup: [../../README.md](../../README.md)
