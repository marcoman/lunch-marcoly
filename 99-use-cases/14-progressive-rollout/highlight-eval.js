/** Evaluate enable-grid-selection-highlight for grid highlight color. */

const LaunchDarkly = require("@launchdarkly/node-server-sdk");

// LaunchDarkly capability: String flag evaluation (server-side SDK)
// See: https://launchdarkly.com/docs/sdk/features/evaluations

// LaunchDarkly: flag key=enable-grid-selection-highlight name="Enable: grid selection highlight" kind=string
// https://app.launchdarkly.com/projects/lunch-marcoly/features/enable-grid-selection-highlight

const FLAG_HIGHLIGHT = "enable-grid-selection-highlight";
const VALID_COLORS = new Set(["yellow", "red", "blue", "green", "purple"]);

function buildContext(username) {
  return { kind: "user", key: username };
}

function normalizeHighlightColor(raw) {
  const color = String(raw || "none")
    .trim()
    .toLowerCase();
  return VALID_COLORS.has(color) ? color : "none";
}

function colorLabel(highlightColor) {
  return highlightColor === "none" ? "(no-color)" : `(${highlightColor})`;
}

function buildResponse(username, raw) {
  const color = normalizeHighlightColor(raw);
  return {
    username,
    flagValue: String(raw ?? "none"),
    highlightColor: color,
    colorLabel: colorLabel(color),
  };
}

async function evaluateHighlight(client, username) {
  if (!client) {
    return buildResponse(username, "none");
  }
  const context = buildContext(username);
  const raw = await client.variation(FLAG_HIGHLIGHT, context, "none");
  return buildResponse(username, raw);
}

module.exports = {
  FLAG_HIGHLIGHT,
  buildContext,
  normalizeHighlightColor,
  colorLabel,
  buildResponse,
  evaluateHighlight,
};
