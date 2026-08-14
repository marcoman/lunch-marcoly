/** Resolve grid selection highlight color and cohort label from username context. */

const { osEmojiFor } = require("./host-os");

// LaunchDarkly: flag key=configure-grid-selection-green-highlight name="Configure: grid selection green highlight" kind=boolean
// https://app.launchdarkly.com/projects/lunch-marcoly/features/configure-grid-selection-green-highlight

const FLAG_HIGHLIGHT = "configure-grid-selection-green-highlight";
// LaunchDarkly: flag key=configure-grid-selection-context-highlight name="Configure: grid selection context highlight" kind=boolean
// https://app.launchdarkly.com/projects/lunch-marcoly/features/configure-grid-selection-context-highlight

const FLAG_CONTEXT = "configure-grid-selection-context-highlight";
// LaunchDarkly: flag key=show-navigation-move-count name="Show: navigation move count" kind=boolean
// https://app.launchdarkly.com/projects/lunch-marcoly/features/show-navigation-move-count

const FLAG_COUNT = "show-navigation-move-count";

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

function resolveHighlightColor(username, highlightEnabled, contextHighlight) {
  if (!highlightEnabled) {
    return "none";
  }
  if (!contextHighlight) {
    return "pink";
  }

  const { isHuman, isRobot, isBeta } = parseCohorts(username);

  if (isHuman && isBeta) return "green";
  if (isRobot && isBeta) return "purple";
  if (isHuman) return "yellow";
  if (isRobot) return "red";
  if (isBeta) return "blue";
  return "pink";
}

function buildFlagResponse(
  username,
  highlightEnabled,
  contextHighlight,
  showMoveCount,
  showOsEmoji,
  hostOs
) {
  const highlightColor = resolveHighlightColor(
    username,
    highlightEnabled,
    contextHighlight
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
  };
}

module.exports = {
  FLAG_HIGHLIGHT,
  FLAG_CONTEXT,
  FLAG_COUNT,
  resolveHighlightColor,
  formatCohortLabel,
  buildFlagResponse,
};
