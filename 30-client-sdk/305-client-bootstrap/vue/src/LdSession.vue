<script setup>
/**
 * Mounts the Vue SDK only after login, with the real user context.
 * Bootstrap values paint the grid. A lab countdown holds that paint, then the stream replaces it.
 * LaunchDarkly: ldInit options.bootstrap
 * https://launchdarkly.com/docs/sdk/features/bootstrapping#javascript
 * https://launchdarkly.com/docs/sdk/client-side/vue
 */
import { onUnmounted, provide, ref } from "vue";
import { ldInit } from "launchdarkly-vue-client-sdk";
import { BOOTSTRAP, FLAG_COUNT, FLAG_HIGHLIGHT, STARTUP_DELAY_SEC, formatChangeDetail, playStartupTone } from "./ld.js";

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

const sdkReady = ref(false);
const holding = ref(true);
const secondsLeft = ref(STARTUP_DELAY_SEC);
const paint = ref({
  source: "bootstrap",
  holding: true,
  secondsLeft: STARTUP_DELAY_SEC,
  first: {
    highlight: BOOTSTRAP[FLAG_HIGHLIGHT],
    showCount: BOOTSTRAP[FLAG_COUNT],
  },
});
provide("paint", paint);

function syncPaint() {
  const showStream = sdkReady.value && !holding.value;
  paint.value = {
    source: showStream ? "stream" : "bootstrap",
    holding: holding.value,
    secondsLeft: secondsLeft.value,
    first: paint.value.first,
  };
}

playStartupTone("tick");
const startupTimer = setInterval(() => {
  if (secondsLeft.value <= 1) {
    secondsLeft.value = 0;
    holding.value = false;
    clearInterval(startupTimer);
    playStartupTone("finish");
  } else {
    secondsLeft.value -= 1;
    playStartupTone("tick");
  }
  syncPaint();
}, 1000);

props.onSdkEvent(
  "bootstrap",
  `first paint highlight=${BOOTSTRAP[FLAG_HIGHLIGHT]} count=${BOOTSTRAP[FLAG_COUNT]} (before ready)`
);

function onReady() {
  sdkReady.value = true;
  props.onSdkEvent("initialize", `key=${props.username}`);
  props.onSdkEvent(
    "ready",
    holding.value
      ? "live flags ready — grid stays on bootstrap during the startup delay"
      : "live flags replaced bootstrap"
  );
  syncPaint();
}

function onFailed(err) {
  props.onSdkEvent("failed", String(err?.message || err));
  sdkReady.value = true;
  syncPaint();
}

function onChange(payload) {
  const keys = formatChangeDetail(payload);
  props.onSdkEvent("change", keys ? `flags=${keys}` : "(stream update)");
}

ldClient.on("ready", onReady);
ldClient.on("failed", onFailed);
ldClient.on("change", onChange);

onUnmounted(() => {
  clearInterval(startupTimer);
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
  <slot />
</template>
