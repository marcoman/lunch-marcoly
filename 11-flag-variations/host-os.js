/** Host OS detection and anonymous-context evaluation for flag variations. */

// LaunchDarkly capability: Anonymous contexts + private attributes
// See: https://launchdarkly.com/docs/sdk/features/anonymous
// See: https://launchdarkly.com/docs/sdk/features/private-attributes

const HOST_OS_ATTR = "hostOs";
const ANONYMOUS_CONTEXT_KEY = "anonymous";
const FLAG_ANON_OS_EMOJI = "show-anonymous-host-os-emoji";

const OS_EMOJI = {
  linux: "🐧",
  macos: "🍎",
  windows: "🪟",
  other: "😊",
};

function detectHostOs() {
  const platform = process.platform;
  if (platform === "linux") return "linux";
  if (platform === "win32") return "windows";
  if (platform === "darwin") return "macos";
  return "other";
}

function osEmojiFor(hostOs, showOsEmoji) {
  if (!showOsEmoji) return "";
  return OS_EMOJI[hostOs] || OS_EMOJI.other;
}

function buildAnonymousContext(hostOs) {
  return {
    kind: "user",
    key: ANONYMOUS_CONTEXT_KEY,
    anonymous: true,
    hostOs,
    privateAttributes: [HOST_OS_ATTR],
  };
}

function buildUserContext(username) {
  return { kind: "user", key: username };
}

module.exports = {
  HOST_OS_ATTR,
  ANONYMOUS_CONTEXT_KEY,
  FLAG_ANON_OS_EMOJI,
  detectHostOs,
  osEmojiFor,
  buildAnonymousContext,
  buildUserContext,
};
