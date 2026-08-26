/**
 * 33-synced-segments React Web SDK session.
 * LaunchDarkly: identify + useBoolVariation(show-inner-circle-badge) + change:
 * https://launchdarkly.com/docs/home/flags/synced-segments
 * https://launchdarkly.com/docs/sdk/client-side/react/react-web
 */
import { useEffect, useMemo, useRef } from "react";
import {
  createLDReactProvider,
  useBoolVariation,
  useInitializationStatus,
  useLDClient,
} from "@launchdarkly/react-sdk";

export const FLAG_BADGE = "show-inner-circle-badge";

function formatChangeDetail(payload) {
  if (payload == null) return "";
  if (Array.isArray(payload)) return payload.join(", ");
  if (typeof payload === "object") return Object.keys(payload).join(", ");
  return String(payload);
}

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
  }, [initialKey, onSdkEvent]);

  return children;
}

export function useIdentifyContext() {
  return useLDClient();
}

export function useGridFlags() {
  return { showBadge: Boolean(useBoolVariation(FLAG_BADGE, false)) };
}
