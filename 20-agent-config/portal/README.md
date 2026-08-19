# 20-agent-config portal

One-command **Python** shell for the AgentControl series examples **21–24**.

The portal serves a tabbed UI on **:8200**, spawns each example’s existing Python
web server as a child process, and embeds those pages in **iframes**.

Keywords: **AgentControl** · **series portal** · **iframe tabs** · **process supervisor**

## Prerequisites

Same as the series landing page: root `.venv`, `LD_SDK_KEY`, Ollama models, and
provisioned configs for the examples you will open.

```bash
# From repo root
source .venv/bin/activate
export LD_SDK_KEY="sdk-..."
# Optional: provision per-example rest/ scripts first — see ../README.md
```

## Run

```bash
cd 20-agent-config/portal
python portal.py
```

Open **http://127.0.0.1:8200/**

| Tab | Example | Child port |
|-----|---------|------------|
| 21 | Completion | **8210** |
| 22 | Tracked + feedback | **8220** |
| 23 | Tools | **8230** |
| 24 | Judges | **8240** |

**Ctrl+C** stops the portal **and** all child servers.

Override the portal listen port with `PORTAL_PORT` (default `8200`).

## How it works

```text
python portal.py
  ├─ HTTP :8200  → portal/index.html (tabs)
  ├─ child 21    → …/21-…/python/…py :8210  ← iframe
  ├─ child 22    → …/22-…/python/…py :8220
  ├─ child 23    → …/23-…/python/…py :8230
  └─ child 24    → …/24-…/python/…py :8240
```

- Children inherit the portal’s environment (`LD_SDK_KEY`, Ollama, etc.).
- If a child port is already in use, the portal **does not** spawn a second
  process (it reuses whatever is listening).
- `GET /api/status` reports whether each child port is reachable (tab dots).

Stories caches remain **per example** (`../NN-…/stories/`). Standalone runs of
each `python/*.py` still work without the portal.

## Non-goals (v1)

- Node / Java / .NET inside the portal (run those entrypoints alone)
- Single shared process / shared LaunchDarkly client for all lessons
- Reverse-proxy under one origin

## Related

- Series setup: [../README.md](../README.md)
- [21-agent-completion-config](../21-agent-completion-config/)
- [22-config-outside-code](../22-config-outside-code/)
- [23-agent-tools](../23-agent-tools/)
- [24-agent-judges](../24-agent-judges/)
