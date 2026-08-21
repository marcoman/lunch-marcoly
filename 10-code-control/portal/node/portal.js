#!/usr/bin/env node
/**
 * portal.js — series shell for 10-code-control (Node web examples 11–13).
 *
 * Serves this folder's index.html on :8101 (PORTAL_PORT), spawns each example's
 * existing Node server with its assigned PORT, and stops all children on exit.
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
const PORTAL_PORT = Number(process.env.PORTAL_PORT || 8101);
const APP_BANNER = "10-code-control[portal-node]";

/** cwd is each example's node/ so assets and dependencies resolve like a solo run. */
const CHILDREN = [
  {
    id: "11",
    label: "Flag enablement",
    script: path.join(SERIES_ROOT, "11-flag-enablement", "node", "11-flag-enablement.js"),
    cwd: path.join(SERIES_ROOT, "11-flag-enablement", "node"),
    port: 8111,
  },
  {
    id: "12",
    label: "Flag variations",
    script: path.join(SERIES_ROOT, "12-flag-variations", "node", "12-flag-variations.js"),
    cwd: path.join(SERIES_ROOT, "12-flag-variations", "node"),
    port: 8121,
  },
  {
    id: "13",
    label: "Flag targeting rules",
    script: path.join(
      SERIES_ROOT,
      "13-flag-targeting-rules",
      "node",
      "13-flag-targeting-rules.js"
    ),
    cwd: path.join(SERIES_ROOT, "13-flag-targeting-rules", "node"),
    port: 8131,
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
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  return false;
}

function pipePrefix(childId, stream) {
  let buffer = "";
  stream.on("data", (chunk) => {
    buffer += chunk.toString("utf8");
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) console.log(`[${childId}] ${line}`);
  });
  stream.on("end", () => {
    if (buffer) console.log(`[${childId}] ${buffer}`);
  });
}

async function startChildren() {
  for (const child of CHILDREN) {
    const { id, port, script, cwd } = child;

    if (!fs.existsSync(script)) {
      console.error(`[${id}] ERROR: missing script ${script}`);
      continue;
    }
    if (!fs.existsSync(path.join(cwd, "node_modules"))) {
      console.error(
        `[${id}] ERROR: missing node_modules in ${cwd} — run: cd ${cwd} && npm install`
      );
      continue;
    }
    if (await portOpen(port)) {
      console.warn(
        `[${id}] WARNING: port ${port} already in use — assuming an existing server; not spawning.`
      );
      continue;
    }

    console.log(`[${id}] Starting ${path.basename(script)} on :${port} …`);
    const proc = spawn(process.execPath, [script], {
      cwd,
      env: { ...process.env, PORT: String(port) },
      stdio: ["ignore", "pipe", "pipe"],
      detached: true,
    });
    procs.set(id, proc);
    pipePrefix(id, proc.stdout);
    pipePrefix(id, proc.stderr);
    proc.on("exit", (code, signal) => {
      if (!shuttingDown) console.log(`[${id}] exited code=${code} signal=${signal || ""}`);
    });

    if (await waitForPort(port)) {
      console.log(`[${id}] Ready http://127.0.0.1:${port}/`);
    } else {
      console.error(
        `[${id}] ERROR: port ${port} not ready (exit=${proc.exitCode}). Check LD_SDK_KEY and logs above.`
      );
    }
  }
}

function stopChildren() {
  if (shuttingDown) return;
  shuttingDown = true;
  const items = [...procs.entries()];
  procs.clear();

  function signalAll(signal) {
    for (const [id, proc] of items) {
      if (proc.exitCode != null) continue;
      try {
        process.kill(-proc.pid, signal);
      } catch (_) {
        try {
          proc.kill(signal);
        } catch (__) {}
      }
      if (signal === "SIGTERM") console.log(`[${id}] Stopping …`);
      if (signal === "SIGKILL") console.log(`[${id}] Kill (still running)`);
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
    out.push({
      id: child.id,
      label: child.label,
      port: child.port,
      url: `http://127.0.0.1:${child.port}/`,
      spawned: procs.has(child.id),
      alive: Boolean(proc && proc.exitCode == null && !proc.killed),
      up: await portOpen(child.port),
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
  if (req.method === "GET" && (url.pathname === "/" || url.pathname === "/index.html")) {
    const index = path.join(HERE, "index.html");
    if (!fs.existsSync(index)) return send(res, 404, "Not found", "text/plain; charset=utf-8");
    return send(res, 200, fs.readFileSync(index), "text/html; charset=utf-8");
  }
  if (req.method === "GET" && url.pathname === "/api/status") {
    return send(
      res,
      200,
      JSON.stringify({
        appBanner: APP_BANNER,
        portalPort: PORTAL_PORT,
        language: "node",
        children: await childStatus(),
      }),
      "application/json; charset=utf-8"
    );
  }
  return send(res, 404, "Not found", "text/plain; charset=utf-8");
}

async function main() {
  if (!String(process.env.LD_SDK_KEY || "").trim()) {
    console.warn(
      "WARNING: LD_SDK_KEY is unset. Child examples will fail to init " +
        "LaunchDarkly until you export a server-side SDK key."
    );
  }

  let server;
  function shutdown() {
    console.log(`\n${APP_BANNER}: shutting down …`);
    stopChildren();
    if (!server) {
      process.exit(0);
      return;
    }
    server.close(() => {
      console.log(`${APP_BANNER}: stopped.`);
      process.exit(0);
    });
    setTimeout(() => process.exit(0), 6000).unref();
  }

  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
  process.on("exit", stopChildren);
  await startChildren();

  server = http.createServer((req, res) => {
    handleRequest(req, res).catch((err) => {
      console.error(err);
      if (!res.headersSent) send(res, 500, String(err.message || err), "text/plain; charset=utf-8");
      else res.end();
    });
  });
  server.listen(PORTAL_PORT, "127.0.0.1", () => {
    console.log(APP_BANNER);
    console.log(`Open http://127.0.0.1:${PORTAL_PORT}/`);
    console.log("Tabs embed Node examples on 8111 / 8121 / 8131.");
    console.log("Ctrl+C stops the portal and all children.");
  });
}

main().catch((err) => {
  console.error(err);
  stopChildren();
  process.exit(1);
});
