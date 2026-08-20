#!/usr/bin/env node
/**
 * portal.js — series shell for 20-agent-config (Node web examples 21–25).
 *
 * One process for the user:
 *   - Serves this folder's index.html on :8201 (PORTAL_PORT)
 *   - Spawns each example's existing Node server as a child
 *   - Embeds those pages in iframes (see index.html)
 *
 * Twin of ../portal.py (Python on :8200 / *210–*250).
 * Standalone entrypoints under each example's node/ still work alone.
 * Ctrl+C / SIGTERM stops the portal and all children.
 */

"use strict";

const http = require("http");
const fs = require("fs");
const path = require("path");
const net = require("net");
const { spawn } = require("child_process");
const { URL } = require("url");

const HERE = __dirname;
const SERIES_ROOT = path.resolve(HERE, "..", "..");
const PORTAL_PORT = Number(process.env.PORTAL_PORT || 8201);
const APP_BANNER = "20-agent-config[portal-node]";

/** cwd = each example's node/ so index.html + require() resolve like a solo run. */
const CHILDREN = [
  {
    id: "21",
    label: "Completion",
    script: path.join(
      SERIES_ROOT,
      "21-agent-completion-config",
      "node",
      "21-agent-completion-config.js"
    ),
    cwd: path.join(SERIES_ROOT, "21-agent-completion-config", "node"),
    port: 8211,
  },
  {
    id: "22",
    label: "Tracked + feedback",
    script: path.join(SERIES_ROOT, "22-config-outside-code", "node", "22-config-outside-code.js"),
    cwd: path.join(SERIES_ROOT, "22-config-outside-code", "node"),
    port: 8221,
  },
  {
    id: "23",
    label: "Tools",
    script: path.join(SERIES_ROOT, "23-agent-tools", "node", "23-agent-tools.js"),
    cwd: path.join(SERIES_ROOT, "23-agent-tools", "node"),
    port: 8231,
  },
  {
    id: "24",
    label: "Judges",
    script: path.join(SERIES_ROOT, "24-agent-judges", "node", "24-agent-judges.js"),
    cwd: path.join(SERIES_ROOT, "24-agent-judges", "node"),
    port: 8241,
  },
  {
    id: "25",
    label: "Graph",
    script: path.join(SERIES_ROOT, "25-agent-graph", "node", "25-agent-graph.js"),
    cwd: path.join(SERIES_ROOT, "25-agent-graph", "node"),
    port: 8251,
  },
];

const procs = new Map();
let shuttingDown = false;

function portOpen(port, host = "127.0.0.1") {
  return new Promise((resolve) => {
    const socket = net.connect({ host, port }, () => {
      socket.end();
      resolve(true);
    });
    socket.on("error", () => resolve(false));
    socket.setTimeout(350, () => {
      socket.destroy();
      resolve(false);
    });
  });
}

async function waitForPort(port, timeoutMs = 45000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await portOpen(port)) return true;
    await new Promise((r) => setTimeout(r, 200));
  }
  return false;
}

function pipePrefix(childId, stream) {
  let buffer = "";
  stream.on("data", (chunk) => {
    buffer += chunk.toString("utf8");
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      console.log(`[${childId}] ${line}`);
    }
  });
  stream.on("end", () => {
    if (buffer) console.log(`[${childId}] ${buffer}`);
  });
}

async function startChildren() {
  for (const child of CHILDREN) {
    const { id: cid, port, script, cwd } = child;

    if (!fs.existsSync(script)) {
      console.error(`[${cid}] ERROR: missing script ${script}`);
      continue;
    }

    const modules = path.join(cwd, "node_modules");
    if (!fs.existsSync(modules)) {
      console.error(
        `[${cid}] ERROR: missing node_modules in ${cwd} — run: cd ${cwd} && npm install`
      );
      continue;
    }

    if (await portOpen(port)) {
      console.warn(
        `[${cid}] WARNING: port ${port} already in use — assuming an existing server; not spawning.`
      );
      continue;
    }

    console.log(`[${cid}] Starting ${path.basename(script)} on :${port} …`);
    const proc = spawn(process.execPath, [script], {
      cwd,
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
      // Own process group so stopChildren can signal the whole tree.
      detached: true,
    });
    procs.set(cid, proc);
    pipePrefix(cid, proc.stdout);
    pipePrefix(cid, proc.stderr);
    proc.on("exit", (code, signal) => {
      if (!shuttingDown) {
        console.log(`[${cid}] exited code=${code} signal=${signal || ""}`);
      }
    });

    if (await waitForPort(port)) {
      console.log(`[${cid}] Ready http://127.0.0.1:${port}/`);
    } else {
      console.error(
        `[${cid}] ERROR: port ${port} not ready (exit=${proc.exitCode}). Check LD_SDK_KEY and logs above.`
      );
    }
  }
}

