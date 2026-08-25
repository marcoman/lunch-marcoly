/**
 * Browser grid + LaunchDarkly JavaScript SDK.
 * Baseline navigation matches 02-reference-client-code.
 * Lesson: boolean flag targeted by a synced/big-style segment.
 */

const ROWS = ["t", "m", "b"];
const COLS = ["l", "m", "r"];

/** Feature flags — boolean variation from segment membership. */
const FLAG_BADGE = "show-inner-circle-badge";

let username = "";
let row = 1;
let col = 1;
let previous = null;
let moveCount = 0;
let showBadge = false;
let ldClient = null;
let clientSideId = null;
let identifyBusy = false;
let membershipBusy = false;
let sdkCallLog = [];
let initializeCount = 0;
let identifyCount = 0;
let changeCount = 0;

/**
 * Record SDK client lifecycle: initialize, identify, streaming change:.
 * Do not log variation() on WASD — that would bury the membership lesson.
 */
function logSdkCall(kind, detail) {
  const line = { t: new Date().toISOString().slice(11, 23), kind, detail };
  sdkCallLog.push(line);
  if (sdkCallLog.length > 40) sdkCallLog.shift();
  console.log(`[33 synced-segments] ${kind}${detail ? " " + detail : ""}`);
  const el = document.getElementById("sdk-call-log");
  if (!el) return;
  el.innerHTML = "";
  if (!sdkCallLog.length) {
    el.textContent = "No SDK client calls yet.";
    return;
  }
  for (const entry of sdkCallLog) {
    const row = document.createElement("div");
    row.className = "sdk-log-line kind-" + entry.kind;
    const kindLabel = entry.kind === "change" ? "change:" : entry.kind;
    row.textContent = `${entry.t}  ${kindLabel}${entry.detail ? "  " + entry.detail : ""}`;
    el.appendChild(row);
  }
  el.scrollTop = el.scrollHeight;
  const counts = document.getElementById("sdk-call-counts");
  if (counts) {
    counts.textContent =
      `initialize ×${initializeCount} · identify ×${identifyCount} · change ×${changeCount}`;
  }
}

function formatChangeDetail(payload) {
  if (payload == null) return "";
  if (Array.isArray(payload)) return payload.join(", ");
  if (typeof payload === "object") return Object.keys(payload).join(", ");
  return String(payload);
}

function formatPos(r, c) {
  return `${ROWS[r]}/${COLS[c]}`;
}

function tryMove(dr, dc) {
  const nr = Math.max(0, Math.min(2, row + dr));
  const nc = Math.max(0, Math.min(2, col + dc));
  if (nr === row && nc === col) return false;
  previous = { row, col };
  row = nr;
  col = nc;
  moveCount += 1;
  return true;
}

/**
 * Read the inner-circle badge flag from the client SDK.
 * LaunchDarkly: variation (boolean) — targeted by segment marcoly-inner-circle
 * https://launchdarkly.com/docs/sdk/features/evaluating-flags
 * https://launchdarkly.com/docs/home/flags/synced-segments
 */
function readFlagsFromClient() {
  if (!ldClient) {
    showBadge = false;
    return;
  }
  showBadge = Boolean(ldClient.variation(FLAG_BADGE, false));
}

function renderGrid() {
  document.getElementById("hdr-name").textContent = username;
  const badge = document.getElementById("inner-badge");
  if (badge) {
    badge.classList.toggle("hidden", !showBadge);
  }
  document.getElementById("hdr-current").textContent = formatPos(row, col);
  document.getElementById("hdr-previous").textContent =
    previous ? formatPos(previous.row, previous.col) : "—";
  document.getElementById("hdr-count").textContent = String(moveCount);
  document.body.classList.toggle("inner-circle-on", showBadge);

  const grid = document.getElementById("grid");
  grid.innerHTML = "";
  for (let r = 0; r < 3; r++) {
    for (let c = 0; c < 3; c++) {
      const selected = r === row && c === col;
      const cell = document.createElement("div");
      cell.className = "cell";
      if (selected) {
        cell.classList.add("selected");
        cell.textContent = "X";
      }
      grid.appendChild(cell);
    }
  }

  const ctx = document.getElementById("context-pre");
  if (ctx) {
    ctx.textContent = username
      ? JSON.stringify({ kind: "user", key: username }, null, 2)
      : "Log in to set the evaluation context.";
  }
  const switchInput = document.getElementById("switch-name");
  if (switchInput && document.activeElement !== switchInput) {
    switchInput.value = username;
  }
  const sdkMeta = document.getElementById("sdk-meta");
  if (sdkMeta) {
    sdkMeta.textContent = clientSideId
      ? `Client-side ID loaded (${clientSideId.slice(0, 6)}…). Badge=${showBadge ? "on" : "off"}.`
      : "No LD_CLIENT_SIDE_ID — using code default (badge off).";
  }
}

