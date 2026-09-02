/** Evaluate the parent and dependent flags for 15-prerequisite-flags.
 *
 * LaunchDarkly: flag prerequisites and evaluation reasons.
 * https://launchdarkly.com/docs/home/flags/prereqs
 * Keywords: prerequisites, dependent flag, off variation
 */

const FLAG_HIGHLIGHT = "enable-grid-selection-highlight-prereq";
const FLAG_COUNT = "show-navigation-move-count-prereq";
const VALID_COLORS = new Set(["green", "yellow", "red", "blue", "purple", "pink"]);

function normalizeUsername(username) {
  const value = String(username || "").trim().toLowerCase();
  if (!value) throw new Error("username is required");
  return value;
}

function reasonPayload(reason) {
  if (!reason) return { kind: "UNKNOWN" };
  if (typeof reason === "object") {
    const payload = { kind: reason.kind || "UNKNOWN" };
    if (reason.ruleIndex != null) payload.ruleIndex = reason.ruleIndex;
    if (reason.ruleId != null) payload.ruleId = reason.ruleId;
    if (reason.prerequisiteKey != null) payload.prerequisiteKey = reason.prerequisiteKey;
    if (reason.errorKind != null) payload.errorKind = reason.errorKind;
    return payload;
  }
  return { kind: String(reason) };
}

function highlightColor(value) {
  if (typeof value !== "string") return "none";
  const candidate = value.trim().toLowerCase();
  return VALID_COLORS.has(candidate) ? candidate : "none";
}

/** Evaluate parent and child independently; LaunchDarkly enforces dependency. */
async function evaluatePrerequisiteFlags(client, username) {
  const userKey = normalizeUsername(username);
  const context = { kind: "user", key: userKey };
  let parentDetail = null;
  let childDetail = null;
  let parentValue = "none";
  let childValue = false;
  let parentReason = { kind: "OFFLINE" };
  let childReason = { kind: "OFFLINE" };

  if (client) {
    parentDetail = await client.variationDetail(FLAG_HIGHLIGHT, context, "none");
    childDetail = await client.variationDetail(FLAG_COUNT, context, false);
    parentValue = parentDetail.value;
    childValue = Boolean(childDetail.value);
    parentReason = reasonPayload(parentDetail.reason);
    childReason = reasonPayload(childDetail.reason);
  }

  const prerequisiteFailed = childReason.kind === "PREREQUISITE_FAILED";
  return {
    username: userKey,
    highlightColor: highlightColor(parentValue),
    showMoveCount: childValue,
    prerequisiteMet: Boolean(client) && parentValue === "green" && !prerequisiteFailed,
    ldContext: { kind: "user", key: userKey },
    parent: {
      key: FLAG_HIGHLIGHT,
      value: parentValue,
      variationIndex: parentDetail?.variationIndex ?? null,
      reason: parentReason,
    },
    child: {
      key: FLAG_COUNT,
      value: childValue,
      variationIndex: childDetail?.variationIndex ?? null,
      reason: childReason,
    },
  };
}

module.exports = {
  FLAG_HIGHLIGHT,
  FLAG_COUNT,
  VALID_COLORS,
  normalizeUsername,
  evaluatePrerequisiteFlags,
};
