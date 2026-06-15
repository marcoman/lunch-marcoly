/** Host OS detection and emoji mapping for private-attribute flag evaluation. */

const os = require("os");

// LaunchDarkly capability: Private context attributes (server-side SDK)
// See: https://launchdarkly.com/docs/sdk/features/private-attributes

const HOST_OS_ATTR = "hostOs";
const FLAG_OS_EMOJI = "show-host-os-emoji";

const OS_EMOJI = {
  linux: "🐧",
  macos: "🍎",
  windows: "🪟",
  other: "😊",
};

function detectHostOs() {
  switch (os.platform()) {
    case "linux":
      return "linux";
    case "win32":
      return "windows";
    case "darwin":
      return "macos";
    default:
      return "other";
  }
}

function osEmojiFor(hostOs, showOsEmoji) {
  if (!showOsEmoji) return "";
  return OS_EMOJI[hostOs] || OS_EMOJI.other;
}

module.exports = {
  HOST_OS_ATTR,
  FLAG_OS_EMOJI,
  OS_EMOJI,
  detectHostOs,
  osEmojiFor,
};
