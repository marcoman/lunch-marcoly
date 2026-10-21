<script setup>
/**
 * Watches moveCount and sends grid_move for a real cell change.
 * LaunchDarkly: track with custom data, then flush
 * https://launchdarkly.com/docs/sdk/features/events
 */
import { computed, inject, watch } from "vue";
import { useLDFlag } from "launchdarkly-vue-client-sdk";
import { FLAG_COUNT, FLAG_HIGHLIGHT, interpretHighlight } from "./ld.js";
import LoggedInUI from "./LoggedInUI.vue";

const props = defineProps({
  username: { type: String, required: true },
  row: { type: Number, required: true },
  col: { type: Number, required: true },
  previous: { type: Object, default: null },
  moveCount: { type: Number, required: true },
  clientSideId: { type: String, default: null },
  sdkCallLog: { type: Array, required: true },
  initializeCount: { type: Number, required: true },
  changeCount: { type: Number, required: true },
  trackCount: { type: Number, required: true },
  controls: { type: Object, default: null },
  controlsWarn: { type: String, default: "" },
  onKeyDown: { type: Function, required: true },
  onRefresh: { type: Function, required: true },
  onPostControl: { type: Function, required: true },
  onSdkEvent: { type: Function, required: true },
});

const ROWS = ["t", "m", "b"];
const COLS = ["l", "m", "r"];
const EVENT_MOVE = "grid_move";

const highlightRaw = useLDFlag(FLAG_HIGHLIGHT, "none");
const showCount = useLDFlag(FLAG_COUNT, false);
const highlight = computed(() => interpretHighlight(highlightRaw.value));
const ldClient = inject("ldClient", null);

function formatPos(r, c) {
  return `${ROWS[r]}/${COLS[c]}`;
}

watch(
  () => props.moveCount,
  (count) => {
    const client = ldClient?.value ?? ldClient;
    if (!client || typeof client.track !== "function" || count < 1 || !props.previous) return;
    const from = formatPos(props.previous.row, props.previous.col);
    const to = formatPos(props.row, props.col);
    const data = { from, to };
    client.track(EVENT_MOVE, data);
    if (typeof client.flush === "function") {
      Promise.resolve(client.flush()).catch(() => {});
    }
    props.onSdkEvent("track", `${EVENT_MOVE}  ${JSON.stringify(data)}`);
  }
);
</script>

<template>
  <LoggedInUI
    v-bind="$props"
    :highlight="highlight"
    :show-count="Boolean(showCount)"
  />
</template>
