#!/usr/bin/env node
/** Console grid navigator for a static LaunchDarkly percentage rollout. */

const readline = require("readline");
const LaunchDarkly = require("@launchdarkly/node-server-sdk");
const { evaluateRollout } = require("../rollout");

// LaunchDarkly: percentage rollout — sticky assignment by context key.
// https://launchdarkly.com/docs/home/flags/rollouts

const ROWS = ["t", "m", "b"];
const COLS = ["l", "m", "r"];
const APP_BANNER = "16-percentage-rollout[node-console]";
const CONFIGURED_GREEN_PCT = 30;
const HISTORY_LIMIT = 8;
const GREEN = "\x1b[92m";
const BG = "\x1b[48;5;236m";
const RESET = "\x1b[0m";

let ldClient = null;

async function initLaunchDarkly() {
  const sdkKey = (process.env.LD_SDK_KEY || "").trim();
  if (!sdkKey) return;
  ldClient = LaunchDarkly.init(sdkKey);
  try {
    await ldClient.waitForInitialization({ timeout: 5 });
  } catch (_) {
    ldClient.close();
    ldClient = null;
  }
}

function generatedUsername(base, index) {
  return index <= 0 ? base : `${base}${index}`;
}

function formatPos(row, col) {
  return `${ROWS[row]}/${COLS[col]}`;
}

function tryMove(row, col, dr, dc) {
  const nr = Math.max(0, Math.min(2, row + dr));
  const nc = Math.max(0, Math.min(2, col + dc));
  return { row: nr, col: nc, moved: nr !== row || nc !== col };
}

function colorize(text, color) {
  if (color !== "green") return text;
  return `${GREEN}${text}${RESET}${BG}`;
}

function drawCell(selected, color) {
  if (selected) {
    const lines = ["┏━━━┓", "┃ X ┃", "┗━━━┛"];
    return color === "green" ? lines.map((line) => colorize(line, color)) : lines;
  }
  return ["┌───┐", "│   │", "└───┘"];
}

function observedLine(seen) {
  const total = seen.size;
  if (!total) return "Observed: no unique keys yet.";
  let greenCount = 0;
  for (const value of seen.values()) if (value === "green") greenCount += 1;
  const noneCount = total - greenCount;
  const pct = Math.round((greenCount / total) * 1000) / 10;
  return (
    `Observed: ${greenCount} green / ${noneCount} none of ${total} unique ` +
    `→ ${pct}% (configured ${CONFIGURED_GREEN_PCT}%)`
  );
}

function navHint(nextName, previousName) {
  const prev = previousName || "—";
  return `Arrows/WASD move.  N next (${nextName})  P prev (${prev})  L logout  Q quit`;
}

function remember(username, flags, seen, history) {
  const value = flags.flagValue || "none";
  const reason = (flags.reason && flags.reason.kind) || "UNKNOWN";
  seen.set(username, value);
  const next = history.filter((item) => item.username !== username);
  next.unshift({ username, value, reason });
  history.length = 0;
  history.push(...next.slice(0, HISTORY_LIMIT));
}

function render(state, flags) {
  const { username, index, base, row, col, previous, seen, history } = state;
  process.stdout.write(`${BG}\x1b[2J\x1b[H`);
  const color = flags.highlightColor || "none";
  const reasonKind = (flags.reason && flags.reason.kind) || "UNKNOWN";
  const variation = flags.variationIndex == null ? "default" : String(flags.variationIndex);
  const prevText = previous ? formatPos(previous.row, previous.col) : "—";
  console.log(APP_BANNER);
  console.log(`Name: ${colorize(username, color)}${RESET}${BG}`);
  console.log(`Current: ${formatPos(row, col)}   Previous: ${prevText}`);
  console.log(`Flag value: ${flags.flagValue}   reason: ${reasonKind}   idx: ${variation}`);
  console.log(observedLine(seen));
  console.log(
    navHint(
      generatedUsername(base, index + 1),
      index === 0 ? null : generatedUsername(base, index - 1)
    )
  );
  console.log("");
  for (let r = 0; r < 3; r++) {
    const top = [];
    const mid = [];
    const bot = [];
    for (let c = 0; c < 3; c++) {
      const selected = r === row && c === col;
      const lines = drawCell(selected, selected ? color : "none");
      top.push(lines[0]);
      mid.push(lines[1]);
      bot.push(lines[2]);
    }
    console.log(top.join(" "));
    console.log(mid.join(" "));
    console.log(bot.join(" "));
  }
  console.log("");
  console.log("Recent evaluations");
  if (!history.length) console.log("(none yet)");
  for (const item of history) {
    console.log(colorize(`${item.username}  ${item.value}  ${item.reason}`, item.value));
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
    console.log(APP_BANNER);
    console.log("Login");
    console.log("Username becomes the LaunchDarkly user context key.\n");
    prompt();
  });
}

function runGrid(base) {
  const state = {
    base,
    index: 0,
    username: generatedUsername(base, 0),
    row: 1,
    col: 1,
    previous: null,
    seen: new Map(),
    history: [],
  };

  return new Promise((resolve) => {
    let active = true;

    const onKeypress = async (str, key) => {
      if (!active) return;
      if (key.ctrl && key.name === "c") {
        cleanup();
        resolve("quit");
        return;
      }
      if (str === "q" || str === "Q") {
        cleanup();
        resolve("quit");
        return;
      }
      if (str === "l" || str === "L") {
        cleanup();
        resolve("logout");
        return;
      }
      if (str === "n" || str === "N") {
        state.index += 1;
        state.username = generatedUsername(base, state.index);
        state.row = 1;
        state.col = 1;
        state.previous = null;
        await refresh();
        return;
      }
      if (str === "p" || str === "P") {
        if (state.index === 0) return;
        state.index -= 1;
        state.username = generatedUsername(base, state.index);
        state.row = 1;
        state.col = 1;
        state.previous = null;
        await refresh();
        return;
      }

      let dr = 0;
      let dc = 0;
      if (key.name === "up" || str === "w" || str === "W") dr = -1;
      else if (key.name === "down" || str === "s" || str === "S") dr = 1;
      else if (key.name === "left" || str === "a" || str === "A") dc = -1;
      else if (key.name === "right" || str === "d" || str === "D") dc = 1;
      else return;

      const result = tryMove(state.row, state.col, dr, dc);
      if (result.moved) {
        state.previous = { row: state.row, col: state.col };
        state.row = result.row;
        state.col = result.col;
      }
      await refresh();
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

    async function refresh() {
      if (!active) return;
      const flags = await evaluateRollout(ldClient, state.username);
      if (!active) return;
      remember(state.username, flags, state.seen, state.history);
      render(state, flags);
    }

    readline.emitKeypressEvents(process.stdin);
    if (process.stdin.isTTY) process.stdin.setRawMode(true);
    process.stdin.resume();
    process.stdin.on("keypress", onKeypress);
    refresh().then(() => {
      pollTimer = setInterval(refresh, 500);
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