function closeLdClient() {
  if (ldClient) {
    logSdkCall("close", "client discarded (logout / re-init)");
    try {
      ldClient.close();
    } catch (_err) {
      /* ignore */
    }
    ldClient = null;
  }
}

/**
 * Initialize the JavaScript SDK after login.
 * LaunchDarkly: client-side ID, contexts, initialize, waitForInitialization
 * https://launchdarkly.com/docs/sdk/client-side/javascript
 */
async function startLdClient(name) {
  closeLdClient();
  if (!clientSideId || typeof LDClient === "undefined") {
    logSdkCall("skip", "no client-side ID — did not call initialize");
    readFlagsFromClient();
    return;
  }
  const context = { kind: "user", key: name };
  initializeCount += 1;
  logSdkCall("initialize", `key=${name}  (client #${initializeCount})`);
  ldClient = LDClient.initialize(clientSideId, context);
  /**
   * Streaming updates — badge follows membership without a page reload.
   * LaunchDarkly: change / change:flag-key events
   * https://launchdarkly.com/docs/sdk/features/flag-changes
   */
  ldClient.on("change", (payload) => {
    changeCount += 1;
    const keys = formatChangeDetail(payload);
    logSdkCall("change", keys ? `flags=${keys}` : "(stream update)");
    readFlagsFromClient();
    renderGrid();
  });
  try {
    await ldClient.waitForInitialization(5);
  } catch (_err) {
    /* defaults until flags arrive */
  }
  readFlagsFromClient();
}

/**
 * Switch context on the existing client. Does not re-initialize or reset the grid.
 * LaunchDarkly: identify (changing contexts)
 * https://launchdarkly.com/docs/sdk/features/identify
 */
async function identifyUser(name) {
  const next = (name || "").trim();
  if (!next || identifyBusy) return;
  if (!ldClient) {
    username = next;
    await startLdClient(next);
    renderGrid();
    return;
  }
  identifyBusy = true;
  try {
    identifyCount += 1;
    logSdkCall("identify", `key=${next}  (no initialize)`);
    await ldClient.identify({ kind: "user", key: next });
    username = next;
    readFlagsFromClient();
    renderGrid();
    document.getElementById("grid-screen").focus();
  } catch (_err) {
    readFlagsFromClient();
    renderGrid();
  } finally {
    identifyBusy = false;
  }
}

function logout() {
  closeLdClient();
  logSdkCall("session", "logged out — next login will initialize again (count kept)");
  username = "";
  row = 1;
  col = 1;
  previous = null;
  moveCount = 0;
  showBadge = false;
  document.getElementById("username").value = "";
  document.getElementById("login-error").classList.add("hidden");
  document.getElementById("app-shell").classList.add("hidden");
  document.body.classList.remove("grid-active", "inner-circle-on");
  document.getElementById("login-screen").classList.remove("hidden");
  document.getElementById("username").focus();
}

function quit() {
  closeLdClient();
  window.close();
  document.body.innerHTML = "<p>Application closed. You may close this tab.</p>";
}

async function startGrid(name) {
  username = name;
  row = 1;
  col = 1;
  previous = null;
  moveCount = 0;
  document.getElementById("login-screen").classList.add("hidden");
  document.getElementById("app-shell").classList.remove("hidden");
  document.body.classList.add("grid-active");
  await startLdClient(name);
  renderGrid();
  document.getElementById("grid-screen").focus();
}

function setMembershipMsg(text, isError) {
  const el = document.getElementById("membership-msg");
  if (!el) return;
  el.textContent = text || "";
  el.classList.toggle("hidden", !text);
  el.classList.toggle("error", Boolean(isError));
}

