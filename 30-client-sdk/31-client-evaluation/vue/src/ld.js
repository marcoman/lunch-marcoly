/**
 * 31-client-evaluation Vue SDK helpers.
 * LaunchDarkly: useLDFlag (string + boolean), streaming change:
 * https://launchdarkly.com/docs/sdk/client-side/vue
 */

export const FLAG_HIGHLIGHT = "enable-client-grid-highlight";
export const FLAG_COUNT = "show-client-move-count";

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
