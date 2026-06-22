/** Build LaunchDarkly user contexts for segment-by-name targeting. */

// LaunchDarkly capability: Context attributes for segment rules
// See: https://launchdarkly.com/docs/home/observability/context-kinds

const FLAG_HIGHLIGHT = "configure-grid-selection-green-highlight";

const COLOR_NAMES = new Set(["yellow", "red", "blue", "green", "purple"]);

const SEGMENT_GENERIC = "generic";
const SEGMENT_NAMED_COLOR = "named-color";
const SEGMENT_HUMAN = "human";
const SEGMENT_ROBOT = "robot";
const SEGMENT_HUMAN_BETA = "human-beta";
const SEGMENT_ROBOT_BETA = "robot-beta";

const ALLOWED_SEGMENT_TYPES = new Set([
  SEGMENT_GENERIC,
  SEGMENT_NAMED_COLOR,
  SEGMENT_HUMAN,
  SEGMENT_ROBOT,
  SEGMENT_HUMAN_BETA,
  SEGMENT_ROBOT_BETA,
]);

function letterCount(username) {
  return [...username].filter((ch) => /[a-zA-Z]/.test(ch)).length;
}

function resolveSegmentInfo(username) {
  const lower = username.toLowerCase();

  if (lower === "generic") {
    return { segmentType: SEGMENT_GENERIC, namedColor: null };
  }

  if (COLOR_NAMES.has(lower)) {
    return { segmentType: SEGMENT_NAMED_COLOR, namedColor: lower };
  }

  const isHuman = letterCount(username) % 2 === 0;
  const isBeta = lower.includes("beta");

  if (isHuman && isBeta) {
    return { segmentType: SEGMENT_HUMAN_BETA, namedColor: null };
  }
  if (isHuman) {
    return { segmentType: SEGMENT_HUMAN, namedColor: null };
  }
  if (isBeta) {
    return { segmentType: SEGMENT_ROBOT_BETA, namedColor: null };
  }
  return { segmentType: SEGMENT_ROBOT, namedColor: null };
}

function buildSegmentContext(username) {
  const info = resolveSegmentInfo(username);
  const context = {
    kind: "user",
    key: username,
    segmentType: info.segmentType,
  };

  if (info.segmentType === SEGMENT_GENERIC) {
    context.generic = true;
  } else if (info.segmentType === SEGMENT_NAMED_COLOR && info.namedColor) {
    context.namedColor = info.namedColor;
  } else {
    const userKind = info.segmentType.startsWith("human") ? "human" : "robot";
    context.userKind = userKind;
    context.beta = info.segmentType.endsWith("beta");
  }

  return { context, info };
}

module.exports = {
  FLAG_HIGHLIGHT,
  COLOR_NAMES,
  SEGMENT_GENERIC,
  SEGMENT_NAMED_COLOR,
  SEGMENT_HUMAN,
  SEGMENT_ROBOT,
  SEGMENT_HUMAN_BETA,
  SEGMENT_ROBOT_BETA,
  ALLOWED_SEGMENT_TYPES,
  letterCount,
  resolveSegmentInfo,
  buildSegmentContext,
};
