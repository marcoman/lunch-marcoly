#!/usr/bin/env node
/** Console grid navigator demonstrating LaunchDarkly targeting rules. */

const readline = require("readline");
const LaunchDarkly = require("@launchdarkly/node-server-sdk");
const { evaluateTeamStyle } = require("../team-style");

const ROWS = ["t", "m", "b"];
const COLS = ["l", "m", "r"];
const TEAMS = { 1: "", 2: "red", 3: "blue", 4: "yellow" };
const APP_BANNER = "13-flag-targeting-rules[node-console]";
const BG = "\x1b[48;5;236m";
const RESET = "\x1b[0m";
const STYLE_COLORS = {
  "colored-red": "\x1b[31m",
  "colored-blue": "\x1b[34m",
  "colored-yellow": "\x1b[33m",
};

let ldClient = null;

/** Initialize the server SDK without private context attributes. */
async function initLaunchDarkly() {
  const sdkKey = process.env.LD_SDK_KEY;
  if (!sdkKey) {
    console.error("Warning: LD_SDK_KEY not set — flag uses plain default.");
    return;
  }
  ldClient = LaunchDarkly.init(sdkKey);
  try {
    await ldClient.waitForInitialization({ timeout: 5 });
  } catch (_) {
    console.error("Warning: LaunchDarkly SDK did not initialize — flag uses plain default.");
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

function coloredTeam(style) {
  const color = STYLE_COLORS[style.style];
  return color ? `${color}${style.teamLabel}${RESET}${BG}` : style.teamLabel;
}

function render(username, row, col, previous, style) {
  process.stdout.write(`${BG}\x1b[2J\x1b[H`);
  console.log(APP_BANNER);
  console.log(`Name: ${username}`);
  console.log(`Team: ${coloredTeam(style)}`);
  console.log(`Current position: ${formatPos(row, col)}`);
  const previousText = previous ? formatPos(previous.row, previous.col) : "—";
  console.log(`Previous position: ${previousText}`);
  console.log("\nUse arrow keys or WASD to move (L to logout, Q to quit).\n");

  for (let r = 0; r < 3; r += 1) {
    const lines = [[], [], []];
    for (let c = 0; c < 3; c += 1) {
      const cell = drawCell(r === row && c === col);
      lines.forEach((line, index) => line.push(cell[index]));
    }
    lines.forEach((line) => console.log(line.join(" ")));
  }
}

/** Prompt for the user key and public team attribute used by targeting rules. */
function askLogin() {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => {
    console.log(APP_BANNER);
    console.log("Login\n");

    const askUsername = () => {
      rl.question("Username: ", (answer) => {
        const username = answer.trim();
        if (!username) {
          console.log("Username is required.");
          askUsername();
          return;
        }
        const askTeam = () => {
          rl.question("Team [1=None 2=Red 3=Blue 4=Yellow]: ", (choice) => {
            const team = TEAMS[choice.trim()];
            if (team === undefined) {
              console.log("Choose 1, 2, 3, or 4.");
              askTeam();
              return;
            }
            rl.close();
            resolve({ username, team });
          });
        };
        askTeam();
      });
    };
    askUsername();
  });
}

/** Re-evaluate the team style every 500 ms while navigating. */
function runGrid(username, team) {
  let row = 1;
  let col = 1;
  let previous = null;
  let style = { teamLabel: team ? `Team ${team[0].toUpperCase()}${team.slice(1)}` : "No team", style: "plain" };

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
        render(username, row, col, previous, style);
      }
    }

    const refreshStyle = async () => {
      if (!active) return;
      style = await evaluateTeamStyle(ldClient, username, team);
      if (active) render(username, row, col, previous, style);
    };

    readline.emitKeypressEvents(process.stdin);
    if (process.stdin.isTTY) process.stdin.setRawMode(true);
    process.stdin.resume();
    process.stdin.on("keypress", onKeypress);
    refreshStyle().then(() => {
      if (active) pollTimer = setInterval(refreshStyle, 500);
    });
  });
}

async function main() {
  await initLaunchDarkly();
  while (true) {
    const { username, team } = await askLogin();
    const action = await runGrid(username, team);
    if (action === "quit") {
      if (ldClient) ldClient.close();
      process.exit(0);
    }
  }
}

main();
