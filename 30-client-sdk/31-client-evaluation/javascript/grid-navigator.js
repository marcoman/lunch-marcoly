/**
 * Browser grid + LaunchDarkly JavaScript SDK.
 * Baseline navigation matches 02-reference-client-code.
 */

const ROWS = ["t", "m", "b"];
const COLS = ["l", "m", "r"];

/** Feature flags — string variation (highlight) + boolean variation (count). */
const FLAG_HIGHLIGHT = "enable-client-grid-highlight";
const FLAG_COUNT = "show-client-move-count";

const COLORS = new Set(["green", "yellow", "red", "blue", "purple"]);

let username = "";
let row = 1;
let col = 1;
let previous = null;
let moveCount = 0;
let highlight = "none";
let showCount = false;
let ldClient = null;
let clientSideId = null;

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

function interpretHighlight(raw) {
  if (typeof raw === "string" && COLORS.has(raw.trim().toLowerCase())) {
    return raw.trim().toLowerCase();
  }
  return "none";
}

/**
 * Read current flag values from the client SDK.
 * LaunchDarkly: variation (boolean + string)
 * https://launchdarkly.com/docs/sdk/features/evaluating-flags
 */
function readFlagsFromClient() {
  if (!ldClient) {
    highlight = "none";
    showCount = false;
    return;
  }
  highlight = interpretHighlight(ldClient.variation(FLAG_HIGHLIGHT, "none"));
  showCount = Boolean(ldClient.variation(FLAG_COUNT, false));
}

function renderGrid() {
  const nameEl = document.getElementById("hdr-name");
  nameEl.textContent = username;
  nameEl.className = highlight !== "none" ? `color-${highlight}` : "";
  document.getElementById("hdr-current").textContent = formatPos(row, col);
  document.getElementById("hdr-previous").textContent =
    previous ? formatPos(previous.row, previous.col) : "—";
  const countRow = document.getElementById("hdr-count-row");
  if (showCount) {
    countRow.classList.remove("hidden");
    document.getElementById("hdr-count").textContent = String(moveCount);
  } else {
    countRow.classList.add("hidden");
  }
  document.body.classList.toggle("highlight-on", highlight !== "none");

  const grid = document.getElementById("grid");
  grid.innerHTML = "";
  for (let r = 0; r < 3; r++) {
    for (let c = 0; c < 3; c++) {
      const selected = r === row && c === col;
      const cell = document.createElement("div");
      cell.className = "cell";
      if (selected) {
        cell.classList.add("selected");
        if (highlight !== "none") cell.classList.add(`highlight-${highlight}`);
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
  const sdkMeta = document.getElementById("sdk-meta");
  if (sdkMeta) {
    sdkMeta.textContent = clientSideId
      ? `Client-side ID loaded (${clientSideId.slice(0, 6)}…). Highlight=${highlight} count=${showCount}.`
      : "No LD_CLIENT_SIDE_ID — using code defaults (none / hidden).";
  }
}

function closeLdClient() {
  if (ldClient) {
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
    readFlagsFromClient();
    return;
  }
  const context = { kind: "user", key: name };
  ldClient = LDClient.initialize(clientSideId, context);
  /**
   * Streaming updates — re-read variation() when targeting changes.
   * LaunchDarkly: change / change:flag-key events
   * https://launchdarkly.com/docs/sdk/features/flag-changes
   */
  ldClient.on("change", () => {
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

function logout() {
  closeLdClient();
  username = "";
  row = 1;
  col = 1;
  previous = null;
  moveCount = 0;
  highlight = "none";
  showCount = false;
  document.getElementById("username").value = "";
  document.getElementById("login-error").classList.add("hidden");
  document.getElementById("app-shell").classList.add("hidden");
  document.body.classList.remove("grid-active");
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

async function refreshControls() {
  const meta = document.getElementById("controls-meta");
  const warn = document.getElementById("controls-warn");
  const list = document.getElementById("controls-list");
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
    list.innerHTML = "";
    for (const f of data.flags || []) {
      const card = document.createElement("div");
      card.className = "flag-card";
      const onLabel = f.on === true ? "On" : f.on === false ? "Off" : "?";
      let colorSelect = "";
      if (f.variationKind === "string" && f.colorOptions && f.colorOptions.length) {
        const opts = f.colorOptions
          .map((c) => {
            const sel = c === f.servedWhenOnFallthrough ? " selected" : "";
            return `<option value="${c}"${sel}>${c}</option>`;
          })
          .join("");
        colorSelect = `<div class="flag-color-row"><label>Fallthrough</label>
          <select class="flag-color-select" data-key="${f.key}">${opts}</select></div>`;
      }
      card.innerHTML = `<div class="flag-card-top">
          <div>
            <h3>${f.label}</h3>
            <div class="flag-key">${f.key}</div>
            <p class="flag-summary">${f.summary || ""}</p>
            <p class="flag-hint">${f.targetingHint || ""}</p>
            ${colorSelect}
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
    list.querySelectorAll(".flag-color-select").forEach((sel) => {
      sel.addEventListener("change", async () => {
        await postControl(sel.getAttribute("data-key"), { fallthrough: sel.value });
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
