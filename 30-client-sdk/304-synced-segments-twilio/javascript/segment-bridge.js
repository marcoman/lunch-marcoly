/**
 * Browser bundle entry for Twilio Segment Analytics.js 2.0.
 * LaunchDarkly: membership is not written here — Segment identify/track feeds
 * an Engage Audience that syncs via LaunchDarkly Audiences.
 * https://github.com/segmentio/analytics-next
 * Keywords: Twilio Segment, Analytics.js, identify, track
 */
import { AnalyticsBrowser } from "@segment/analytics-next";

window.AnalyticsBrowser = AnalyticsBrowser;
