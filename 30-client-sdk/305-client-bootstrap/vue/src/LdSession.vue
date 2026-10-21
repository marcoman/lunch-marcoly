<script setup>
/**
 * Mounts the Vue SDK only after login, with the real user context.
 * Bootstrap values paint the grid before `ready`. The stream replaces them after.
 * LaunchDarkly: ldInit options.bootstrap
 * https://launchdarkly.com/docs/sdk/features/bootstrapping#javascript
 * https://launchdarkly.com/docs/sdk/client-side/vue
 */
import { onUnmounted, provide, ref } from "vue";
import { ldInit } from "launchdarkly-vue-client-sdk";
import { BOOTSTRAP, FLAG_COUNT, FLAG_HIGHLIGHT, formatChangeDetail } from "./ld.js";

const props = defineProps({
  clientSideId: { type: String, required: true },
  username: { type: String, required: true },
  onSdkEvent: { type: Function, required: true },
});

const [, ldClient] = ldInit({
  clientSideID: props.clientSideId,
  context: { kind: "user", key: props.username },
  options: {
    streaming: true,
    bootstrap: BOOTSTRAP,
  },
});

const ready = ref(false);
const paint = ref({
  source: "bootstrap",
  first: {
    highlight: BOOTSTRAP[FLAG_HIGHLIGHT],
    showCount: BOOTSTRAP[FLAG_COUNT],
  },
});
provide("paint", paint);

props.onSdkEvent(
  "bootstrap",
  `first paint highlight=${BOOTSTRAP[FLAG_HIGHLIGHT]} count=${BOOTSTRAP[FLAG_COUNT]} (before ready)`
);

function onReady() {
  ready.value = true;
  paint.value = { ...paint.value, source: "stream" };
  props.onSdkEvent("initialize", `key=${props.username}`);
  props.onSdkEvent("ready", "live flags replaced bootstrap");
}

function onFailed(err) {
  props.onSdkEvent("failed", String(err?.message || err));
  ready.value = true;
  paint.value = { ...paint.value, source: "stream" };
}

function onChange(payload) {
  const keys = formatChangeDetail(payload);
  props.onSdkEvent("change", keys ? `flags=${keys}` : "(stream update)");
}

ldClient.on("ready", onReady);
ldClient.on("failed", onFailed);
ldClient.on("change", onChange);

onUnmounted(() => {
  ldClient.off("ready", onReady);
  ldClient.off("failed", onFailed);
  ldClient.off("change", onChange);
  props.onSdkEvent("close", "client discarded (logout / re-init)");
  if (typeof ldClient.close === "function") {
    try {
      ldClient.close();
    } catch (_err) {
      /* ignore */
    }
  }
});
</script>

<template>
  <slot :ready="ready" />
</template>
