/** Resolve grid selection highlight color and cohort label from username context. */

const FLAG_HIGHLIGHT = "configure-grid-selection-green-highlight";
const FLAG_CONTEXT = "configure-grid-selection-context-highlight";
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

function buildFlagResponse(username, highlightEnabled, contextHighlight, showMoveCount) {
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
  };
}

module.exports = {
  FLAG_HIGHLIGHT,
  FLAG_CONTEXT,
  FLAG_COUNT,
  resolveHighlightColor,
  buildFlagResponse,
};
