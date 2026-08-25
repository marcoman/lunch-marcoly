/**
 * Browser grid navigator — same rules as 00-reference-code.
 * The page is the application; this file is the behavior. No LaunchDarkly.
 */

const ROWS = ["t", "m", "b"];
const COLS = ["l", "m", "r"];

let username = "";
let row = 1;
let col = 1;
let previous = null;

function formatPos(r, c) {
  return `${ROWS[r]}/${COLS[c]}`;
}

/** Move one step; returns true when position changed (updates previous). */
function tryMove(dr, dc) {
  const nr = Math.max(0, Math.min(2, row + dr));
  const nc = Math.max(0, Math.min(2, col + dc));
  if (nr === row && nc === col) return false;
  previous = { row, col };
  row = nr;
  col = nc;
  return true;
}

function renderGrid() {
  document.getElementById("hdr-name").textContent = username;
  document.getElementById("hdr-current").textContent = formatPos(row, col);
  document.getElementById("hdr-previous").textContent =
    previous ? formatPos(previous.row, previous.col) : "—";

  const grid = document.getElementById("grid");
  grid.innerHTML = "";
  for (let r = 0; r < 3; r++) {
    for (let c = 0; c < 3; c++) {
      const cell = document.createElement("div");
      cell.className = "cell" + (r === row && c === col ? " selected" : "");
      cell.textContent = r === row && c === col ? "X" : "";
      grid.appendChild(cell);
    }
  }
}

function logout() {
  username = "";
  row = 1;
  col = 1;
  previous = null;
  document.getElementById("username").value = "";
  document.getElementById("login-error").classList.add("hidden");
  document.getElementById("grid-screen").classList.add("hidden");
  document.getElementById("login-screen").classList.remove("hidden");
  document.getElementById("username").focus();
}

function quit() {
  window.close();
  document.body.innerHTML = "<p>Application closed. You may close this tab.</p>";
}

function startGrid(name) {
  username = name;
  row = 1;
  col = 1;
  previous = null;
  document.getElementById("login-screen").classList.add("hidden");
  document.getElementById("grid-screen").classList.remove("hidden");
  renderGrid();
  document.getElementById("grid-screen").focus();
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
