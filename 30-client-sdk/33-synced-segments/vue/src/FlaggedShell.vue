<script setup>
import { computed } from "vue";
import { useLDClient, useLDFlag } from "launchdarkly-vue-client-sdk";
import { FLAG_BADGE } from "./ld.js";
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
  identifyCount: { type: Number, required: true },
  changeCount: { type: Number, required: true },
  controls: { type: Object, default: null },
  controlsWarn: { type: String, default: "" },
  onContextKey: { type: Function, required: true },
  onSdkEvent: { type: Function, required: true },
  onKeyDown: { type: Function, required: true },
  onRefresh: { type: Function, required: true },
  onPostControl: { type: Function, required: true },
});

const badgeRaw = useLDFlag(FLAG_BADGE, false);
const showBadge = computed(() => Boolean(badgeRaw.value));
const ldClient = useLDClient();
</script>

<template>
  <LoggedInUI v-bind="$props" :show-badge="showBadge" :ld-client="ldClient" />
</template>
