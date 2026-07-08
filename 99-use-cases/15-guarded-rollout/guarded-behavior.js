/** Simulated guarded-release behavior when the highlight flag serves green. */

const LATENCY_THRESHOLD_MS = 200;
const LATENCY_FAIL_TOLERANCE = 0.1;
const ERROR_COLOR_CHANCE = 0.05;
const MIN_NAVIGATIONS = 5;
const MOVEMENT_THRESHOLD = 1;
const SKIP_NAV_CHANCE = 0.05;
const MAX_LATENCY_MS = 1000;
const WRONG_COLORS = ["yellow", "red", "blue", "purple"];

function isFlagEnabled(highlightColor) {
  return highlightColor === "green";
}

function rngFor(username, seed) {
  let state = seed ?? hashString(username);
  return () => {
    state = (state * 1664525 + 1013904223) >>> 0;
    return state / 0x100000000;
  };
}

function hashString(value) {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (Math.imul(31, hash) + value.charCodeAt(i)) >>> 0;
  }
  return hash;
}

function sampleLatencyMs(next) {
  return Math.floor(next() * (MAX_LATENCY_MS + 1));
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function sampleDisplayColor(expected, next) {
  if (expected !== "green") return { displayed: expected, correct: true };
  if (next() < ERROR_COLOR_CHANCE) {
    const wrong = WRONG_COLORS[Math.floor(next() * WRONG_COLORS.length)];
    return { displayed: wrong, correct: false };
  }
  return { displayed: expected, correct: true };
}

function assessLatency(latencyMs, flagEnabled) {
  if (!flagEnabled || latencyMs.length === 0) return { failures: 0, failure: false };
  const failures = latencyMs.filter((ms) => ms >= LATENCY_THRESHOLD_MS).length;
  return { failures, failure: failures / latencyMs.length > LATENCY_FAIL_TOLERANCE };
}

async function exerciseSession(flags, { skipNavigation = false, seed } = {}) {
  const username = String(flags.username ?? "");
  const expected = String(flags.highlightColor ?? "none");
  const flagEnabled = isFlagEnabled(expected);
  const next = rngFor(username, seed);

  const result = {
    ...flags,
    expectedColor: expected,
    skippedNavigation: skipNavigation,
    guardrailsActive: flagEnabled,
  };

  if (skipNavigation) {
    return {
      ...result,
      navigations: 0,
      latencyMs: [],
      latencyFailures: 0,
      latencyFailure: false,
      displayedColors: [],
      colorErrors: 0,
      errorRateFailure: false,
      movementFailure: true,
    };
  }

  const latencyMs = [];
  const displayedColors = [];
  let colorErrors = 0;

  for (let i = 0; i < MIN_NAVIGATIONS; i += 1) {
    if (flagEnabled) {
      const ms = sampleLatencyMs(next);
      await sleep(ms);
      latencyMs.push(ms);
      const { displayed, correct } = sampleDisplayColor(expected, next);
      displayedColors.push(displayed);
      if (!correct) colorErrors += 1;
    } else {
      latencyMs.push(0);
      displayedColors.push(expected);
    }
  }

  const { failures, failure } = assessLatency(latencyMs, flagEnabled);

  return {
    ...result,
    navigations: MIN_NAVIGATIONS,
    latencyMs,
    latencyFailures: failures,
    latencyFailure: failure,
    displayedColors,
    colorErrors,
    errorRateFailure: flagEnabled && colorErrors > 0,
    movementFailure: MIN_NAVIGATIONS < MOVEMENT_THRESHOLD,
  };
}

module.exports = {
  SKIP_NAV_CHANCE,
  isFlagEnabled,
  rngFor,
  sampleLatencyMs,
  sleep,
  sampleDisplayColor,
  exerciseSession,
};
