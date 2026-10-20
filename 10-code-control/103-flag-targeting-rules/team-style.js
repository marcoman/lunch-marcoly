/** Team-label targeting helpers for 103-flag-targeting-rules.
 *
 * LaunchDarkly targeting rules inspect the public `team` context attribute.
 * https://launchdarkly.com/docs/home/flags/target-rules
 */

// LaunchDarkly: flag key=configure-team-label-style
// https://app.launchdarkly.com/projects/lunch-marcoly/features/configure-team-label-style

const FLAG_TEAM_LABEL_STYLE = "configure-team-label-style";
// JSON flag: words shown in the UI. Style values stay colored-red/blue/yellow/plain.
// https://launchdarkly.com/docs/sdk/features/flag-types
// LaunchDarkly: flag key=configure-team-display-labels
// https://app.launchdarkly.com/projects/lunch-marcoly/features/configure-team-display-labels

const FLAG_TEAM_DISPLAY_LABELS = "configure-team-display-labels";
const PLAIN = "plain";
const TEAM_LABELS = {
  "": "No team",
  red: "Team Red",
  blue: "Team Blue",
  yellow: "Team Yellow",
};
const LABEL_KEYS = ["none", "red", "blue", "yellow"];
const STYLE_COLORS = {
  plain: null,
  "colored-red": "red",
  "colored-blue": "blue",
  "colored-yellow": "yellow",
};

function normalizeTeam(team) {
  const value = String(team || "").trim().toLowerCase();
  if (!Object.prototype.hasOwnProperty.call(TEAM_LABELS, value)) {
    throw new Error("team must be empty, red, blue, or yellow");
  }
  return value;
}

/** Build a user context, omitting `team` entirely for No team.
 * The attribute stays public so rules and analytics can inspect it.
 * https://launchdarkly.com/docs/home/flags/context-attributes
 */
function buildContext(username, team) {
  const context = { kind: "user", key: username };
  if (team) context.team = team;
  return context;
}

function defaultDisplayLabels() {
  return {
    none: TEAM_LABELS[""],
    red: TEAM_LABELS.red,
    blue: TEAM_LABELS.blue,
    yellow: TEAM_LABELS.yellow,
  };
}

function displayLabelsFrom(value) {
  const labels = defaultDisplayLabels();
  if (!value || typeof value !== "object" || Array.isArray(value)) return labels;
  for (const key of LABEL_KEYS) {
    const text = value[key];
    if (typeof text === "string" && text.trim()) labels[key] = text.trim();
  }
  return labels;
}

/** Evaluate the style flag and the JSON display-label flag. */
async function evaluateTeamStyle(client, username, team) {
  const normalizedTeam = normalizeTeam(team);
  const context = buildContext(username, normalizedTeam);
  const detail = client
    ? await client.variationDetail(FLAG_TEAM_LABEL_STYLE, context, PLAIN)
    : null;
  const candidate = detail ? detail.value : PLAIN;
  const style = Object.prototype.hasOwnProperty.call(STYLE_COLORS, candidate)
    ? candidate
    : PLAIN;
  const attributes = normalizedTeam ? { team: normalizedTeam } : {};
  const labelDefault = defaultDisplayLabels();
  const labelDetail = client
    ? await client.variationDetail(FLAG_TEAM_DISPLAY_LABELS, context, labelDefault)
    : null;
  const labels = displayLabelsFrom(labelDetail ? labelDetail.value : labelDefault);

  return {
    team: normalizedTeam,
    teamLabel: labels[normalizedTeam || "none"],
    labels,
    style,
    colored: STYLE_COLORS[style] !== null,
    cssColor: STYLE_COLORS[style],
    ldContext: {
      kind: "user",
      key: username,
      attributes,
      teamAttribute: normalizedTeam || null,
      teamOmitted: !normalizedTeam,
      privateAttributes: [],
      note: "team is public; No team omits the attribute so rules skip to fallthrough.",
    },
    variationIndex: detail?.variationIndex ?? null,
    reason: detail?.reason ?? { kind: "OFFLINE" },
    labelEvaluation: {
      flagKey: FLAG_TEAM_DISPLAY_LABELS,
      value: labels,
      variationIndex: labelDetail?.variationIndex ?? null,
      reason: labelDetail?.reason ?? { kind: "OFFLINE" },
    },
  };
}

module.exports = {
  FLAG_TEAM_LABEL_STYLE,
  FLAG_TEAM_DISPLAY_LABELS,
  normalizeTeam,
  buildContext,
  evaluateTeamStyle,
};
