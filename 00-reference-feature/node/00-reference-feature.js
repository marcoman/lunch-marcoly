#!/usr/bin/env node
/** Serve the grid navigator web UI on a local HTTP server. */

const http = require("http");
const fs = require("fs");
const path = require("path");

const PORT = 8080;
const ROOT = __dirname;

const server = http.createServer((req, res) => {
  const urlPath = req.url === "/" ? "/index.html" : req.url;
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
  console.log(`Grid navigator running at http://127.0.0.1:${PORT}/`);
  console.log("Press Ctrl+C to stop.");
});
