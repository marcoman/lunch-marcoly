# 30-client-sdk portal

One-command series shells for **31-client-evaluation**, **32-client-identify**,
and **33-synced-segments**. Each portal serves a tabbed UI, spawns that client
SDK's existing hosts as children, and embeds them in **iframes**.

Portals are keyed by **client SDK**, not by Python / Java / .NET. Those host
languages are the 10- and 20-series pattern.

| Client SDK | Entry | Portal port | Child ports |
|------------|-------|-------------|-------------|
| **JavaScript** | [`javascript/`](javascript/) | **8300** | 8310 (31) · 8320 (32) · 8330 (33) |
| **React** | [`react/`](react/) | **8301** | 8311 (31) · 8321 (32) · 8331 (33) |
| **Vue** | [`vue/`](vue/) | **8302** | 8312 (31) · 8322 (32) · 8332 (33) |

Keywords: **client-side SDK** · **client-side ID** · **series portal** · **iframe tabs** · **process supervisor**

## Prerequisites

Export `LD_CLIENT_SIDE_ID` and provision the flags for all three examples. See
each language folder’s README for child `npm install`.

## Run

```bash
export LD_CLIENT_SIDE_ID="..."

# JavaScript → http://127.0.0.1:8300/
(cd 30-client-sdk/portal/javascript && npm start)

# React → http://127.0.0.1:8301/
(cd 30-client-sdk/portal/react && npm start)

# Vue → http://127.0.0.1:8302/
(cd 30-client-sdk/portal/vue && npm start)
```

**Ctrl+C** stops the portal and all children. Override the listen port with
`PORTAL_PORT`.

## How it works

- Children inherit the portal environment, including `LD_CLIENT_SIDE_ID`.
- Each portal sets the assigned `PORT` in every child environment.
- If a child port is already in use, the portal reuses that server.
- `GET /api/status` reports whether each child port is reachable.
- JavaScript children are the existing `node 3x-….js` hosts. React and Vue
  children are local Vite (`node_modules/vite/bin/vite.js`).
- The page evaluates flags in the iframe with that client SDK. The portal
  process never uses `LD_SDK_KEY`.

Standalone per-example entrypoints continue to work without a portal.
