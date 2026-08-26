/**
 * Lab proxy — flag on/off + inner-circle membership.
 * Writer token stays on the Node host.
 *
 * https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
 * https://launchdarkly.com/docs/api/segments/update-big-segment-targets
 * Keywords: synced segments, big segments, addIncludedTargets
 */

const FLAG_BADGE = "show-inner-circle-badge";
const SEGMENT_KEY = "marcoly-inner-circle";

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
    segmentKey: SEGMENT_KEY,
    flagKey: FLAG_BADGE,
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
  if (!cfg.configured) {
    return {
      ...cfg,
      flags: [
        {
          key: FLAG_BADGE,
          label: "Inner-circle badge",
          summary: "Boolean: true when the context is in marcoly-inner-circle. Leave ON.",
          on: null,
          targetingHint: "Set missing env vars to enable controls.",
        },
      ],
      segment: { key: SEGMENT_KEY, found: false },
    };
  }
  const query = new URLSearchParams({ env: cfg.environmentKey }).toString();
  let flagSummary;
  try {
    const flag = await ldRequest("GET", `/flags/${cfg.projectKey}/${FLAG_BADGE}?${query}`);
    const env = (flag.environments || {})[cfg.environmentKey] || {};
    flagSummary = {
      key: FLAG_BADGE,
      label: "Inner-circle badge",
      summary:
        "Boolean: true when the context is in marcoly-inner-circle. Leave ON for the demo.",
      on: env.on === true,
      variationKind: "boolean",
      targetingHint: env.on
        ? "Flag is ON — members of the segment see the badge."
        : "Flag is OFF — badge hidden for everyone.",
    };
  } catch (exc) {
    flagSummary = {
      key: FLAG_BADGE,
      label: "Inner-circle badge",
      on: null,
      targetingHint: String(exc.message || exc),
      error: String(exc.message || exc),
    };
  }

  let segment = { key: SEGMENT_KEY, found: false };
  try {
    const seg = await ldRequest(
      "GET",
      `/segments/${cfg.projectKey}/${cfg.environmentKey}/${SEGMENT_KEY}`
    );
    segment = {
      key: SEGMENT_KEY,
      found: true,
      name: seg.name || SEGMENT_KEY,
      unbounded: Boolean(seg.unbounded),
    };
  } catch (exc) {
    segment = {
      key: SEGMENT_KEY,
      found: false,
      error: String(exc.message || exc),
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
      comment: "33-synced-segments UI",
      instructions: [{ kind: on ? "turnFlagOn" : "turnFlagOff" }],
    },
    { semantic: true }
  );
  return listFlagControls();
}

async function applyMembership(contextKey, action) {
  const key = String(contextKey || "").trim();
  if (!key) {
    const err = new Error("contextKey is required");
    err.status = 400;
    throw err;
  }
  if (action !== "add" && action !== "remove") {
    const err = new Error('action must be "add" or "remove"');
    err.status = 400;
    throw err;
  }
  const cfg = apiConfig();
  const base = `/segments/${cfg.projectKey}/${cfg.environmentKey}/${SEGMENT_KEY}`;
  const included =
    action === "add" ? { included: { add: [key] } } : { included: { remove: [key] } };
  try {
    await ldRequest("POST", `${base}/users`, included);
    return { ok: true, mode: "big-segment-users", action, contextKey: key, segmentKey: SEGMENT_KEY };
  } catch (exc) {
    const instruction =
      action === "add"
        ? { kind: "addIncludedTargets", contextKind: "user", values: [key] }
        : { kind: "removeIncludedTargets", contextKind: "user", values: [key] };
    await ldRequest(
      "PATCH",
      base,
      { comment: "33-synced-segments UI membership", instructions: [instruction] },
      { semantic: true }
    );
    return {
      ok: true,
      mode: "list-included-targets",
      action,
      contextKey: key,
      segmentKey: SEGMENT_KEY,
      note: String(exc.message || ""),
    };
  }
}

export {
  FLAG_BADGE,
  SEGMENT_KEY,
  apiConfig,
  listFlagControls,
  applyFlagControl,
  applyMembership,
};
