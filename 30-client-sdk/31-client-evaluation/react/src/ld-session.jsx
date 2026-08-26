/**
 * 31-client-evaluation React Web SDK session.
 * LaunchDarkly: createLDReactProvider, useStringVariation, useBoolVariation, change:
 * https://launchdarkly.com/docs/sdk/client-side/react/react-web
 */
import { useEffect, useMemo, useRef } from "react";
import {
  createLDReactProvider,
  useBoolVariation,
  useInitializationStatus,
  useLDClient,
  useStringVariation,
} from "@launchdarkly/react-sdk";

export const FLAG_HIGHLIGHT = "enable-client-grid-highlight";
export const FLAG_COUNT = "show-client-move-count";

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
  const initLogged = useRef(false);

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
