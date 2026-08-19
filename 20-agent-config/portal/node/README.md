# 20-agent-config portal — Node

One-command **Node** shell for the AgentControl series examples **21–24**.

Twin of the [Python portal](../README.md) (`portal.py` on **:8200**). This portal
serves a tabbed UI on **:8201**, spawns each example’s existing Node web server,
and embeds those pages in **iframes**.

Keywords: **AgentControl** · **series portal** · **iframe tabs** · **process supervisor**

## Prerequisites

```bash
nvm use
export LD_SDK_KEY="sdk-..."

# Install deps once per example (portal will refuse to spawn without node_modules)
for d in \
  ../../21-agent-completion-config/node \
  ../../22-config-outside-code/node \
  ../../23-agent-tools/node \
  ../../24-agent-judges/node
do
  (cd "$d" && npm install)
done
```

Provision configs as usual — see [../../README.md](../../README.md).

## Run

```bash
cd 20-agent-config/portal/node
npm start
# or: node portal.js
```

Open **http://127.0.0.1:8201/**

| Tab | Example | Child port |
|-----|---------|------------|
| 21 | Completion | **8211** |
| 22 | Tracked + feedback | **8221** |
| 23 | Tools | **8231** |
| 24 | Judges | **8241** |

**Ctrl+C** stops the portal **and** all child servers.

Override the portal listen port with `PORTAL_PORT` (default `8201`).

## How it works

```text
node portal.js
  ├─ HTTP :8201  → portal/node/index.html (tabs)
  ├─ child 21    → …/21-…/node/…js :8211  ← iframe
  ├─ child 22    → …/22-…/node/…js :8221
  ├─ child 23    → …/23-…/node/…js :8231
  └─ child 24    → …/24-…/node/…js :8241
```

- Children inherit the portal’s environment (`LD_SDK_KEY`, Ollama, etc.).
- If a child port is already in use, the portal **does not** spawn a second
  process (it reuses whatever is listening).
- `GET /api/status` reports whether each child port is reachable (tab dots).

Yahoo headlines use the **series** cache at [`../../stories/`](../../stories/).
Standalone `npm start` in each example’s `node/` still works without the portal.

## Related

- Python portal: [../README.md](../README.md) (**:8200**)
- Series setup: [../../README.md](../../README.md)
