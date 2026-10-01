/**
 * 36-client-track-events Vue SDK helpers.
 * LaunchDarkly: useLDFlag (string + boolean), streaming change:
 * https://launchdarkly.com/docs/sdk/client-side/vue
 */

// LaunchDarkly: flag key=enable-client-track-highlight
// https://app.launchdarkly.com/projects/lunch-marcoly/features/enable-client-track-highlight

export const FLAG_HIGHLIGHT = "enable-client-track-highlight";
// LaunchDarkly: flag key=show-client-track-move-count
// https://app.launchdarkly.com/projects/lunch-marcoly/features/show-client-track-move-count

export const FLAG_COUNT = "show-client-track-move-count";

const COLORS = new Set(["green", "yellow", "red", "blue", "purple"]);

export function interpretHighlight(raw) {
  if (typeof raw === "string" && COLORS.has(raw.trim().toLowerCase())) {
    return raw.trim().toLowerCase();
  }
  return "none";
}

export function formatChangeDetail(payload) {
  if (payload == null) return "";
  if (Array.isArray(payload)) return payload.join(", ");
  if (typeof payload === "object") return Object.keys(payload).join(", ");
  return String(payload);
}
