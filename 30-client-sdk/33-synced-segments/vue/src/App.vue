<script setup>
import { onMounted, ref, watch } from "vue";
import FlaggedShell from "./FlaggedShell.vue";
import LdSession from "./LdSession.vue";
import LoggedInUI from "./LoggedInUI.vue";

const BANNER = "33-synced-segments[vue]";

const clientSideId = ref(null);
const authKey = ref("");
const username = ref("");
const loginValue = ref("");
const loginError = ref(false);
const closed = ref(false);
const nav = ref({ row: 1, col: 1, previous: null, moveCount: 0 });
const sdkCallLog = ref([]);
const initializeCount = ref(0);
const identifyCount = ref(0);
const changeCount = ref(0);
const controls = ref(null);
const controlsWarn = ref("");

function onSdkEvent(kind, detail) {
  const line = { t: new Date().toISOString().slice(11, 23), kind, detail };
  console.log(`[33 synced-segments][vue] ${kind}${detail ? " " + detail : ""}`);
  const next = [...sdkCallLog.value, line];
  sdkCallLog.value = next.length > 40 ? next.slice(-40) : next;
  if (kind === "initialize") initializeCount.value += 1;
  if (kind === "identify") identifyCount.value += 1;
  if (kind === "change") changeCount.value += 1;
}

async function refreshControls() {
  try {
    const res = await fetch("/api/flag-controls", { cache: "no-store" });
    const data = await res.json();
    controls.value = data;
    if (!data.configured) {
      controlsWarn.value =
        "Controls need " + (data.missing || []).join(", ") + " on the Vite host (not in the page).";
    } else {
      controlsWarn.value = "";
    }
  } catch (err) {
    controlsWarn.value = String(err.message || err);
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

function tryMove(dr, dc) {
  const cur = nav.value;
  const nr = Math.max(0, Math.min(2, cur.row + dr));
  const nc = Math.max(0, Math.min(2, cur.col + dc));
  if (nr === cur.row && nc === cur.col) return;
  nav.value = {
    row: nr,
    col: nc,
    previous: { row: cur.row, col: cur.col },
    moveCount: cur.moveCount + 1,
  };
}

function handleGridKey(e) {
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
}

function startGrid(name) {
  authKey.value = name;
  username.value = name;
  nav.value = { row: 1, col: 1, previous: null, moveCount: 0 };
  if (!clientSideId.value) {
    onSdkEvent("skip", "no client-side ID — did not initialize the Vue SDK");
  }
}

function logout() {
  onSdkEvent("session", "logged out — next login will initialize again (count kept)");
  authKey.value = "";
  username.value = "";
  nav.value = { row: 1, col: 1, previous: null, moveCount: 0 };
  loginValue.value = "";
  loginError.value = false;
  document.body.classList.remove("inner-circle-on");
}

function quit() {
  window.close();
  closed.value = true;
}

function setUsername(key) {
  username.value = key;
}

function submitLogin() {
  const name = loginValue.value.trim();
  if (!name) {
    loginError.value = true;
    return;
  }
  loginError.value = false;
  startGrid(name);
}

onMounted(() => {
  fetch("/api/config", { cache: "no-store" })
    .then((res) => res.json())
    .then((cfg) => {
      clientSideId.value = cfg.clientSideId;
      refreshControls();
    })
    .catch(() => {
      clientSideId.value = null;
    });
});

watch(
  [authKey, closed],
  () => {
    document.body.classList.toggle("grid-active", Boolean(authKey.value) && !closed.value);
  },
  { immediate: true }
);
</script>

<template>
  <p v-if="closed">Application closed. You may close this tab.</p>
  <template v-else>
    <section v-if="!authKey" id="login-screen">
      <div class="app-banner">{{ BANNER }}</div>
      <h1>Login</h1>
      <label for="username">Username</label>
      <input
        id="username"
        type="text"
        autocomplete="username"
        autofocus
        v-model="loginValue"
        @keydown.enter="submitLogin"
      />
      <p :class="loginError ? 'error' : 'error hidden'">Username is required.</p>
      <button id="login-btn" type="button" @click="submitLogin">Continue</button>
    </section>
    <LdSession
      v-else-if="clientSideId"
      :key="authKey"
      :client-side-id="clientSideId"
      :initial-key="authKey"
      :on-sdk-event="onSdkEvent"
    >
      <FlaggedShell
        :username="username"
        :row="nav.row"
        :col="nav.col"
        :previous="nav.previous"
        :move-count="nav.moveCount"
        :client-side-id="clientSideId"
        :sdk-call-log="sdkCallLog"
        :initialize-count="initializeCount"
        :identify-count="identifyCount"
        :change-count="changeCount"
        :controls="controls"
        :controls-warn="controlsWarn"
        :on-context-key="setUsername"
        :on-sdk-event="onSdkEvent"
        :on-key-down="handleGridKey"
        :on-refresh="refreshControls"
        :on-post-control="postControl"
      />
    </LdSession>
    <LoggedInUI
      v-else
      :username="username"
      :show-badge="false"
      :ld-client="null"
      :row="nav.row"
      :col="nav.col"
      :previous="nav.previous"
      :move-count="nav.moveCount"
      :client-side-id="null"
      :sdk-call-log="sdkCallLog"
      :initialize-count="initializeCount"
      :identify-count="identifyCount"
      :change-count="changeCount"
      :controls="controls"
      :controls-warn="controlsWarn"
      :on-context-key="setUsername"
      :on-sdk-event="onSdkEvent"
      :on-key-down="handleGridKey"
      :on-refresh="refreshControls"
      :on-post-control="postControl"
    />
  </template>
</template>
