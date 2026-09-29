/**
 * 35-client-bootstrap React Web SDK session.
 * LaunchDarkly: createLDReactProvider bootstrap, useStringVariation, useBoolVariation
 * https://launchdarkly.com/docs/sdk/features/bootstrapping#javascript
 */
import { useEffect, useMemo, useRef } from "react";
import {
  createLDReactProvider,
  useBoolVariation,
  useInitializationStatus,
  useLDClient,
  useStringVariation,
} from "@launchdarkly/react-sdk";

export const FLAG_HIGHLIGHT = "enable-client-bootstrap-highlight";
export const FLAG_COUNT = "show-client-bootstrap-move-count";

/**
 * First-paint values passed to the JS client as bootstrap.
 * LaunchDarkly: bootstrap
 * https://launchdarkly.com/docs/sdk/features/bootstrapping#javascript
 */
export const BOOTSTRAP = {
  [FLAG_HIGHLIGHT]: "green",
  [FLAG_COUNT]: true,
};

const COLORS = new Set(["green", "yellow", "red", "blue", "purple"]);

export function interpretHighlight(raw) {
  if (typeof raw === "string" && COLORS.has(raw.trim().toLowerCase())) {
    return raw.trim().toLowerCase();
  }
  return "none";
}

function formatChangeDetail(payload) {
  if (payload == null) return "";
  if (Array.isArray(payload)) return payload.join(", ");
  if (typeof payload === "object") return Object.keys(payload).join(", ");
  return String(payload);
}

/**
 * Mounts the React Web SDK only after login, with the real user context.
 * Does not initialize anonymously then identify — that is example 32.
 */
export function LdSession({ clientSideId, username, onSdkEvent, children }) {
  const Provider = useMemo(
    () =>
      createLDReactProvider(clientSideId, { kind: "user", key: username }, {
        ldOptions: { streaming: true },
        bootstrap: BOOTSTRAP,
      }),
    [clientSideId, username]
  );
  return (
    <Provider>
      <LdBridge username={username} onSdkEvent={onSdkEvent}>
        {children}
      </LdBridge>
    </Provider>
  );
}

function LdBridge({ username, onSdkEvent, children }) {
  const { status } = useInitializationStatus();
  const ldClient = useLDClient();
  const bootstrapLogged = useRef(false);
  const initLogged = useRef(false);

  useEffect(() => {
    if (bootstrapLogged.current) return;
    bootstrapLogged.current = true;
    onSdkEvent(
      "bootstrap",
      `first paint highlight=${BOOTSTRAP[FLAG_HIGHLIGHT]} count=${BOOTSTRAP[FLAG_COUNT]} (before ready)`
    );
  }, [onSdkEvent]);

  useEffect(() => {
    if (status !== "complete" || initLogged.current) return;
    initLogged.current = true;
    onSdkEvent("initialize", `key=${username}`);
  }, [status, username, onSdkEvent]);

  /**
   * Streaming flag updates — the variation hooks re-render; this listener is
   * only for the lab SDK call log (not WASD).
   * LaunchDarkly: change events
   * https://launchdarkly.com/docs/sdk/features/flag-changes
   */
  useEffect(() => {
    if (!ldClient || typeof ldClient.on !== "function") return undefined;
    const onChange = (payload) => {
      const keys = formatChangeDetail(payload);
      onSdkEvent("change", keys ? `flags=${keys}` : "(stream update)");
    };
    ldClient.on("change", onChange);
    return () => {
      if (typeof ldClient.off === "function") ldClient.off("change", onChange);
    };
  }, [ldClient, onSdkEvent]);

  const clientRef = useRef(null);
  clientRef.current = ldClient;

  useEffect(() => {
    return () => {
      onSdkEvent("close", "client discarded (logout / re-init)");
      const client = clientRef.current;
      if (client && typeof client.close === "function") {
        try {
          client.close();
        } catch (_err) {
          /* ignore */
        }
      }
    };
  }, [username, onSdkEvent]);

  return children;
}

/**
 * Until the client is ready, the grid shows the bootstrap map.
 * After ready, typed variation hooks show the live values.
 * LaunchDarkly: bootstrap, then variation
 * https://launchdarkly.com/docs/sdk/features/bootstrapping#javascript
 */
export function usePaintReport() {
  const init = useInitializationStatus();
  const status = typeof init === "string" ? init : init && init.status;
  const live = useGridFlags();
  const ready = status === "complete" || status === "failed" || status === "timeout";
  const first = useRef({
    highlight: BOOTSTRAP[FLAG_HIGHLIGHT],
    showCount: BOOTSTRAP[FLAG_COUNT],
  });
  return {
    source: ready ? "stream" : "bootstrap",
    first: first.current,
    highlight: ready ? live.highlight : first.current.highlight,
    showCount: ready ? live.showCount : first.current.showCount,
  };
}

/**
 * Read flags via typed variation hooks (React Web SDK).
 * Keys stay kebab-case — not the deprecated camelCase useFlags path.
 */
export function useGridFlags() {
  const highlightRaw = useStringVariation(FLAG_HIGHLIGHT, "none");
  const showCount = useBoolVariation(FLAG_COUNT, false);
  return {
    highlight: interpretHighlight(highlightRaw),
    showCount: Boolean(showCount),
  };
}
