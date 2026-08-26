<script setup>
/**
 * Mounts the Vue SDK only after login, with the real user context.
 * Does not initialize anonymously then identify — that is example 32.
 * LaunchDarkly: ldInit, ready, change events
 * https://launchdarkly.com/docs/sdk/client-side/vue
 * https://launchdarkly.com/docs/sdk/features/flag-changes
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
  username: { type: String, required: true },
  onSdkEvent: { type: Function, required: true },
});

const [, ldClient] = ldInit({
  clientSideID: props.clientSideId,
  context: { kind: "user", key: props.username },
  streaming: true,
});

const ready = ref(false);

function onReady() {
  props.onSdkEvent("initialize", `key=${props.username}`);
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
