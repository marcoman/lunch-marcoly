/**
 * 32-client-identify React Web SDK session.
 * LaunchDarkly: createLDReactProvider once, then identify() — not a second initialize
 * https://launchdarkly.com/docs/sdk/features/identify
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

export const FLAG_HIGHLIGHT = "enable-identify-grid-highlight";
export const FLAG_COUNT = "show-identify-move-count";

const COLORS = new Set(["green", "yellow", "red", "blue", "purple"]);

export function interpretHighlight(raw) {
  if (typeof raw === "string" && COLORS.has(raw.trim().toLowerCase())) {
    return raw.trim().toLowerCase();
  }
  return "none";
}

/**
 * Provider is keyed by login session (initialKey), not the current identify key.
 * Changing initialKey remounts the client (logout / new login).
 */
export function LdSession({ clientSideId, initialKey, onSdkEvent, children }) {
  const Provider = useMemo(
    () =>
      createLDReactProvider(clientSideId, { kind: "user", key: initialKey }, {
        ldOptions: { streaming: true },
      }),
    [clientSideId, initialKey]
  );
  return (
    <Provider>
      <LdBridge initialKey={initialKey} onSdkEvent={onSdkEvent}>
        {children}
      </LdBridge>
    </Provider>
  );
}

function LdBridge({ initialKey, onSdkEvent, children }) {
  const { status } = useInitializationStatus();
  const ldClient = useLDClient();
  const initLogged = useRef(false);

  useEffect(() => {
    if (status !== "complete" || initLogged.current) return;
    initLogged.current = true;
    onSdkEvent("initialize", `key=${initialKey}`);
  }, [status, initialKey, onSdkEvent]);

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
  }, [initialKey, onSdkEvent]);

  return children;
}

/**
 * Switch context on the existing client.
 * LaunchDarkly: identify
 */
export function useIdentifyContext() {
  return useLDClient();
}

export function useGridFlags() {
  const highlightRaw = useStringVariation(FLAG_HIGHLIGHT, "none");
  const showCount = useBoolVariation(FLAG_COUNT, false);
  return {
    highlight: interpretHighlight(highlightRaw),
    showCount: Boolean(showCount),
  };
}
