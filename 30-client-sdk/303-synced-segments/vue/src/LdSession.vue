<script setup>
/**
 * Login session client: identify + streaming change: for the inner-circle badge.
 * LaunchDarkly: ldInit, identify, change:
 * https://launchdarkly.com/docs/home/flags/synced-segments
 * https://launchdarkly.com/docs/sdk/client-side/vue
 *
 * The slot waits for this client's `ready`. The plugin's shared ready ref stays
 * true from an earlier session, and `useLDFlag` reads `variation` once at setup
 * when it believes the client is ready — evaluating a child too early pins it to
 * the code default until the next `change:`.
 */
import { onUnmounted, ref } from "vue";
import { ldInit } from "launchdarkly-vue-client-sdk";
import { formatChangeDetail } from "./ld.js";

const props = defineProps({
  clientSideId: { type: String, required: true },
  initialKey: { type: String, required: true },
  onSdkEvent: { type: Function, required: true },
});

const [, ldClient] = ldInit({
  clientSideID: props.clientSideId,
  context: { kind: "user", key: props.initialKey },
  streaming: true,
});

const ready = ref(false);

function onReady() {
  props.onSdkEvent("initialize", `key=${props.initialKey}`);
  ready.value = true;
}

function onFailed(err) {
  props.onSdkEvent("failed", String(err?.message || err));
  ready.value = true;
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
  <slot v-if="ready" />
  <p v-else class="hint">Connecting to LaunchDarkly…</p>
</template>
