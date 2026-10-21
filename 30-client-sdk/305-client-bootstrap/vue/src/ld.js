/**
 * 35-client-bootstrap Vue SDK helpers.
 * LaunchDarkly: useLDFlag (string + boolean), streaming change:
 * https://launchdarkly.com/docs/sdk/client-side/vue
 */

// LaunchDarkly: flag key=enable-client-bootstrap-highlight
// https://app.launchdarkly.com/projects/lunch-marcoly/features/enable-client-bootstrap-highlight

export const FLAG_HIGHLIGHT = "enable-client-bootstrap-highlight";
// LaunchDarkly: flag key=show-client-bootstrap-move-count
// https://app.launchdarkly.com/projects/lunch-marcoly/features/show-client-bootstrap-move-count

export const FLAG_COUNT = "show-client-bootstrap-move-count";

/**
 * First-paint values. The grid uses these until the client is ready.
 * LaunchDarkly: bootstrap
 * https://launchdarkly.com/docs/sdk/features/bootstrapping#javascript
 */
export const BOOTSTRAP = {
  [FLAG_HIGHLIGHT]: "green",
  [FLAG_COUNT]: true,
};

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
