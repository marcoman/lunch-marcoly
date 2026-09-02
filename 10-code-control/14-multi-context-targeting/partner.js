/** Multi-context evaluation helpers for 14-multi-context-targeting.
 *
 * LaunchDarkly: one variation call with kind multi (user + organization).
 * https://launchdarkly.com/docs/home/flags/multi-contexts
 */

const FLAG_PARTNER_BADGE = "show-partner-org-badge";
const ORG_LABELS = { acme: "Acme", globex: "Globex" };

function normalizeUsername(username) {
  const value = String(username || "").trim().toLowerCase();
  if (!value) throw new Error("username is required");
  return value;
}

function normalizeOrg(org) {
  const value = String(org || "").trim().toLowerCase();
  if (!Object.prototype.hasOwnProperty.call(ORG_LABELS, value)) {
    throw new Error("org must be acme or globex");
  }
  return value;
}

/** Build user + organization multi-context. Do not put org on the user.
 * https://launchdarkly.com/docs/sdk/features/user-context
 */
function buildMultiContext(username, org) {
  const userKey = normalizeUsername(username);
  const orgKey = normalizeOrg(org);
  return {
    kind: "multi",
    user: { kind: "user", key: userKey },
    organization: { kind: "organization", key: orgKey, name: ORG_LABELS[orgKey] },
  };
}

function reasonPayload(reason) {
  if (!reason) return { kind: "UNKNOWN" };
  if (typeof reason === "object") return reason;
  return { kind: String(reason) };
}

/** Evaluate show-partner-org-badge. The SDK variation is the source of truth. */
async function evaluatePartner(client, username, org) {
  const userKey = normalizeUsername(username);
  const orgKey = normalizeOrg(org);
  const context = buildMultiContext(userKey, orgKey);
  const detail = client
    ? await client.variationDetail(FLAG_PARTNER_BADGE, context, false)
    : null;
  return {
    username: userKey,
    org: orgKey,
    orgLabel: ORG_LABELS[orgKey],
    partner: Boolean(detail ? detail.value : false),
    ldContext: {
      kind: "multi",
      user: { key: userKey },
      organization: { key: orgKey, name: ORG_LABELS[orgKey] },
      note: "Org is a separate context kind, not a user attribute.",
    },
    variationIndex: detail?.variationIndex ?? null,
    reason: detail ? reasonPayload(detail.reason) : { kind: "OFFLINE" },
  };
}

module.exports = {
  FLAG_PARTNER_BADGE,
  normalizeUsername,
  normalizeOrg,
  buildMultiContext,
  evaluatePartner,
};
