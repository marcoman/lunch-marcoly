/**
 * Evaluate the adaptive highlight flag for one user context.
 * LaunchDarkly: server-side string variation with a code fallback of `none`.
 * https://launchdarkly.com/docs/sdk/features/evaluations
 */
const FLAG_HIGHLIGHT = "enable-adaptive-grid-highlight";
const VALID_COLORS = new Set(["green"]);

function buildContext(username) {
  return { kind: "user", key: username };
}

function buildResponse(username, raw) {
  const value = String(raw ?? "none").trim().toLowerCase();
  const highlightColor = VALID_COLORS.has(value) ? value : "none";
  return {
    username,
    flagValue: value,
    highlightColor,
    colorLabel: highlightColor === "none" ? "(no-color)" : `(${highlightColor})`,
  };
}

async function evaluateHighlight(client, username) {
  if (!client) return buildResponse(username, "none");
  const raw = await client.variation(FLAG_HIGHLIGHT, buildContext(username), "none");
  return buildResponse(username, raw);
}

module.exports = { FLAG_HIGHLIGHT, buildContext, evaluateHighlight };
