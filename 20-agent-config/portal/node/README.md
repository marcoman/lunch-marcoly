# 20-agent-config portal — Node

One-command **Node** shell for the AgentControl series examples **201–206**.

Twin of the [Python](../python/), [Java](../java/), and [.NET](../dotnet/) portals.
This portal serves a tabbed UI on **:8201**, spawns each example’s existing Node
web server, and embeds those pages in **iframes**.

Keywords: **AgentControl** · **series portal** · **iframe tabs** · **process supervisor**

## Prerequisites

```bash
nvm use
export LD_SDK_KEY="sdk-..."

# Install deps once per example (portal will refuse to spawn without node_modules)
for d in \
  ../../201-agent-completion-config/node \
  ../../202-config-outside-code/node \
  ../../203-agent-tools/node \
  ../../204-agent-judges/node \
  ../../205-agent-graph/node \
  ../../206-flags-vs-agent-control/node
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
| 201 | Completion | **8211** |
| 202 | Tracked + feedback | **8221** |
| 203 | Tools | **8231** |
| 204 | Judges | **8241** |
| 205 | Graph | **8251** |
| 206 | Flag compare | **8261** |

**Ctrl+C** stops the portal **and** all child servers.

Override the portal listen port with `PORTAL_PORT` (default `8201`).

## How it works

```text
node portal.js
  ├─ HTTP :8201  → portal/node/index.html (tabs)
  ├─ child 201   → …/201-…/node/201-….js :8211  ← iframe
  ├─ child 202   → …/202-…/node/202-….js :8221
  ├─ child 203   → …/203-…/node/203-….js :8231
  ├─ child 204   → …/204-…/node/204-….js :8241
  ├─ child 205   → …/205-…/node/205-….js :8251
  └─ child 206   → …/206-…/node/206-….js :8261
```

- Children inherit the portal’s environment (`LD_SDK_KEY`, Ollama, etc.).
- If a child port is already in use, the portal **does not** spawn a second
  process (it reuses whatever is listening).
- `GET /api/status` reports whether each child port is reachable (tab dots).

Headlines use the **series** cache at [`../../stories/`](../../stories/).
Standalone `npm start` in each example’s `node/` still works without the portal.

## Related

- Series portal index: [../README.md](../README.md)
- Series setup: [../../README.md](../../README.md)