function stopChildren() {
  if (shuttingDown) return;
  shuttingDown = true;

  const items = [...procs.entries()];
  procs.clear();

  function signalAll(sig) {
    for (const [cid, proc] of items) {
      if (proc.exitCode != null) continue;
      try {
        // Negative PID = process group (detached: true above).
        process.kill(-proc.pid, sig);
      } catch (_) {
        try {
          proc.kill(sig);
        } catch (__) {}
      }
      if (sig === "SIGTERM") console.log(`[${cid}] Stopping …`);
      if (sig === "SIGKILL") console.log(`[${cid}] Kill (still running)`);
    }
  }

  signalAll("SIGTERM");

  const deadline = Date.now() + 5000;
  while (Date.now() < deadline) {
    if (items.every(([, proc]) => proc.exitCode != null)) break;
    Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 100);
  }
  signalAll("SIGKILL");
}

async function childStatus() {
  const out = [];
  for (const child of CHILDREN) {
    const proc = procs.get(child.id);
    const alive = Boolean(proc && proc.exitCode == null && !proc.killed);
    const up = await portOpen(child.port);
    out.push({
      id: child.id,
      label: child.label,
      port: child.port,
      url: `http://127.0.0.1:${child.port}/`,
      spawned: procs.has(child.id) || Boolean(proc),
      alive,
      up,
    });
  }
  return out;
}

function send(res, status, body, contentType) {
  const raw = Buffer.isBuffer(body) ? body : Buffer.from(body);
  res.writeHead(status, {
    "Content-Type": contentType,
    "Content-Length": raw.length,
    "Cache-Control": "no-store",
  });
  res.end(raw);
}

async function handleRequest(req, res) {
  const url = new URL(req.url || "/", `http://${req.headers.host || "127.0.0.1"}`);
  const pathname = url.pathname;

  if (req.method === "GET" && (pathname === "/" || pathname === "/index.html")) {
    const index = path.join(HERE, "index.html");
    if (!fs.existsSync(index)) {
      send(res, 404, "Not found", "text/plain; charset=utf-8");
      return;
    }
    send(res, 200, fs.readFileSync(index), "text/html; charset=utf-8");
    return;
  }

  if (req.method === "GET" && pathname === "/api/status") {
    const children = await childStatus();
    send(
      res,
      200,
      JSON.stringify({
        appBanner: APP_BANNER,
        portalPort: PORTAL_PORT,
        language: "node",
        children,
      }),
      "application/json; charset=utf-8"
    );
    return;
  }

  send(res, 404, "Not found", "text/plain; charset=utf-8");
}

async function main() {
  if (!String(process.env.LD_SDK_KEY || "").trim()) {
    console.warn(
      "WARNING: LD_SDK_KEY is unset. Child examples will fail to init " +
        "LaunchDarkly until you export a server-side SDK key."
    );
  }

  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
  process.on("exit", () => {
    stopChildren();
  });

  await startChildren();

  const server = http.createServer((req, res) => {
    handleRequest(req, res).catch((err) => {
      console.error(err);
      if (!res.headersSent) {
        send(res, 500, String(err.message || err), "text/plain; charset=utf-8");
      } else {
        res.end();
      }
    });
  });

  function shutdown() {
    console.log(`\n${APP_BANNER}: shutting down …`);
    stopChildren();
    server.close(() => {
      console.log(`${APP_BANNER}: stopped.`);
      process.exit(0);
    });
    // Force exit if close hangs.
    setTimeout(() => process.exit(0), 6000).unref();
  }

  server.listen(PORTAL_PORT, "127.0.0.1", () => {
    console.log(APP_BANNER);
    console.log(`Open http://127.0.0.1:${PORTAL_PORT}/`);
    console.log("Tabs embed Node examples on 8211 / 8221 / 8231 / 8241 / 8251.");
    console.log("Ctrl+C stops the portal and all children.");
  });
}

main().catch((err) => {
  console.error(err);
  stopChildren();
  process.exit(1);
});
