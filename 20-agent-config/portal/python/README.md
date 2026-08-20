# 20-agent-config portal — Python

One-command **Python** shell for the AgentControl series examples **21–25**.

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
| 21 | Completion | **8210** |
| 22 | Tracked + feedback | **8220** |
| 23 | Tools | **8230** |
| 24 | Judges | **8240** |
| 25 | Graph | **8250** |

**Ctrl+C** stops the portal **and** all child servers.

Override the portal listen port with `PORTAL_PORT` (default `8200`).

A shim at [`../portal.py`](../portal.py) still forwards to this entrypoint.

## How it works

```text
python portal.py
  ├─ HTTP :8200  → portal/python/index.html (tabs)
  ├─ child 21    → …/21-…/python/…py :8210  ← iframe
  ├─ child 22    → …/22-…/python/…py :8220
  ├─ child 23    → …/23-…/python/…py :8230
  ├─ child 24    → …/24-…/python/…py :8240
  └─ child 25    → …/25-…/python/…py :8250
```

- Children inherit the portal’s environment (`LD_SDK_KEY`, Ollama, etc.).
- If a child port is already in use, the portal **does not** spawn a second
  process (it reuses whatever is listening).
- `GET /api/status` reports whether each child port is reachable (tab dots).

Yahoo headlines use the **series** cache at [`../../stories/`](../../stories/).
Standalone `python …/python/*.py` still works without the portal.

## Related

- Series portal index: [../README.md](../README.md)
- Series setup: [../../README.md](../../README.md)
