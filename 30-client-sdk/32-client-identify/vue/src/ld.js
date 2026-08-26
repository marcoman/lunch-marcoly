/**
 * 32-client-identify Vue SDK helpers.
 * LaunchDarkly: useLDFlag + identify() on the existing client
 * https://launchdarkly.com/docs/sdk/features/identify
 * https://launchdarkly.com/docs/sdk/client-side/vue
 */

export const FLAG_HIGHLIGHT = "enable-identify-grid-highlight";
export const FLAG_COUNT = "show-identify-move-count";

const COLORS = new Set(["green", "yellow", "red", "blue", "purple"]);

export function interpretHighlight(raw) {
  if (typeof raw === "string" && COLORS.has(raw.trim().toLowerCase())) {
    return raw.trim().toLowerCase();
  }
  return "none";
}
