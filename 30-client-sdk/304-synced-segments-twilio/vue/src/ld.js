/**
 * 34-synced-segments-twilio Vue SDK helpers.
 * LaunchDarkly: useLDFlag(show-twilio-inner-circle-badge) + identify + change:
 * https://launchdarkly.com/docs/home/flags/synced-segments
 * https://launchdarkly.com/docs/sdk/client-side/vue
 */

// LaunchDarkly: flag key=show-twilio-inner-circle-badge
// https://app.launchdarkly.com/projects/lunch-marcoly/features/show-twilio-inner-circle-badge

export const FLAG_BADGE = "show-twilio-inner-circle-badge";

export function formatChangeDetail(payload) {
  if (payload == null) return "";
  if (Array.isArray(payload)) return payload.join(", ");
  if (typeof payload === "object") return Object.keys(payload).join(", ");
  return String(payload);
}
