<script setup>
import { nextTick, onMounted, ref, watch } from "vue";

const BANNER = "32-client-identify[vue]";
const ROWS = ["t", "m", "b"];
const COLS = ["l", "m", "r"];

const props = defineProps({
  username: { type: String, required: true },
  highlight: { type: String, required: true },
  showCount: { type: Boolean, required: true },
  ldClient: { type: Object, default: null },
  row: { type: Number, required: true },
  col: { type: Number, required: true },
  previous: { type: Object, default: null },
  moveCount: { type: Number, required: true },
  clientSideId: { type: String, default: null },
  sdkCallLog: { type: Array, required: true },
  initializeCount: { type: Number, required: true },
  identifyCount: { type: Number, required: true },
  controls: { type: Object, default: null },
  controlsWarn: { type: String, default: "" },
  onContextKey: { type: Function, required: true },
  onSdkEvent: { type: Function, required: true },
  onKeyDown: { type: Function, required: true },
  onRefresh: { type: Function, required: true },
  onPostControl: { type: Function, required: true },
});

const gridRef = ref(null);
const logRef = ref(null);
const switchName = ref(props.username);
const identifyBusy = ref(false);

function formatPos(r, c) {
  return `${ROWS[r]}/${COLS[c]}`;
}

function cellClass(r, c) {
  const selected = r === props.row && c === props.col;
  const cls = ["cell"];
  if (selected) {
    cls.push("selected");
    if (props.highlight !== "none") cls.push(`highlight-${props.highlight}`);
  }
  return cls.join(" ");
}

async function identifyUser(name) {
  const next = (name || "").trim();
  if (!next || identifyBusy.value) return;
  if (!props.ldClient || typeof props.ldClient.identify !== "function") {
    props.onContextKey(next);
    return;
  }
  identifyBusy.value = true;
  try {
    props.onSdkEvent("identify", `key=${next}  (no initialize)`);
    await props.ldClient.identify({ kind: "user", key: next });
    props.onContextKey(next);
    gridRef.value?.focus();
  } finally {
    identifyBusy.value = false;
  }
}

onMounted(() => {
  gridRef.value?.focus();
});

watch(
  () => props.highlight,
  () => {
    document.body.classList.toggle("highlight-on", props.highlight !== "none");
    nextTick(() => gridRef.value?.focus());
  },
  { immediate: true }
);

watch(
  () => props.username,
  (name) => {
    switchName.value = name;
  }
);

watch(
  () => props.sdkCallLog.length,
  async () => {
    await nextTick();
    if (logRef.value) logRef.value.scrollTop = logRef.value.scrollHeight;
  }
);
</script>

<template>
  <div id="app-shell">
    <section id="grid-screen" tabindex="0" ref="gridRef" @keydown="onKeyDown">
      <div class="header">
        <div class="app-banner">{{ BANNER }}</div>
        <div>
          Name:
          <span :class="highlight !== 'none' ? `color-${highlight}` : ''">{{ username }}</span>
        </div>
        <div>Current position: {{ formatPos(row, col) }}</div>
        <div>
          Previous position:
          {{ previous ? formatPos(previous.row, previous.col) : "—" }}
        </div>
        <div v-if="showCount">Count: {{ moveCount }}</div>
      </div>
      <div class="grid" aria-label="3 by 3 grid">
        <div
          v-for="i in 9"
          :key="i"
          :class="cellClass(Math.floor((i - 1) / 3), (i - 1) % 3)"
        >
          {{
            Math.floor((i - 1) / 3) === row && (i - 1) % 3 === col ? "X" : ""
          }}
        </div>
      </div>
      <p class="hint">
        Use arrow keys or WASD to move. Press L to log out, Q to quit. Switch user in the lab rail
        (identify — no reload).
      </p>
    </section>
    <aside class="ld-rail" aria-label="LaunchDarkly lab">
      <h2>LaunchDarkly · lab</h2>
      <div style="font-weight: 650">Identify</div>
      <p class="ld-about-p" style="margin-top: 0.35rem">
        Same SDK client. <code>{{ "identify({ kind: \"user\", key })" }}</code> changes targeting without
        reload. Grid position and Count persist.
      </p>
      <div class="identify-row">
        <input
          type="text"
          autocomplete="username"
          aria-label="Context key"
          v-model="switchName"
          @keydown.enter.prevent="identifyUser(switchName)"
        />
        <button type="button" @click="identifyUser(switchName)">Identify</button>
        <button type="button" @click="identifyUser('alice')">Alice</button>
        <button type="button" @click="identifyUser('bob')">Bob</button>
      </div>
      <div style="font-weight: 650">SDK calls</div>
      <p class="sdk-call-counts">
        initialize ×{{ initializeCount }} · identify ×{{ identifyCount }}
      </p>
      <div class="sdk-log" ref="logRef" aria-live="polite">
        <template v-if="!sdkCallLog.length">No SDK client calls yet.</template>
        <div
          v-else
          v-for="(entry, i) in sdkCallLog"
          :key="i"
          :class="'sdk-log-line kind-' + entry.kind"
        >
          {{ entry.t }} {{ entry.kind === "change" ? "change:" : entry.kind
          }}{{ entry.detail ? `  ${entry.detail}` : "" }}
        </div>
      </div>
      <p class="ld-controls-meta">
        {{
          clientSideId
            ? `Client-side ID loaded (${clientSideId.slice(0, 6)}…). Highlight=${highlight} count=${showCount}.`
            : "No LD_CLIENT_SIDE_ID — using code defaults (none / hidden)."
        }}
      </p>
      <p class="ld-controls-meta">
        {{
          controls?.projectKey
            ? `Project ${controls.projectKey} · env ${controls.environmentKey}`
            : "REST controls unavailable."
        }}
      </p>
      <div v-if="controlsWarn" class="ld-controls-warn">{{ controlsWarn }}</div>
      <div class="ld-toolbar">
        <button type="button" @click="onRefresh().catch(() => {})">Refresh status</button>
      </div>
      <div>
        <div v-for="f in controls?.flags || []" :key="f.key" class="flag-card">
          <div class="flag-card-top">
            <div>
              <h3>{{ f.label }}</h3>
              <div class="flag-key">{{ f.key }}</div>
              <p class="flag-summary">{{ f.summary || "" }}</p>
              <p class="flag-hint">{{ f.targetingHint || "" }}</p>
            </div>
            <button
              type="button"
              :class="'flag-toggle ' + (f.on ? 'on' : 'off')"
              @click="onPostControl(f.key, { on: !f.on })"
            >
              {{ f.on === true ? "On" : f.on === false ? "Off" : "?" }}
            </button>
          </div>
        </div>
      </div>
      <p class="ld-about-p">
        This example teaches <strong>identify</strong>, not a second <code>initialize</code>. Keys:
        <code>alice</code> (green + count), <code>bob</code> (blue, no count), anything else (none).
        Docs:
        <a href="https://launchdarkly.com/docs/sdk/features/identify">identify</a>
        ·
        <a href="https://launchdarkly.com/docs/sdk/client-side/vue">Vue SDK</a>.
      </p>
      <div style="margin-top: 1rem; font-weight: 650">Context</div>
      <pre class="context-pre">{{
        username
          ? JSON.stringify({ kind: "user", key: username }, null, 2)
          : "Log in to set the evaluation context."
      }}</pre>
    </aside>
  </div>
</template>