async function refreshControls() {
  const meta = document.getElementById("controls-meta");
  const warn = document.getElementById("controls-warn");
  const list = document.getElementById("controls-list");
  const segMeta = document.getElementById("segment-meta");
  try {
    const res = await fetch("/api/flag-controls", { cache: "no-store" });
    const data = await res.json();
    if (!data.configured) {
      warn.classList.remove("hidden");
      warn.textContent =
        "Controls need " + (data.missing || []).join(", ") + " on the Node host (not in the page).";
    } else {
      warn.classList.add("hidden");
    }
    meta.textContent = data.projectKey
      ? `Project ${data.projectKey} · env ${data.environmentKey}`
      : "REST controls unavailable.";
    if (segMeta) {
      const s = data.segment || {};
      if (s.found) {
        segMeta.textContent = `${s.key}${s.unbounded ? " (unbounded / big)" : " (list-based)"}`;
      } else {
        segMeta.textContent = s.error
          ? `Segment missing — ${s.error}`
          : `${s.key || "marcoly-inner-circle"} not found. Run rest/create-flags.sh.`;
      }
    }
    list.innerHTML = "";
    for (const f of data.flags || []) {
      const card = document.createElement("div");
      card.className = "flag-card";
      const onLabel = f.on === true ? "On" : f.on === false ? "Off" : "?";
      card.innerHTML = `<div class="flag-card-top">
          <div>
            <h3>${f.label}</h3>
            <div class="flag-key">${f.key}</div>
            <p class="flag-summary">${f.summary || ""}</p>
            <p class="flag-hint">${f.targetingHint || ""}</p>
          </div>
          <button type="button" class="flag-toggle ${f.on ? "on" : "off"}" data-key="${f.key}" data-on="${f.on ? "1" : "0"}">${onLabel}</button>
        </div>`;
      list.appendChild(card);
    }
    list.querySelectorAll(".flag-toggle").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const key = btn.getAttribute("data-key");
        const currentlyOn = btn.getAttribute("data-on") === "1";
        await postControl(key, { on: !currentlyOn });
      });
    });
  } catch (err) {
    warn.classList.remove("hidden");
    warn.textContent = String(err.message || err);
  }
}

async function postControl(key, body) {
  const res = await fetch("/api/flag-controls", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key, ...body }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || res.statusText);
  await refreshControls();
}

/**
 * Add or remove the current context key on marcoly-inner-circle.
 * Token stays on the Node host. Expect a streaming change: when targeting updates.
 */
async function postMembership(action) {
  if (!username || membershipBusy) return;
  membershipBusy = true;
  setMembershipMsg(`${action === "add" ? "Adding" : "Removing"} ${username}…`);
  try {
    const res = await fetch("/api/segment-membership", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ contextKey: username, action }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || res.statusText);
    setMembershipMsg(`${action === "add" ? "Added" : "Removed"} ${username} (${data.mode || "ok"}). Wait for change:.`);
    await refreshControls();
    window.setTimeout(() => {
      readFlagsFromClient();
      renderGrid();
    }, 400);
  } catch (err) {
    setMembershipMsg(String(err.message || err), true);
  } finally {
    membershipBusy = false;
  }
}

document.getElementById("login-btn").addEventListener("click", () => {
  const name = document.getElementById("username").value.trim();
  const err = document.getElementById("login-error");
  if (!name) {
    err.classList.remove("hidden");
    return;
  }
  err.classList.add("hidden");
  startGrid(name);
});

document.getElementById("username").addEventListener("keydown", (e) => {
  if (e.key === "Enter") document.getElementById("login-btn").click();
});

document.getElementById("grid-screen").addEventListener("keydown", (e) => {
  const key = e.key.toLowerCase();
  if (key === "q") {
    e.preventDefault();
    quit();
    return;
  }
  if (key === "l") {
    e.preventDefault();
    logout();
    return;
  }
  if (e.key === "ArrowUp" || key === "w") tryMove(-1, 0);
  else if (e.key === "ArrowDown" || key === "s") tryMove(1, 0);
  else if (e.key === "ArrowLeft" || key === "a") tryMove(0, -1);
  else if (e.key === "ArrowRight" || key === "d") tryMove(0, 1);
  else return;
  e.preventDefault();
  renderGrid();
});

document.getElementById("btn-identify").addEventListener("click", () => {
  identifyUser(document.getElementById("switch-name").value);
});
document.getElementById("switch-name").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    identifyUser(document.getElementById("switch-name").value);
  }
});
document.getElementById("btn-alice").addEventListener("click", () => {
  identifyUser("alice");
});
document.getElementById("btn-bob").addEventListener("click", () => {
  identifyUser("bob");
});
document.getElementById("btn-member-add").addEventListener("click", () => {
  postMembership("add");
});
document.getElementById("btn-member-remove").addEventListener("click", () => {
  postMembership("remove");
});
document.getElementById("btn-controls-refresh").addEventListener("click", () => {
  refreshControls().catch(() => {});
});

fetch("/api/config", { cache: "no-store" })
  .then((res) => res.json())
  .then((cfg) => {
    clientSideId = cfg.clientSideId;
    refreshControls().catch(() => {});
  })
  .catch(() => {
    clientSideId = null;
  });
