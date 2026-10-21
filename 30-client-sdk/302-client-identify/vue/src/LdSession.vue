<script setup>
/**
 * Provider is keyed by login session (initialKey), not the current identify key.
 * Changing initialKey remounts the client (logout / new login).
 * LaunchDarkly: ldInit once, then identify() — not a second initialize
 * https://launchdarkly.com/docs/sdk/features/identify
 * https://launchdarkly.com/docs/sdk/client-side/vue
 *
 * The slot waits for this client's `ready`. The plugin's shared ready ref stays
 * true from an earlier session, and `useLDFlag` reads `variation` once at setup
 * when it believes the client is ready — evaluating a child too early pins it to
 * the code default until the next `change:`.
 */
import { onUnmounted, ref } from "vue";
import { ldInit } from "launchdarkly-vue-client-sdk";

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

ldClient.on("ready", onReady);
ldClient.on("failed", onFailed);

onUnmounted(() => {
  ldClient.off("ready", onReady);
  ldClient.off("failed", onFailed);
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
