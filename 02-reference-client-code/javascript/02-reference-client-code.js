#!/usr/bin/env node
/** Serve the browser grid navigator as static files. No LaunchDarkly. */

const http = require("http");
const fs = require("fs");
const path = require("path");

const PORT = Number.parseInt(process.env.PORT || "8020", 10);
const ROOT = __dirname;

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
};

const server = http.createServer((req, res) => {
  const raw = (req.url || "/").split("?")[0];
  const urlPath = raw === "/" ? "/index.html" : raw;
  const relative = path.normalize(decodeURIComponent(urlPath)).replace(/^[/\\]+/, "");
  const filePath = path.join(ROOT, relative);

  if (!filePath.startsWith(ROOT + path.sep) && filePath !== ROOT) {
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
    res.writeHead(200, {
      "Content-Type": MIME[ext] || "text/plain; charset=utf-8",
      "Cache-Control": "no-store",
    });
    res.end(data);
  });
});

server.listen(PORT, "127.0.0.1", () => {
  console.log("02-reference-client-code[javascript]");
  console.log(`Grid navigator running at http://127.0.0.1:${PORT}/`);
  console.log("Press Ctrl+C to stop.");
});
