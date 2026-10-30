/**
 * Evaluate api-progressive-grid-highlight for one username.
 *
 * The schedule lives in an environment release. This function only reads
 * the variation.
 *
 * LaunchDarkly: string flag variation
 * https://launchdarkly.com/docs/sdk/features/evaluations
 */

const FLAG_HIGHLIGHT = "api-progressive-grid-highlight";
const VALID_COLORS = new Set(["yellow", "red", "blue", "green", "purple"]);

function buildContext(username) {
  return { kind: "user", key: username, name: username };
}

function normalizeHighlightColor(raw) {
  const color = String(raw || "none").trim().toLowerCase();
  return VALID_COLORS.has(color) ? color : "none";
}

function buildResponse(username, raw, reason, variationIndex) {
  const color = normalizeHighlightColor(raw);
  return {
    username,
    flagKey: FLAG_HIGHLIGHT,
    flagValue: String(raw ?? "none"),
    highlightColor: color,
    colorLabel: color === "none" ? "(no-color)" : `(${color})`,
    variationIndex: variationIndex ?? null,
    reason: reason || { kind: "ERROR", errorKind: "CLIENT_NOT_READY" },
    ldContext: buildContext(username),
  };
}

async function evaluateHighlight(client, username) {
  if (!client) return buildResponse(username, "none");
  const detail = await client.variationDetail(FLAG_HIGHLIGHT, buildContext(username), "none");
  const reason = detail && detail.reason ? detail.reason : { kind: "UNKNOWN" };
  return buildResponse(username, detail.value, reason, detail.variationIndex);
}

module.exports = { FLAG_HIGHLIGHT, evaluateHighlight };
