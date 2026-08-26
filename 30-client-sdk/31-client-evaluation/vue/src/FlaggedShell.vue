<script setup>
import { computed } from "vue";
import { useLDFlag } from "launchdarkly-vue-client-sdk";
import { FLAG_COUNT, FLAG_HIGHLIGHT, interpretHighlight } from "./ld.js";
import LoggedInUI from "./LoggedInUI.vue";

defineProps({
  username: { type: String, required: true },
  row: { type: Number, required: true },
  col: { type: Number, required: true },
  previous: { type: Object, default: null },
  moveCount: { type: Number, required: true },
  clientSideId: { type: String, default: null },
  sdkCallLog: { type: Array, required: true },
  initializeCount: { type: Number, required: true },
  changeCount: { type: Number, required: true },
  controls: { type: Object, default: null },
  controlsWarn: { type: String, default: "" },
  onKeyDown: { type: Function, required: true },
  onRefresh: { type: Function, required: true },
  onPostControl: { type: Function, required: true },
});

const highlightRaw = useLDFlag(FLAG_HIGHLIGHT, "none");
const showCount = useLDFlag(FLAG_COUNT, false);
const highlight = computed(() => interpretHighlight(highlightRaw.value));
</script>

<template>
  <LoggedInUI
    v-bind="$props"
    :highlight="highlight"
    :show-count="Boolean(showCount)"
  />
</template>
