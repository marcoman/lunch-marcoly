# 20-agent-config portal

One-command series shells for AgentControl examples **21–25**. Each portal serves
a tabbed UI, spawns that language’s existing web servers as children, and embeds
them in **iframes**.

| Language | Entry | Portal port | Child ports |
|----------|-------|-------------|-------------|
| **Python** | [`portal.py`](portal.py) / this README | **8200** | 8210 · 8220 · 8230 · 8240 · 8250 |
| **Node** | [`node/`](node/) | **8201** | 8211 · 8221 · 8231 · 8241 · 8251 |

Keywords: **AgentControl** · **series portal** · **iframe tabs** · **process supervisor**

## Prerequisites

Same as the series landing page: `LD_SDK_KEY`, Ollama models, and provisioned
configs. Python needs the root `.venv`; Node needs `nvm use` and `npm install`
in each example’s `node/` folder (see [node/README.md](node/README.md)).

```bash
# From repo root
export LD_SDK_KEY="sdk-..."
# Optional: provision per-example rest/ scripts first — see ../README.md
```

## Run — Python

```bash
source ../.venv/bin/activate   # from repo root: source .venv/bin/activate
cd 20-agent-config/portal
python portal.py
```

Open **http://127.0.0.1:8200/**

## Run — Node

```bash
cd 20-agent-config/portal/node
npm start
```

Open **http://127.0.0.1:8201/**

**Ctrl+C** stops the portal **and** all child servers.

Override listen port with `PORTAL_PORT`.

## How it works (Python)

```text
python portal.py
  ├─ HTTP :8200  → portal/index.html (tabs)
  ├─ child 21    → …/21-…/python/…py :8210  ← iframe
  ├─ child 22    → …/22-…/python/…py :8220
  ├─ child 23    → …/23-…/python/…py :8230
  ├─ child 24    → …/24-…/python/…py :8240
  └─ child 25    → …/25-…/python/…py :8250
```

Node is the same shape on **:8201** with `*211`–`*251` children — see [node/README.md](node/README.md).

- Children inherit the portal’s environment (`LD_SDK_KEY`, Ollama, etc.).
- If a child port is already in use, the portal **does not** spawn a second
  process (it reuses whatever is listening).
- `GET /api/status` reports whether each child port is reachable (tab dots).

Yahoo headlines use the **series** cache at [`../stories/`](../stories/).
Standalone per-example entrypoints still work without the portal.

## Non-goals (v1)

- Java / .NET inside the portal (run those entrypoints alone)
- Single shared process / shared LaunchDarkly client for all lessons
- Reverse-proxy under one origin

## Related

- Series setup: [../README.md](../README.md)
- [21-agent-completion-config](../21-agent-completion-config/)
- [22-config-outside-code](../22-config-outside-code/)
- [23-agent-tools](../23-agent-tools/)
- [24-agent-judges](../24-agent-judges/)
- [25-agent-graph](../25-agent-graph/)
