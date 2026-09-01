<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import {
  segmentIdentify,
  segmentJoinInnerCircle,
  segmentLeaveInnerCircle,
} from "./segment.js";

const BANNER = "34-synced-segments-twilio[vue]";
const ROWS = ["t", "m", "b"];
const COLS = ["l", "m", "r"];
const SEGMENT_SYNC_HINT =
  "Wait for Twilio Segment → LaunchDarkly Audiences (often tens of seconds; first destination sync ~10 min), then change:.";

const props = defineProps({
  username: { type: String, required: true },
  showBadge: { type: Boolean, required: true },
  ldClient: { type: Object, default: null },
  row: { type: Number, required: true },
  col: { type: Number, required: true },
  previous: { type: Object, default: null },
  moveCount: { type: Number, required: true },
  clientSideId: { type: String, default: null },
  sdkCallLog: { type: Array, required: true },
  initializeCount: { type: Number, required: true },
  identifyCount: { type: Number, required: true },
  changeCount: { type: Number, required: true },
  controls: { type: Object, default: null },
  controlsWarn: { type: String, default: "" },
  onContextKey: { type: Function, required: true },
  onSdkEvent: { type: Function, required: true },
  onKeyDown: { type: Function, required: true },
  onRefresh: { type: Function, required: true },
  onPostControl: { type: Function, required: true },
  segmentWriteKey: { type: String, default: null },
});

const gridRef = ref(null);
const logRef = ref(null);
const switchName = ref(props.username);
const identifyBusy = ref(false);
const membershipBusy = ref(false);
const membershipMsg = ref("");
const membershipErr = ref(false);

function formatPos(r, c) {
  return `${ROWS[r]}/${COLS[c]}`;
}

const segmentMeta = computed(() => {
  const seg = props.controls?.segment || {};
  if (seg.found) {
    return `${seg.key}${seg.unbounded ? " (unbounded / big)" : " (list-based)"}`;
  }
  if (seg.error) return `Segment missing — ${seg.error}`;
  if (seg.key) return `${seg.key} not found. Twilio creates it on first Audiences sync; set LD_TWILIO_SEGMENT_KEY.`;
  return "Loading segment…";
});

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
    if (props.segmentWriteKey) await segmentIdentify(props.segmentWriteKey, next);
    gridRef.value?.focus();
  } finally {
    identifyBusy.value = false;
  }
}

async function postMembership(action) {
  if (!props.username || membershipBusy.value) return;
  membershipBusy.value = true;
  membershipErr.value = false;
  membershipMsg.value = `${action === "add" ? "Joining" : "Leaving"} ${props.username} via Twilio Segment…`;
  try {
    if (action === "add") {
      await segmentJoinInnerCircle(props.segmentWriteKey, props.username);
      membershipMsg.value = `Sent identify + track “Joined Inner Circle” for ${props.username}. ${SEGMENT_SYNC_HINT}`;
    } else {
      await segmentLeaveInnerCircle(props.segmentWriteKey, props.username);
      membershipMsg.value = `Sent identify + track “Left Inner Circle” for ${props.username}. ${SEGMENT_SYNC_HINT}`;
    }
    await props.onRefresh();
  } catch (err) {
    membershipErr.value = true;
    membershipMsg.value = String(err.message || err);
  } finally {
    membershipBusy.value = false;
  }
}

onMounted(() => {
  gridRef.value?.focus();
});

watch(
  () => props.showBadge,
  () => {
    document.body.classList.toggle("inner-circle-on", props.showBadge);
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
  () => [props.username, props.segmentWriteKey],
  ([name, writeKey]) => {
    if (name && writeKey) segmentIdentify(writeKey, name).catch(() => {});
  },
  { immediate: true }
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
        <div class="name-row">
          Name: <span>{{ username }}</span>
          <span v-if="showBadge" class="inner-badge">inner circle</span>
        </div>
        <div>Current position: {{ formatPos(row, col) }}</div>
        <div>
          Previous position:
          {{ previous ? formatPos(previous.row, previous.col) : "—" }}
        </div>
        <div>Count: {{ moveCount }}</div>
      </div>
      <div class="grid" aria-label="3 by 3 grid">
        <div
          v-for="i in 9"
          :key="i"
          :class="
            Math.floor((i - 1) / 3) === row && (i - 1) % 3 === col
              ? 'cell selected'
              : 'cell'
          "
        >
          {{
            Math.floor((i - 1) / 3) === row && (i - 1) % 3 === col ? "X" : ""
          }}
        </div>
      </div>
      <p class="hint">
        Use arrow keys or WASD to move. Press L to log out, Q to quit. Membership and identify live
        in the lab rail.
      </p>
    </section>
    <aside class="ld-rail" aria-label="LaunchDarkly lab">
      <h2>LaunchDarkly · lab</h2>
      <div style="font-weight: 650">Inner circle</div>
      <p class="ld-about-p" style="margin-top: 0.35rem">
        Flag <code>show-twilio-inner-circle-badge</code> is true when this context is in the
        Twilio-synced segment (default key <code>marcoly-twilio-inner-circle</code>). Join/leave
        calls Twilio Segment <code>identify</code> + <code>track</code>; LaunchDarkly Audiences
        syncs membership.
        <a href="https://launchdarkly.com/docs/home/flags/twilio">Twilio Segment Audiences</a>.
      </p>
      <p class="ld-controls-meta">{{ segmentMeta }}</p>
      <div class="membership-row">
        <button type="button" @click="postMembership('add')">Join inner circle</button>
        <button type="button" @click="postMembership('remove')">Leave inner circle</button>
      </div>
      <p v-if="membershipMsg" id="membership-msg" :class="membershipErr ? 'error' : ''">
        {{ membershipMsg }}
      </p>

      <div style="font-weight: 650">Identify</div>
      <p class="ld-about-p" style="margin-top: 0.35rem">
        Same SDK client. <code>{{ "identify({ kind: \"user\", key })" }}</code> switches who is evaluated —
        badge follows that key’s membership.
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
        initialize ×{{ initializeCount }} · identify ×{{ identifyCount }} · change ×{{ changeCount }}
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
            ? `Client-side ID loaded (${clientSideId.slice(0, 6)}…). Badge=${showBadge ? "on" : "off"}.`
            : "No LD_CLIENT_SIDE_ID — using code default (badge off)."
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
      <div>
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
        Leave the flag <strong>on</strong>. The lesson is membership, not the kill switch. Docs:
        <a href="https://launchdarkly.com/docs/home/flags/twilio">Twilio Segment Audiences</a>
        ·
        <a href="https://launchdarkly.com/docs/home/flags/synced-segments">synced segments</a>
        ·
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
