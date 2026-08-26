/**
 * 33-synced-segments Vue SDK helpers.
 * LaunchDarkly: useLDFlag(show-inner-circle-badge) + identify + change:
 * https://launchdarkly.com/docs/home/flags/synced-segments
 * https://launchdarkly.com/docs/sdk/client-side/vue
 */

export const FLAG_BADGE = "show-inner-circle-badge";

export function formatChangeDetail(payload) {
  if (payload == null) return "";
  if (Array.isArray(payload)) return payload.join(", ");
  if (typeof payload === "object") return Object.keys(payload).join(", ");
  return String(payload);
}
