/** Flag variation keys, defaults, and response building for 11-flag-variations. */

const {
  FLAG_ANON_OS_EMOJI,
  buildAnonymousContext,
  buildUserContext,
  detectHostOs,
  osEmojiFor,
} = require("./host-os");

// LaunchDarkly capability: Multivariate flag evaluation (string, number, JSON)
// See: https://launchdarkly.com/docs/sdk/features/flag-types

const FLAG_COUNT_LABEL = "configure-navigation-count-label";
const FLAG_LUCKY_NUMBER = "configure-lucky-number";
const FLAG_MAX_MOVES = "configure-max-navigation-moves";

const DEFAULT_COUNT_LABEL = "Count";
const DEFAULT_LUCKY_NUMBER = 0;
const DEFAULT_MAX_MOVES = 100;

function parseMaxMoves(raw) {
  if (raw && typeof raw === "object" && "maxMoves" in raw) {
    return Number(raw.maxMoves) || DEFAULT_MAX_MOVES;
  }
  if (typeof raw === "string") {
    try {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object" && "maxMoves" in parsed) {
        return Number(parsed.maxMoves) || DEFAULT_MAX_MOVES;
      }
    } catch (_) {
      /* keep default */
    }
  }
  return DEFAULT_MAX_MOVES;
}

function buildFlagResponse(countLabel, luckyNumber, maxMoves, osEmoji) {
  return {
    countLabel: countLabel || DEFAULT_COUNT_LABEL,
    luckyNumber: Number(luckyNumber),
    maxMoves,
    osEmoji: osEmoji || "",
  };
}

async function evaluateFlags(client, username, hostOs) {
  const host = hostOs || detectHostOs();
  if (!client) {
    return buildFlagResponse(
      DEFAULT_COUNT_LABEL,
      DEFAULT_LUCKY_NUMBER,
      DEFAULT_MAX_MOVES,
      ""
    );
  }

  const anonContext = buildAnonymousContext(host);
  const userContext = buildUserContext(username);

  const showEmoji = await client.variation(FLAG_ANON_OS_EMOJI, anonContext, false);
  const countLabel = await client.variation(
    FLAG_COUNT_LABEL,
    userContext,
    DEFAULT_COUNT_LABEL
  );
  const luckyNumber = await client.variation(
    FLAG_LUCKY_NUMBER,
    userContext,
    DEFAULT_LUCKY_NUMBER
  );
  const maxMovesRaw = await client.variation(FLAG_MAX_MOVES, userContext, {
    maxMoves: DEFAULT_MAX_MOVES,
  });

  return buildFlagResponse(
    String(countLabel),
    luckyNumber,
    parseMaxMoves(maxMovesRaw),
    osEmojiFor(host, Boolean(showEmoji))
  );
}

module.exports = {
  FLAG_COUNT_LABEL,
  FLAG_LUCKY_NUMBER,
  FLAG_MAX_MOVES,
  DEFAULT_COUNT_LABEL,
  DEFAULT_LUCKY_NUMBER,
  DEFAULT_MAX_MOVES,
  parseMaxMoves,
  buildFlagResponse,
  evaluateFlags,
};
