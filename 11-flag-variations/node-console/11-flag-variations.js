#!/usr/bin/env node
/** Console grid navigator with LaunchDarkly flag variation evaluation. */

const readline = require("readline");
const LaunchDarkly = require("@launchdarkly/node-server-sdk");
const { evaluateFlags, buildFlagResponse } = require("../flag-variations");
const { detectHostOs, HOST_OS_ATTR } = require("../host-os");

// LaunchDarkly capability: Multivariate flag evaluation + anonymous contexts
// See: https://launchdarkly.com/docs/sdk/features/flag-types
// See: https://launchdarkly.com/docs/sdk/features/anonymous

const ROWS = ["t", "m", "b"];
const COLS = ["l", "m", "r"];
const HOST_OS = detectHostOs();
const BG = "\x1b[48;5;236m";

let ldClient = null;

async function initLaunchDarkly() {
  const sdkKey = process.env.LD_SDK_KEY;
  if (!sdkKey) {
    console.error("Warning: LD_SDK_KEY not set — flags default to off.");
    return;
  }
  ldClient = LaunchDarkly.init(sdkKey, { privateAttributes: [HOST_OS_ATTR] });
  try {
    await ldClient.waitForInitialization({ timeout: 5 });
  } catch (_) {
    console.error("Warning: LaunchDarkly SDK did not initialize — flags default to off.");
    ldClient = null;
  }
}

function displayName(username, flags) {
  const emoji = flags.osEmoji || "";
  return emoji ? `${emoji} ${username}` : username;
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

function drawCell(selected) {
  if (selected) {
    return ["┏━━━┓", "┃ X ┃", "┗━━━┛"];
  }
  return ["┌───┐", "│   │", "└───┘"];
}

function render(username, row, col, previous, moveCount, flags) {
  process.stdout.write(`${BG}\x1b[2J\x1b[H`);
  const prevText = previous ? formatPos(previous.row, previous.col) : "—";
  console.log(`Name: ${displayName(username, flags)}`);
  console.log(`Current position: ${formatPos(row, col)}`);
  console.log(`Previous position: ${prevText}`);
  console.log(`${flags.countLabel}: ${moveCount}`);
  console.log(`Lucky Number is: ${flags.luckyNumber}`);
  console.log("\nUse arrow keys or WASD to move (L to logout, Q to quit).\n");

  for (let r = 0; r < 3; r++) {
    const topLine = [];
    const midLine = [];
    const botLine = [];
    for (let c = 0; c < 3; c++) {
      const lines = drawCell(r === row && c === col);
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
  let moveCount = 0;
  let flags = buildFlagResponse("Count", 0, 100, "");

  return new Promise((resolve) => {
    let active = true;

    const onKeypress = async (str, key) => {
      if (!active) return;
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

      if (moveCount >= flags.maxMoves) return;

      const result = tryMove(row, col, dr, dc);
      if (result.moved) {
        previous = { row, col };
        row = result.row;
        col = result.col;
        moveCount += 1;
      }
      flags = await evaluateFlags(ldClient, username, HOST_OS);
      if (!active) return;
      render(username, row, col, previous, moveCount, flags);
    };

    let pollTimer = null;

    function cleanup() {
      active = false;
      if (pollTimer) clearInterval(pollTimer);
      pollTimer = null;
      process.stdin.removeListener("keypress", onKeypress);
      if (process.stdin.isTTY) process.stdin.setRawMode(false);
      process.stdin.pause();
    }

    const refreshFlags = async () => {
      if (!active) return;
      flags = await evaluateFlags(ldClient, username, HOST_OS);
      if (!active) return;
      render(username, row, col, previous, moveCount, flags);
    };

    readline.emitKeypressEvents(process.stdin);
    if (process.stdin.isTTY) process.stdin.setRawMode(true);
    process.stdin.resume();
    process.stdin.on("keypress", onKeypress);

    refreshFlags().then(() => {
      pollTimer = setInterval(refreshFlags, 500);
    });
  });
}

async function main() {
  await initLaunchDarkly();
  while (true) {
    const username = await askUsername();
    const action = await runGrid(username);
    if (action === "quit") {
      if (ldClient) ldClient.close();
      process.exit(0);
    }
  }
}

main();
