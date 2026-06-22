/** Map segment types and flag variations to UI highlight styling. */

const {
  FLAG_HIGHLIGHT,
  SEGMENT_GENERIC,
  SEGMENT_HUMAN,
  SEGMENT_HUMAN_BETA,
  SEGMENT_NAMED_COLOR,
  SEGMENT_ROBOT,
  SEGMENT_ROBOT_BETA,
  buildSegmentContext,
} = require("./segment-context");

// LaunchDarkly capability: String flag variation from segment targeting
// See: https://launchdarkly.com/docs/home/flags/segments

const VALID_COLORS = new Set(["yellow", "red", "blue", "green", "purple"]);

function colorLabelName(highlightColor) {
  return highlightColor === "none" ? "no-color" : highlightColor;
}

function formatSegmentLabel(info, highlightColor) {
  const colorName = colorLabelName(highlightColor);
  if (info.segmentType === SEGMENT_GENERIC) {
    return "(generic)";
  }
  if (info.segmentType === SEGMENT_NAMED_COLOR) {
    return `(${colorName})`;
  }
  if (info.segmentType === SEGMENT_HUMAN || info.segmentType === SEGMENT_ROBOT) {
    return `(${info.segmentType}-${colorName})`;
  }
  if (info.segmentType === SEGMENT_HUMAN_BETA || info.segmentType === SEGMENT_ROBOT_BETA) {
    return `(${info.segmentType}-${colorName})`;
  }
  return `(${colorName})`;
}

const SEGMENT_HIGHLIGHT_COLORS = {
  [SEGMENT_HUMAN]: "yellow",
  [SEGMENT_ROBOT]: "red",
  [SEGMENT_HUMAN_BETA]: "green",
  [SEGMENT_ROBOT_BETA]: "purple",
};

function expectedColorForSegment(info) {
  if (info.segmentType === SEGMENT_GENERIC) {
    return "none";
  }
  if (info.segmentType === SEGMENT_NAMED_COLOR && info.namedColor) {
    return info.namedColor;
  }
  return SEGMENT_HIGHLIGHT_COLORS[info.segmentType] || "none";
}

function normalizeHighlightColor(raw) {
  const color = String(raw || "none")
    .trim()
    .toLowerCase();
  return VALID_COLORS.has(color) ? color : "none";
}

function resolveVariationColor(raw, info) {
  const color = normalizeHighlightColor(raw);
  if (color !== "none") {
    return color;
  }
  if (raw === true) {
    return expectedColorForSegment(info);
  }
  return "none";
}

function buildFlagResponse(username, highlightColor, info) {
  const color = normalizeHighlightColor(highlightColor);
  return {
    highlightColor: color,
    segmentLabel: formatSegmentLabel(info, color),
    segmentType: info.segmentType,
  };
}

async function evaluateHighlight(client, username) {
  const { context, info } = buildSegmentContext(username);
  if (!client) {
    return buildFlagResponse(username, "none", info);
  }
  const raw = await client.variation(FLAG_HIGHLIGHT, context, "none");
  const color = resolveVariationColor(raw, info);
  return buildFlagResponse(username, color, info);
}

module.exports = {
  FLAG_HIGHLIGHT,
  VALID_COLORS,
  colorLabelName,
  formatSegmentLabel,
  normalizeHighlightColor,
  buildFlagResponse,
  evaluateHighlight,
};
