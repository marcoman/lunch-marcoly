#!/usr/bin/env node
/** Console grid navigator with LaunchDarkly flag evaluation. */

const readline = require("readline");
const LaunchDarkly = require("@launchdarkly/node-server-sdk");
const {
  FLAG_HIGHLIGHT,
  FLAG_CONTEXT,
  FLAG_COUNT,
  buildFlagResponse,
} = require("../highlight-style");
const { detectHostOs, HOST_OS_ATTR, FLAG_OS_EMOJI } = require("../host-os");

// LaunchDarkly capability: Boolean flag evaluation + private context attributes
// See: https://launchdarkly.com/docs/sdk/features/private-attributes

const ROWS = ["t", "m", "b"];
const COLS = ["l", "m", "r"];
const HOST_OS = detectHostOs();
const ANSI = {
  pink: "\x1b[95m",
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
  ldClient = LaunchDarkly.init(sdkKey, { privateAttributes: [HOST_OS_ATTR] });
  try {
    await ldClient.waitForInitialization({ timeout: 5 });
  } catch (_) {
    ldClient = null;
  }
}

async function evaluateFlags(username) {
  if (!ldClient) return buildFlagResponse(username, false, false, false, false, HOST_OS);
  const context = {
    kind: "user",
    key: username,
    hostOs: HOST_OS,
    privateAttributes: [HOST_OS_ATTR],
  };
  const highlightEnabled = await ldClient.variation(FLAG_HIGHLIGHT, context, false);
  const contextHighlight = await ldClient.variation(FLAG_CONTEXT, context, false);
  const showMoveCount = await ldClient.variation(FLAG_COUNT, context, false);
  const showOsEmoji = await ldClient.variation(FLAG_OS_EMOJI, context, false);
  return buildFlagResponse(
    username,
    Boolean(highlightEnabled),
    Boolean(contextHighlight),
    Boolean(showMoveCount),
    Boolean(showOsEmoji),
    HOST_OS
  );
}

function displayName(username, osEmoji) {
  return osEmoji ? `${osEmoji} ${username}` : username;
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
  const namePart = colorize(displayName(username, flags.osEmoji), color);
  const cohort = colorize(` ${flags.cohortLabel}`, color);
  return `Name: ${namePart}${cohort}${RESET}${BG}`;
}

function render(username, row, col, previous, moveCount, flags) {
  process.stdout.write(`${BG}\x1b[2J\x1b[H`);
  const prevText = previous ? formatPos(previous.row, previous.col) : "—";
  console.log(formatNameLine(username, flags));
  console.log(`Current position: ${formatPos(row, col)}`);
  console.log(`Previous position: ${prevText}`);
  if (flags.showMoveCount) {
    console.log(`Count: ${moveCount}`);
  }
  console.log("\nUse arrow keys or WASD to move (q to quit).\n");

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

async function runGrid(username) {
  let row = 1;
  let col = 1;
  let previous = null;
  let moveCount = 0;
  let flags = buildFlagResponse(username, false, false, false, false, HOST_OS);

  readline.emitKeypressEvents(process.stdin);
  if (process.stdin.isTTY) process.stdin.setRawMode(true);
  process.stdin.resume();

  const refreshFlags = async () => {
    flags = await evaluateFlags(username);
    render(username, row, col, previous, moveCount, flags);
  };

  await refreshFlags();
  const pollTimer = setInterval(refreshFlags, 500);

  process.stdin.on("keypress", async (str, key) => {
    if (key.ctrl && key.name === "c") {
      clearInterval(pollTimer);
      process.stdin.setRawMode(false);
      process.stdin.pause();
      if (ldClient) ldClient.close();
      process.exit(0);
    }
    let dir = null;
    if (key.name === "up" || str === "w" || str === "W") dir = "up";
    else if (key.name === "down" || str === "s" || str === "S") dir = "down";
    else if (key.name === "left" || str === "a" || str === "A") dir = "left";
    else if (key.name === "right" || str === "d" || str === "D") dir = "right";
    else if (str === "q" || str === "Q") dir = "quit";
    if (dir === "quit") {
      clearInterval(pollTimer);
      process.stdin.setRawMode(false);
      process.stdin.pause();
      if (ldClient) ldClient.close();
      process.exit(0);
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
      moveCount += 1;
    }
    flags = await evaluateFlags(username);
    render(username, row, col, previous, moveCount, flags);
  });
}

initLaunchDarkly().then(() => askUsername().then(runGrid));
