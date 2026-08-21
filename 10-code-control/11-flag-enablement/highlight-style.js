/** Resolve grid selection highlight color and cohort label from username context.
 *
 * enable-grid-selection-highlight is a string flag (none | colors).
 * Legacy boolean true/false is still accepted by interpretHighlightVariation.
 *
 * LaunchDarkly: feature flags — multivariate string variations
 * https://launchdarkly.com/docs/home/flags/concepts
 */

const { osEmojiFor } = require("./host-os");

// LaunchDarkly: flag key=enable-grid-selection-highlight
// name="Enable: grid selection highlight" kind=string
// https://app.launchdarkly.com/projects/lunch-marcoly/features/enable-grid-selection-highlight

const FLAG_HIGHLIGHT = "enable-grid-selection-highlight";
// LaunchDarkly: flag key=enable-grid-highlight-color-override
// name="Enable: grid highlight color override" kind=boolean
// https://app.launchdarkly.com/projects/lunch-marcoly/features/enable-grid-highlight-color-override

const FLAG_CONTEXT = "enable-grid-highlight-color-override";
// LaunchDarkly: flag key=show-navigation-move-count
// https://app.launchdarkly.com/projects/lunch-marcoly/features/show-navigation-move-count

const FLAG_COUNT = "show-navigation-move-count";

const VALID_COLORS = new Set([
  "pink",
  "yellow",
  "red",
  "blue",
  "green",
  "purple",
  "none",
]);

const DEFAULT_STRING_ON_COLOR = "green";

function parseCohorts(username) {
  const lower = username.toLowerCase();
  return {
    isHuman: lower.includes("human"),
    isRobot: lower.includes("robot"),
    isBeta: lower.includes("beta"),
  };
}

function colorLabelName(highlightColor) {
  return highlightColor === "none" ? "no-color" : highlightColor;
}

function formatCohortLabel(username, highlightColor, contextHighlight) {
  const colorName = colorLabelName(highlightColor);
  const parts = [];
  if (contextHighlight) {
    const { isHuman, isRobot, isBeta } = parseCohorts(username);
    if (isHuman) parts.push("human");
    if (isRobot) parts.push("robot");
    if (isBeta) parts.push("beta");
  }
  if (parts.length) {
    return `(${parts.join("-")}-${colorName})`;
  }
  return `(${colorName})`;
}

function isHighlightOffValue(value) {
  if (value === false || value == null) return true;
  if (typeof value === "string") {
    return ["", "none", "false", "off"].includes(value.trim().toLowerCase());
  }
  return false;
}

function interpretHighlightVariation(raw) {
  if (typeof raw === "boolean") return { enabled: raw, servedColor: null };
  if (isHighlightOffValue(raw)) return { enabled: false, servedColor: null };
  if (typeof raw === "string") {
    const color = raw.trim().toLowerCase();
    if (VALID_COLORS.has(color) && color !== "none") {
      return { enabled: true, servedColor: color };
    }
    return { enabled: true, servedColor: null };
  }
  return { enabled: Boolean(raw), servedColor: null };
}

function resolveHighlightColor(
  username,
  highlightEnabled,
  contextHighlight,
  servedColor = null
) {
  if (!highlightEnabled) {
    return "none";
  }

  if (contextHighlight) {
    const { isHuman, isRobot, isBeta } = parseCohorts(username);
    if (isHuman && isBeta) return "green";
    if (isRobot && isBeta) return "purple";
    if (isHuman) return "yellow";
    if (isRobot) return "red";
    if (isBeta) return "blue";
    if (servedColor && VALID_COLORS.has(servedColor) && servedColor !== "none") {
      return servedColor;
    }
    return "pink";
  }

  if (servedColor && VALID_COLORS.has(servedColor) && servedColor !== "none") {
    return servedColor;
  }
  return "pink";
}

function buildFlagResponse(
  username,
  highlightEnabled,
  contextHighlight,
  showMoveCount,
  showOsEmoji,
  hostOs,
  servedColor = null
) {
  const highlightColor = resolveHighlightColor(
    username,
    highlightEnabled,
    contextHighlight,
    servedColor
  );
  const cohortLabel = formatCohortLabel(
    username,
    highlightColor,
    contextHighlight
  );
  return {
    highlightEnabled,
    contextHighlight,
    showMoveCount,
    highlightColor,
    cohortLabel,
    osEmoji: osEmojiFor(hostOs, showOsEmoji),
    highlightServedValue:
      servedColor != null ? servedColor : highlightEnabled,
  };
}

module.exports = {
  FLAG_HIGHLIGHT,
  FLAG_CONTEXT,
  FLAG_COUNT,
  DEFAULT_STRING_ON_COLOR,
  interpretHighlightVariation,
  resolveHighlightColor,
  formatCohortLabel,
  buildFlagResponse,
};
