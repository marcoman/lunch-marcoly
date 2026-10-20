#!/usr/bin/env node
/** Console grid navigator demonstrating LaunchDarkly multi-context targeting. */

const readline = require("readline");
const LaunchDarkly = require("@launchdarkly/node-server-sdk");
const { evaluatePartner } = require("../partner");

const ROWS = ["t", "m", "b"];
const COLS = ["l", "m", "r"];
const USERS = { 1: "alice", 2: "bob" };
const ORGS = { 1: "acme", 2: "globex" };
const APP_BANNER = "14-multi-context-targeting[node-console]";
const BG = "\x1b[48;5;236m";
const RESET = "\x1b[0m";
const GREEN = "\x1b[32m";

let ldClient = null;

/** Initialize the server SDK for user + organization multi-context evaluation. */
async function initLaunchDarkly() {
  const sdkKey = process.env.LD_SDK_KEY;
  if (!sdkKey) {
    console.error("Warning: LD_SDK_KEY not set — partner badge stays false.");
    return;
  }
  ldClient = LaunchDarkly.init(sdkKey);
  try {
    await ldClient.waitForInitialization({ timeout: 5 });
  } catch (_) {
    console.error("Warning: LaunchDarkly SDK did not initialize — partner badge stays false.");
    ldClient.close();
    ldClient = null;
  }
}

function formatPos(row, col) {
  return `${ROWS[row]}/${COLS[col]}`;
}

function tryMove(row, col, dr, dc) {
  const nextRow = Math.max(0, Math.min(2, row + dr));
  const nextCol = Math.max(0, Math.min(2, col + dc));
  return { row: nextRow, col: nextCol, moved: nextRow !== row || nextCol !== col };
}

function drawCell(selected) {
  return selected
    ? ["┏━━━┓", "┃ X ┃", "┗━━━┛"]
    : ["┌───┐", "│   │", "└───┘"];
}

function nameLine(username, flags) {
  if (!flags.partner) return `Name: ${username}`;
  return `Name: ${username}  ${GREEN}partner${RESET}${BG}`;
}

function render(username, org, row, col, previous, flags) {
  process.stdout.write(`${BG}\x1b[2J\x1b[H`);
  console.log(APP_BANNER);
  console.log(nameLine(username, flags));
  console.log(`Org: ${flags.orgLabel || org}`);
  console.log(`Current position: ${formatPos(row, col)}`);
  const previousText = previous ? formatPos(previous.row, previous.col) : "—";
  console.log(`Previous position: ${previousText}`);
  console.log("\n1/2 user Alice/Bob, 3/4 org Acme/Globex. Arrows or WASD. L logout, Q quit.\n");

  for (let r = 0; r < 3; r += 1) {
    const lines = [[], [], []];
    for (let c = 0; c < 3; c += 1) {
      const cell = drawCell(r === row && c === col);
      lines.forEach((line, index) => line.push(cell[index]));
    }
    lines.forEach((line) => console.log(line.join(" ")));
  }
}

/** Prompt for Alice/Bob and Acme/Globex — the two multi-context keys. */
function askLogin() {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => {
    console.log(APP_BANNER);
    console.log("Login\n");

    const askUser = () => {
      rl.question("User [1=Alice 2=Bob]: ", (answer) => {
        const username = USERS[answer.trim()];
        if (!username) {
          console.log("Choose 1 or 2.");
          askUser();
          return;
        }
        const askOrg = () => {
          rl.question("Org  [1=Acme 2=Globex]: ", (choice) => {
            const org = ORGS[choice.trim()];
            if (!org) {
              console.log("Choose 1 or 2.");
              askOrg();
              return;
            }
            rl.close();
            resolve({ username, org });
          });
        };
        askOrg();
      });
    };
    askUser();
  });
}

/** Re-evaluate the partner badge every 500 ms; 1–4 walk the 2×2 without logout. */
function runGrid(username, org) {
  let row = 1;
  let col = 1;
  let previous = null;
  let flags = { partner: false, orgLabel: org === "globex" ? "Globex" : "Acme" };

  return new Promise((resolve) => {
    let active = true;
    let pollTimer = null;

    function cleanup() {
      active = false;
      if (pollTimer) clearInterval(pollTimer);
      process.stdin.removeListener("keypress", onKeypress);
      if (process.stdin.isTTY) process.stdin.setRawMode(false);
      process.stdin.pause();
      process.stdout.write(RESET);
    }

    function onKeypress(str, key) {
      if (!active) return;
      if (key.ctrl && key.name === "c") {
        cleanup();
        resolve("quit");
        return;
      }

      if (str === "q" || str === "Q" || str === "l" || str === "L") {
        const action = str.toLowerCase() === "q" ? "quit" : "logout";
        cleanup();
        resolve(action);
        return;
      }
      if (str === "1") {
        username = "alice";
        return;
      }
      if (str === "2") {
        username = "bob";
        return;
      }
      if (str === "3") {
        org = "acme";
        return;
      }
      if (str === "4") {
        org = "globex";
        return;
      }

      let dr = 0;
      let dc = 0;
      if (key.name === "up" || str === "w" || str === "W") dr = -1;
      else if (key.name === "down" || str === "s" || str === "S") dr = 1;
      else if (key.name === "left" || str === "a" || str === "A") dc = -1;
      else if (key.name === "right" || str === "d" || str === "D") dc = 1;
      else return;

      const result = tryMove(row, col, dr, dc);
      if (result.moved) {
        previous = { row, col };
        row = result.row;
        col = result.col;
        render(username, org, row, col, previous, flags);
      }
    }

    const refresh = async () => {
      if (!active) return;
      flags = await evaluatePartner(ldClient, username, org);
      username = flags.username || username;
      org = flags.org || org;
      if (active) render(username, org, row, col, previous, flags);
    };

    readline.emitKeypressEvents(process.stdin);
    if (process.stdin.isTTY) process.stdin.setRawMode(true);
    process.stdin.resume();
    process.stdin.on("keypress", onKeypress);
    refresh().then(() => {
      if (active) pollTimer = setInterval(refresh, 500);
    });
  });
}

async function main() {
  await initLaunchDarkly();
  while (true) {
    const { username, org } = await askLogin();
    const action = await runGrid(username, org);
    if (action === "quit") {
      if (ldClient) ldClient.close();
      process.exit(0);
    }
  }
}

main();
