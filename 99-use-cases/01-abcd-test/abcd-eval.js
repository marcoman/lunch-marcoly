/** LaunchDarkly evaluation for the ABCD navigation count label test. */

const LaunchDarkly = require("@launchdarkly/node-server-sdk");

// LaunchDarkly capability: String flag evaluation for multivariate A/B/C/D test
// See: https://launchdarkly.com/docs/sdk/features/flag-types

const FLAG_COUNT_LABEL = "configure-navigation-count-label";
const DEFAULT_COUNT_LABEL = "Count";

const VARIATION_VALUES = [
  "Count",
  "Move Count",
  "Moves",
  "Navigation Counts",
];

let ldClient = null;

async function initClient() {
  if (ldClient) {
    return ldClient;
  }
  const sdkKey = process.env.LD_SDK_KEY;
  if (!sdkKey) {
    return null;
  }
  ldClient = LaunchDarkly.init(sdkKey);
  try {
    await ldClient.waitForInitialization({ timeout: 5 });
  } catch (_) {
    ldClient = null;
  }
  return ldClient;
}

async function closeClient() {
  if (ldClient) {
    await ldClient.close();
    ldClient = null;
  }
}

async function evaluateCountLabel(username) {
  const client = await initClient();
  if (!client) {
    return DEFAULT_COUNT_LABEL;
  }
  const context = { kind: "user", key: username };
  const label = await client.variation(FLAG_COUNT_LABEL, context, DEFAULT_COUNT_LABEL);
  return String(label || DEFAULT_COUNT_LABEL);
}

module.exports = {
  FLAG_COUNT_LABEL,
  DEFAULT_COUNT_LABEL,
  VARIATION_VALUES,
  initClient,
  closeClient,
  evaluateCountLabel,
};
