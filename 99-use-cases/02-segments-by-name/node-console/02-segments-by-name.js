#!/usr/bin/env node
/** Console grid navigator with LaunchDarkly segment-by-name highlight. */

const readline = require("readline");
const LaunchDarkly = require("@launchdarkly/node-server-sdk");
const { evaluateHighlight } = require("../segment-style");

// LaunchDarkly capability: String flag variation from segment targeting
// See: https://launchdarkly.com/docs/home/flags/segments

const ROWS = ["t", "m", "b"];
const COLS = ["l", "m", "r"];
const ANSI = {
  yellow: "\x1b[93m",
  red: "\x1b[91m",
  blue: "\x1b[94m",
  green: "\x1b[92m",
  purple: "\x1b[35m",
};
const BG = "\x1b[48;5;236m";
const RESET = "\x1b[0m";

let ldClient = null;

async function initLaunchDarkly() {
  const sdkKey = process.env.LD_SDK_KEY;
  if (!sdkKey) return;
  ldClient = LaunchDarkly.init(sdkKey);
  try {
    await ldClient.waitForInitialization({ timeout: 5 });
  } catch (_) {
    ldClient = null;
  }
}

function formatPos(row, col) {
  return `${ROWS[row]}/${COLS[col]}`;
}

function tryMove(row, col, dr, dc) {
  const nr = Math.max(0, Math.min(2, row + dr));
  const nc = Math.max(0, Math.min(2, col + dc));
  if (nr === row && nc === col) return { row, col, moved: false };
  return { row: nr, col: nc, moved: true };
}

function colorize(text, color) {
  if (!color || color === "none" || !ANSI[color]) return text;
  return `${ANSI[color]}${text}${RESET}${BG}`;
}

function drawCell(selected, color) {
  if (selected) {
    const lines = ["┏━━━┓", "┃ X ┃", "┗━━━┛"];
    if (color && color !== "none") {
      return lines.map((line) => colorize(line, color));
    }
    return lines;
  }
  return ["┌───┐", "│   │", "└───┘"];
}

function formatNameLine(username, flags) {
  const color = flags.highlightColor;
  const namePart = colorize(username, color);
  const label = colorize(` ${flags.segmentLabel}`, color);
  return `Name: ${namePart}${label}${RESET}${BG}`;
}

function render(username, row, col, previous, flags) {
  process.stdout.write(`${BG}\x1b[2J\x1b[H`);
  const prevText = previous ? formatPos(previous.row, previous.col) : "—";
  console.log(formatNameLine(username, flags));
  console.log(`Current position: ${formatPos(row, col)}`);
  console.log(`Previous position: ${prevText}`);
  console.log("\nUse arrow keys or WASD to move (L to logout, Q to quit).\n");

  const cellColor = flags.highlightColor;
  for (let r = 0; r < 3; r++) {
    const topLine = [];
    const midLine = [];
    const botLine = [];
    for (let c = 0; c < 3; c++) {
      const lines = drawCell(r === row && c === col, cellColor);
      topLine.push(lines[0]);
      midLine.push(lines[1]);
      botLine.push(lines[2]);
    }
    console.log(topLine.join(" "));
    console.log(midLine.join(" "));
    console.log(botLine.join(" "));
  }
}

function askUsername() {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => {
    const prompt = () => {
      rl.question("Username: ", (answer) => {
        const name = answer.trim();
        if (!name) {
          console.log("Username is required.");
          prompt();
          return;
        }
        rl.close();
        resolve(name);
      });
    };
    console.log("Login\n");
    prompt();
  });
}

function runGrid(username) {
  let row = 1;
  let col = 1;
  let previous = null;
  let flags = { highlightColor: "none", segmentLabel: "", segmentType: "" };

  return new Promise((resolve) => {
    const onKeypress = async (str, key) => {
      if (key.ctrl && key.name === "c") {
        cleanup();
        resolve("quit");
        return;
      }
      let dir = null;
      if (key.name === "up" || str === "w" || str === "W") dir = "up";
      else if (key.name === "down" || str === "s" || str === "S") dir = "down";
      else if (key.name === "left" || str === "a" || str === "A") dir = "left";
      else if (key.name === "right" || str === "d" || str === "D") dir = "right";
      else if (str === "q" || str === "Q") dir = "quit";
      else if (str === "l" || str === "L") dir = "logout";
      if (dir === "quit" || dir === "logout") {
        cleanup();
        resolve(dir);
        return;
      }
      if (!dir) return;

      let dr = 0;
      let dc = 0;
      if (dir === "up") dr = -1;
      else if (dir === "down") dr = 1;
      else if (dir === "left") dc = -1;
      else if (dir === "right") dc = 1;

      const result = tryMove(row, col, dr, dc);
      if (result.moved) {
        previous = { row, col };
        row = result.row;
        col = result.col;
      }
      render(username, row, col, previous, flags);
    };

    function cleanup() {
      process.stdin.removeListener("keypress", onKeypress);
      if (process.stdin.isTTY) process.stdin.setRawMode(false);
      process.stdin.pause();
    }

    readline.emitKeypressEvents(process.stdin);
    if (process.stdin.isTTY) process.stdin.setRawMode(true);
    process.stdin.resume();
    process.stdin.on("keypress", onKeypress);

    evaluateHighlight(ldClient, username).then((result) => {
      flags = result;
      render(username, row, col, previous, flags);
    });
  });
}

async function main() {
  await initLaunchDarkly();
  try {
    while (true) {
      const username = await askUsername();
      const action = await runGrid(username);
      if (action === "quit") break;
    }
  } finally {
    if (ldClient) await ldClient.close();
  }
}

const args = process.argv.slice(2);
if (args.length >= 2 && args[0] === "--evaluate-once") {
  (async () => {
    await initLaunchDarkly();
    try {
      const result = await evaluateHighlight(ldClient, args[1]);
      console.log(JSON.stringify(result));
    } finally {
      if (ldClient) await ldClient.close();
    }
    process.exit(0);
  })();
} else {
  main();
}
