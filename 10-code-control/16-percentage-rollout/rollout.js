/** LaunchDarkly evaluation helpers for the static percentage-rollout lesson.
 *
 * LaunchDarkly percentage rollout:
 * https://launchdarkly.com/docs/home/flags/rollouts
 * Keywords: percentage rollout, context key, sticky bucketing, variation detail
 */

const FLAG_KEY = "enable-grid-selection-highlight-pct";
const DEFAULT_VALUE = "none";

function normalizeUsername(value) {
  const username = String(value || "").trim();
  if (!username) throw new Error("Username is required.");
  return username;
}

function reasonPayload(reason) {
  if (!reason) return { kind: "UNKNOWN" };
  if (typeof reason === "object") {
    const payload = { kind: reason.kind || "UNKNOWN" };
    if (reason.ruleIndex != null) payload.ruleIndex = reason.ruleIndex;
    if (reason.ruleId != null) payload.ruleId = reason.ruleId;
    if (reason.errorKind != null) payload.errorKind = reason.errorKind;
    return payload;
  }
  return { kind: String(reason) };
}

function offlineResult(username) {
  return {
    flagKey: FLAG_KEY,
    flagValue: DEFAULT_VALUE,
    highlightColor: DEFAULT_VALUE,
    variationIndex: null,
    reason: { kind: "ERROR", errorKind: "CLIENT_NOT_READY" },
    ldContext: { kind: "user", key: username, name: username },
    stickyNote: "Safe SDK default; LaunchDarkly client is not ready.",
  };
}

/** Evaluate the static rollout without implementing bucketing in app code. */
async function evaluateRollout(client, rawUsername) {
  const username = normalizeUsername(rawUsername);
  const context = { kind: "user", key: username, name: username };

  if (!client) {
    return offlineResult(username);
  }

  const detail = await client.variationDetail(FLAG_KEY, context, DEFAULT_VALUE);
  const raw = detail && detail.value;
  const value = raw === "none" || raw === "green" ? raw : DEFAULT_VALUE;
  const variationIndex =
    detail && Number.isInteger(detail.variationIndex) ? detail.variationIndex : null;
  return {
    flagKey: FLAG_KEY,
    flagValue: value,
    highlightColor: value,
    variationIndex,
    reason: reasonPayload(detail && detail.reason),
    ldContext: { kind: "user", key: username, name: username },
    stickyNote:
      "LaunchDarkly buckets this user context key deterministically. " +
      "The same key keeps the same assignment while weights stay unchanged.",
  };
}

module.exports = {
  FLAG_KEY,
  DEFAULT_VALUE,
  normalizeUsername,
  evaluateRollout,
};
