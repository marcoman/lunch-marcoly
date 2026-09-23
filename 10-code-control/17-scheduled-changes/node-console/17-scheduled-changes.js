#!/usr/bin/env node
/** Console grid navigator for LaunchDarkly scheduled flag changes. */

const readline = require("readline");
const LaunchDarkly = require("@launchdarkly/node-server-sdk");
const {
  apiConfig,
  evaluateHighlight,
  listScheduledChanges,
  startScheduledChange,
  stopScheduledChange,
} = require("../scheduled-change");

// LaunchDarkly: scheduled flag changes — the server SDK re-evaluates; the
// REST API owns executionDate. https://launchdarkly.com/docs/home/flags/scheduled-changes

const ROWS = ["t", "m", "b"];
const COLS = ["l", "m", "r"];
const DELAYS = [1, 2, 5, 10];
const APP_BANNER = "17-scheduled-changes[node-console]";
const GREEN = "\x1b[92m";
const DIM = "\x1b[2m";
const BOLD = "\x1b[1m";
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

function clockMs(ms) {
  const seconds = Math.floor(Math.max(0, ms) / 1000);
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${String(secs).padStart(2, "0")}`;
}

function nowMs() {
  return Date.now();
}

function wall(ms) {
  if (!ms) return "—";
  const d = new Date(ms);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

function statusLine({ pending, startedAt, stoppedAt, observedAt, executionDate, green }) {
  if (pending) {
    return {
      status: "PENDING · LaunchDarkly will turn the flag on",
      when: `Scheduled wall time: ${wall(executionDate)}`,
    };
  }
  if (stoppedAt) {
    const elapsed = startedAt ? ` after ${clockMs(stoppedAt - startedAt)} elapsed` : "";
    return {
      status: "STOPPED · pending change cancelled, flag off",
      when: `Stopped at ${wall(stoppedAt)}${elapsed}.`,
    };
  }
  if (green && startedAt) {
    const observed = observedAt
      ? `; green first observed here at ${clockMs(observedAt - startedAt)}`
      : "";
    return {
      status: "APPLIED · SDK now serves green",
      when: `Scheduled for ${wall(executionDate)}${observed}.`,
    };
  }
  return {
    status: "No pending change.",
    when: "G starts a schedule. T stops it and turns the flag off.",
  };
}

function render(state, flags) {
  const {
    username,
    row,
    col,
    previous,
    delay,
    startedAt,
    stoppedAt,
    observedAt,
    executionDate,
    pending,
    restOk,
    error,
  } = state;
  process.stdout.write(`${BG}\x1b[2J\x1b[H`);
  const color = flags.highlightColor || "none";
  const reasonKind = (flags.reason && flags.reason.kind) || "UNKNOWN";
  const variation = flags.variationIndex == null ? "default" : String(flags.variationIndex);
  const prevText = previous ? formatPos(previous.row, previous.col) : "—";
  const end = stoppedAt || nowMs();
  const elapsed = startedAt ? clockMs(end - startedAt) : "0:00";
  const { status, when } = statusLine({
    pending,
    startedAt,
    stoppedAt,
    observedAt,
    executionDate,
    green: color === "green",
  });
  const rest = restOk
    ? "REST configured"
    : "REST disabled — set LD_API_ACCESS_TOKEN, LD_PROJECT_KEY, LD_ENVIRONMENT_KEY";

  console.log(APP_BANNER);
  console.log(`Name: ${colorize(username, color)}${RESET}${BG}`);
  console.log(`Current: ${formatPos(row, col)}   Previous: ${prevText}`);
  console.log(`Flag value: ${flags.flagValue}   reason: ${reasonKind}   idx: ${variation}`);
  console.log(`Delay: ${delay} min   Elapsed: ${elapsed}`);
  console.log(status);
  console.log(when);
  console.log(rest);
  console.log("G start  T stop  M delay  1/2/5/0=10 min  arrows/WASD  L logout  Q quit");
  console.log(
    `${DIM}Lag is normal: LD executes near the date, the SDK stream follows, this loop polls ~500ms.${RESET}${BG}`,
  );
  if (error) console.log(`${BOLD}${error}${RESET}${BG}`);
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

function runGrid(username) {
  const state = {
    username,
    row: 1,
    col: 1,
    previous: null,
    delayIndex: 0,
    delay: DELAYS[0],
    startedAt: null,
    stoppedAt: null,
    observedAt: null,
    executionDate: null,
    pending: null,
    restOk: false,
    error: "",
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
      if (str === "m" || str === "M") {
        state.delayIndex = (state.delayIndex + 1) % DELAYS.length;
        state.delay = DELAYS[state.delayIndex];
        await refresh();
        return;
      }
      if (str === "1") {
        state.delayIndex = 0;
        state.delay = DELAYS[0];
        await refresh();
        return;
      }
      if (str === "2") {
        state.delayIndex = 1;
        state.delay = DELAYS[1];
        await refresh();
        return;
      }
      if (str === "5") {
        state.delayIndex = 2;
        state.delay = DELAYS[2];
        await refresh();
        return;
      }
      if (str === "0") {
        state.delayIndex = 3;
        state.delay = DELAYS[3];
        await refresh();
        return;
      }
      if (str === "g" || str === "G") {
        try {
          const result = await startScheduledChange(DELAYS[state.delayIndex]);
          if (!active) return;
          state.startedAt = result.startedAt;
          state.executionDate = result.scheduledChange.executionDate;
          state.stoppedAt = null;
          state.observedAt = null;
          state.pending = result.scheduledChange;
          state.error = "";
        } catch (exc) {
          state.error = String(exc.message || exc);
        }
        await refresh();
        return;
      }
      if (str === "t" || str === "T") {
        try {
          const result = await stopScheduledChange();
          if (!active) return;
          state.stoppedAt = result.stoppedAt;
          state.pending = null;
          state.error = "";
        } catch (exc) {
          state.error = String(exc.message || exc);
        }
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
      // Feature flags — detailed variation; the SDK stream is the source of highlight.
      // Do not flip green from a local countdown. Poll ~500ms to observe LD.
      // https://docs.launchdarkly.com/sdk/features/evaluating#evaluation-reasons
      const flags = await evaluateHighlight(ldClient, state.username);
      if (!active) return;
      if (
        state.startedAt &&
        !state.stoppedAt &&
        !state.observedAt &&
        flags.highlightColor === "green"
      ) {
        state.observedAt = nowMs();
      }
      const rest = apiConfig();
      state.restOk = Boolean(rest.configured);
      try {
        const listed = await listScheduledChanges();
        if (!active) return;
        state.pending = (listed.items || [null])[0] || null;
        if (state.pending) {
          state.executionDate = state.pending.executionDate || state.executionDate;
          state.startedAt = state.startedAt || state.pending.createdAt;
        }
      } catch (_) {
        state.pending = null;
      }
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
