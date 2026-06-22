#!/usr/bin/env node
/** Console grid navigator with ABCD navigation count label (LaunchDarkly string flag). */

const readline = require("readline");
const { initClient, closeClient, evaluateCountLabel } = require("../abcd-eval.js");

// LaunchDarkly capability: String flag evaluation for multivariate A/B/C/D test
// See: https://launchdarkly.com/docs/sdk/features/flag-types

const ROWS = ["t", "m", "b"];
const COLS = ["l", "m", "r"];

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

function render(username, row, col, previous, moveCount, countLabel) {
  console.clear();
  const prevText = previous ? formatPos(previous.row, previous.col) : "—";
  console.log(`Name: ${username}`);
  console.log(`Current position: ${formatPos(row, col)}`);
  console.log(`Previous position: ${prevText}`);
  console.log(`${countLabel}: ${moveCount}`);
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
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });
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
  const countLabel = await evaluateCountLabel(username);

  return new Promise((resolve) => {
    const onKeypress = (str, key) => {
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
        moveCount += 1;
      }
      render(username, row, col, previous, moveCount, countLabel);
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

    render(username, row, col, previous, moveCount, countLabel);
  });
}

async function main() {
  await initClient();
  try {
    while (true) {
      const username = await askUsername();
      const action = await runGrid(username);
      if (action === "quit") break;
    }
  } finally {
    await closeClient();
  }
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
  main();
}
