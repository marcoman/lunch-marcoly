#!/usr/bin/env node
/** Serve the ABCD navigation count label grid navigator web UI on a local HTTP server. */

const http = require("http");
const fs = require("fs");
const path = require("path");
const { initClient, closeClient, evaluateCountLabel } = require("../abcd-eval.js");

// LaunchDarkly capability: String flag evaluation for multivariate A/B/C/D test
// See: https://launchdarkly.com/docs/sdk/features/flag-types

const PORT = 8080;
const ROOT = __dirname;

function sendJson(res, status, body) {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(payload),
  });
  res.end(payload);
}

async function runServer() {
  await initClient();

  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, `http://127.0.0.1:${PORT}`);

    if (url.pathname === "/api/count-label") {
      const username = (url.searchParams.get("username") || "").trim();
      if (!username) {
        sendJson(res, 400, { error: "username query parameter is required" });
        return;
      }
      const countLabel = await evaluateCountLabel(username);
      sendJson(res, 200, { countLabel });
      return;
    }

    const urlPath = url.pathname === "/" ? "/index.html" : url.pathname;
    const filePath = path.join(ROOT, urlPath);

    if (!filePath.startsWith(ROOT)) {
      res.writeHead(403);
      res.end("Forbidden");
      return;
    }

    fs.readFile(filePath, (err, data) => {
      if (err) {
        res.writeHead(404);
        res.end("Not found");
        return;
      }
      const ext = path.extname(filePath);
      const type = ext === ".html" ? "text/html" : "text/plain";
      res.writeHead(200, { "Content-Type": type });
      res.end(data);
    });
  });

  server.listen(PORT, "127.0.0.1", () => {
    console.log(`Grid navigator (ABCD count label) running at http://127.0.0.1:${PORT}/`);
    console.log("Press Ctrl+C to stop.");
  });
}

const args = process.argv.slice(2);
if (args.length >= 2 && args[0] === "--evaluate-once") {
  (async () => {
    await initClient();
    try {
      console.log(await evaluateCountLabel(args[1]));
    } finally {
      await closeClient();
    }
    process.exit(0);
  })();
} else {
  runServer().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}

process.on("SIGINT", async () => {
  await closeClient();
  process.exit(0);
});
