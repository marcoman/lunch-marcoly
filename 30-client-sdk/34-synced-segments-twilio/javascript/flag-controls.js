/**
 * Lab proxy — flag on/off only. Inner-circle membership is Twilio Segment
 * Analytics.js in the page (identify + track), not LaunchDarkly REST.
 *
 * https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
 * https://launchdarkly.com/docs/home/flags/twilio
 * Keywords: synced segments, Twilio Segment Audiences, segmentMatch
 */

const FLAG_BADGE = "show-twilio-inner-circle-badge";
const DEFAULT_SEGMENT_KEY = "marcoly-twilio-inner-circle";

function segmentKey() {
  return (process.env.LD_TWILIO_SEGMENT_KEY || DEFAULT_SEGMENT_KEY).trim();
}

function apiConfig() {
  const token = (process.env.LD_API_ACCESS_TOKEN || "").trim();
  const project = (process.env.LD_PROJECT_KEY || "").trim();
  const environment = (process.env.LD_ENVIRONMENT_KEY || "").trim();
  const missing = [];
  if (!token) missing.push("LD_API_ACCESS_TOKEN");
  if (!project) missing.push("LD_PROJECT_KEY");
  if (!environment) missing.push("LD_ENVIRONMENT_KEY");
  return {
    configured: missing.length === 0,
    missing,
    projectKey: project || null,
    environmentKey: environment || null,
    apiHost: process.env.LD_API_HOST || "https://app.launchdarkly.com",
    segmentKey: segmentKey(),
    flagKey: FLAG_BADGE,
    segmentWriteKeyConfigured: Boolean((process.env.SEGMENT_WRITE_KEY || "").trim()),
  };
}

function ldRequest(method, path, body, { semantic = false } = {}) {
  const cfg = apiConfig();
  if (!cfg.configured) {
    const err = new Error("Lab controls need " + cfg.missing.join(", ") + " in the server environment.");
    err.status = 503;
    throw err;
  }
  const token = (process.env.LD_API_ACCESS_TOKEN || "").trim();
  const version = process.env.LD_API_VERSION || "20240415";
  const url = `${cfg.apiHost.replace(/\/$/, "")}/api/v2${path}`;
  const headers = {
    Authorization: token,
    "LD-API-Version": version,
    Accept: "application/json",
  };
  const opts = { method, headers };
  if (body !== undefined) {
    headers["Content-Type"] = semantic
      ? "application/json; domain-model=launchdarkly.semanticpatch"
      : "application/json";
    opts.body = JSON.stringify(body);
  }
  return fetch(url, opts).then(async (res) => {
    const text = await res.text();
    let parsed = {};
    if (text) {
      try {
        parsed = JSON.parse(text);
      } catch (_err) {
        parsed = { raw: text };
      }
    }
    if (!res.ok) {
      const err = new Error(parsed.message || text || `LaunchDarkly API ${res.status}`);
      err.status = res.status;
      throw err;
    }
    return parsed;
  });
}

async function listFlagControls() {
  const cfg = apiConfig();
  const key = cfg.segmentKey;
  if (!cfg.configured) {
    return {
      ...cfg,
      flags: [
        {
          key: FLAG_BADGE,
          label: "Inner-circle badge (Twilio)",
          summary: `Boolean: true when the context is in ${key}. Leave ON.`,
          on: null,
          targetingHint: "Set missing env vars to enable controls.",
        },
      ],
      segment: { key, found: false },
    };
  }
  const query = new URLSearchParams({ env: cfg.environmentKey }).toString();
  let flagSummary;
  try {
    const flag = await ldRequest("GET", `/flags/${cfg.projectKey}/${FLAG_BADGE}?${query}`);
    const env = (flag.environments || {})[cfg.environmentKey] || {};
    flagSummary = {
      key: FLAG_BADGE,
      label: "Inner-circle badge (Twilio)",
      summary: `Boolean: true when the context is in ${key}. Leave ON for the demo.`,
      on: env.on === true,
      variationKind: "boolean",
      targetingHint: env.on
        ? "Flag is ON — Twilio-synced members of the segment see the badge."
        : "Flag is OFF — badge hidden for everyone.",
    };
  } catch (exc) {
    flagSummary = {
      key: FLAG_BADGE,
      label: "Inner-circle badge (Twilio)",
      on: null,
      targetingHint: String(exc.message || exc),
      error: String(exc.message || exc),
    };
  }

  let segment = { key, found: false };
  try {
    const seg = await ldRequest(
      "GET",
      `/segments/${cfg.projectKey}/${cfg.environmentKey}/${key}`
    );
    segment = {
      key,
      found: true,
      name: seg.name || key,
      unbounded: Boolean(seg.unbounded),
    };
  } catch (exc) {
    segment = {
      key,
      found: false,
      error: String(exc.message || exc),
      hint:
        "Twilio creates this segment on first LaunchDarkly Audiences sync. Copy the key from the Segments page into LD_TWILIO_SEGMENT_KEY.",
    };
  }

  return { ...cfg, flags: [flagSummary], segment };
}

async function applyFlagControl(flagKey, { on } = {}) {
  if (flagKey !== FLAG_BADGE) {
    const err = new Error(`Flag key not allowed: ${flagKey}`);
    err.status = 400;
    throw err;
  }
  if (on === undefined) {
    const err = new Error('Provide "on"');
    err.status = 400;
    throw err;
  }
  const cfg = apiConfig();
  await ldRequest(
    "PATCH",
    `/flags/${cfg.projectKey}/${FLAG_BADGE}`,
    {
      environmentKey: cfg.environmentKey,
      comment: "34-synced-segments-twilio UI",
      instructions: [{ kind: on ? "turnFlagOn" : "turnFlagOff" }],
    },
    { semantic: true }
  );
  return listFlagControls();
}

module.exports = {
  FLAG_BADGE,
  DEFAULT_SEGMENT_KEY,
  segmentKey,
  apiConfig,
  listFlagControls,
  applyFlagControl,
};
