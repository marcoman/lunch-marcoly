/**
 * 301-client-evaluation React Web SDK session.
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

const WATCHED_FLAGS = [FLAG_HIGHLIGHT, FLAG_COUNT];

function formatChangeDetail(payload) {
  if (payload == null) return "";
  if (Array.isArray(payload)) return payload.join(", ");
  if (typeof payload === "object") return Object.keys(payload).join(", ");
  return String(payload);
}

function changedFlagKeys(changes) {
  if (Array.isArray(changes)) return changes;
  if (changes && typeof changes === "object") return Object.keys(changes);
  return [];
}

/**
 * Variation after a change event. This SDK's callback does not include it.
 * LaunchDarkly: stringVariation / boolVariation
 * https://launchdarkly.com/docs/sdk/features/evaluating-flags
 */
function readWatchedVariation(ldClient, key) {
  if (key === FLAG_COUNT && typeof ldClient.boolVariation === "function") {
    return ldClient.boolVariation(key, false);
  }
  if (key === FLAG_HIGHLIGHT && typeof ldClient.stringVariation === "function") {
    return ldClient.stringVariation(key, "none");
  }
  if (typeof ldClient.variation === "function") return ldClient.variation(key, null);
  return undefined;
}

/**
 * Mounts the React Web SDK only after login, with the real user context.
 * Does not initialize anonymously then identify — that is example 302.
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
  const seenValues = useRef({});

  useEffect(() => {
    if (status !== "complete" || initLogged.current) return;
    initLogged.current = true;
    onSdkEvent("initialize", `key=${username}`);
  }, [status, username, onSdkEvent]);

  /**
   * Streaming flag updates — the variation hooks re-render; this listener is
   * only for the lab SDK call log (not WASD).
   * LaunchDarkly: change events. This SDK passes (context, changed flag keys)
   * and does not include the new variation, so a fallthrough color change
   * would otherwise repeat the same keys. Read the variation after the callback.
   * https://launchdarkly.com/docs/sdk/features/flag-changes
   */
  useEffect(() => {
    if (!ldClient || typeof ldClient.on !== "function") return undefined;
    const onChange = (...args) => {
      const changes = args.length > 1 ? args[1] : args[0];
      const keys = formatChangeDetail(changes);
      const keyList = changedFlagKeys(changes);
      const evaluated = {};
      for (const key of WATCHED_FLAGS) {
        if (!keyList.includes(key)) continue;
        const current = readWatchedVariation(ldClient, key);
        const entry = { current };
        if (Object.prototype.hasOwnProperty.call(seenValues.current, key)) {
          entry.previous = seenValues.current[key];
        }
        seenValues.current[key] = current;
        evaluated[key] = entry;
      }
      const valueNote = Object.entries(evaluated)
        .map(([key, entry]) => {
          const was = Object.prototype.hasOwnProperty.call(entry, "previous")
            ? ` (was ${JSON.stringify(entry.previous)})`
            : "";
          return `${key}=${JSON.stringify(entry.current)}${was}`;
        })
        .join(", ");
      const payload = { callback: args.length === 1 ? args[0] : [args[0], args[1]] };
      if (Object.keys(evaluated).length) payload.evaluated = evaluated;
      onSdkEvent(
        "change",
        [keys ? `flags=${keys}` : "(stream update)", valueNote].filter(Boolean).join("  "),
        payload
      );
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
