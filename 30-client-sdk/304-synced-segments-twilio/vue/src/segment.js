/**
 * Twilio Segment Analytics.js — join/leave inner circle from the page.
 * https://github.com/segmentio/analytics-next
 * https://launchdarkly.com/docs/home/flags/twilio
 * Keywords: identify, track, Engage Audiences, synced segments
 */
import { AnalyticsBrowser } from "@segment/analytics-next";

export const SEGMENT_TRACK_JOIN = "Joined Inner Circle";
export const SEGMENT_TRACK_LEAVE = "Left Inner Circle";

let client = null;

export function loadSegment(writeKey) {
  const key = (writeKey || "").trim();
  if (!key) return null;
  if (!client) client = AnalyticsBrowser.load({ writeKey: key });
  return client;
}

export async function segmentIdentify(writeKey, userKey) {
  const analytics = loadSegment(writeKey);
  if (!analytics || !userKey) return;
  await analytics.identify(userKey);
}

export async function segmentJoinInnerCircle(writeKey, userKey) {
  const analytics = loadSegment(writeKey);
  if (!analytics) {
    throw new Error("SEGMENT_WRITE_KEY is unset on the host — cannot talk to Twilio Segment.");
  }
  await analytics.identify(userKey, { innerCircle: true });
  await analytics.track(SEGMENT_TRACK_JOIN, { innerCircle: true });
}

export async function segmentLeaveInnerCircle(writeKey, userKey) {
  const analytics = loadSegment(writeKey);
  if (!analytics) {
    throw new Error("SEGMENT_WRITE_KEY is unset on the host — cannot talk to Twilio Segment.");
  }
  await analytics.identify(userKey, { innerCircle: false });
  await analytics.track(SEGMENT_TRACK_LEAVE, { innerCircle: false });
}
