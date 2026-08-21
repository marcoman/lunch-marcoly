/** Team-label targeting helpers for 13-flag-targeting-rules.
 *
 * LaunchDarkly targeting rules inspect the public `team` context attribute.
 * https://launchdarkly.com/docs/home/flags/target-rules
 */

const FLAG_TEAM_LABEL_STYLE = "configure-team-label-style";
const PLAIN = "plain";
const TEAM_LABELS = {
  "": "No team",
  red: "Team Red",
  blue: "Team Blue",
  yellow: "Team Yellow",
};
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

/** Evaluate the string variation with detail so the UI can trace its reason. */
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

  return {
    team: normalizedTeam,
    teamLabel: TEAM_LABELS[normalizedTeam],
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
  };
}

module.exports = {
  FLAG_TEAM_LABEL_STYLE,
  normalizeTeam,
  buildContext,
  evaluateTeamStyle,
};
