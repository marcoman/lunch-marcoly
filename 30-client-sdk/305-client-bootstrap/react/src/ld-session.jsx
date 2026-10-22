/**
 * 305-client-bootstrap React Web SDK session.
 * LaunchDarkly: createLDReactProvider bootstrap, useStringVariation, useBoolVariation
 * https://launchdarkly.com/docs/sdk/features/bootstrapping#javascript
 */
import { useEffect, useMemo, useRef, useState } from "react";
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

/**
 * Hold the bootstrap paint after login so the handoff is visible.
 * The client still initializes immediately. This is a lab delay, not an SDK option.
 */
const STARTUP_DELAY_SEC = 8;

/**
 * Countdown cue. Same oscillator shape as 107-scheduled-changes:
 * 440 Hz on each second, 880 Hz when the live flags apply.
 * The login click unlocks audio; later ticks play from the timer.
 */
let audioContext = null;

export function unlockStartupAudio() {
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!Ctx) return null;
  audioContext = audioContext || new Ctx();
  if (audioContext.state === "suspended") audioContext.resume().catch(() => {});
  return audioContext;
}

function playStartupTone(kind) {
  const context = unlockStartupAudio();
  if (!context) return;
  const finish = kind === "finish";
  const frequency = finish ? 880 : 440;
  const duration = finish ? 0.32 : 0.16;
  const oscillator = context.createOscillator();
  const gain = context.createGain();
  const now = context.currentTime;
  oscillator.type = "sine";
  oscillator.frequency.setValueAtTime(frequency, now);
  gain.gain.setValueAtTime(0.0001, now);
  gain.gain.exponentialRampToValueAtTime(0.08, now + 0.015);
  gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);
  oscillator.connect(gain);
  gain.connect(context.destination);
  oscillator.start(now);
  oscillator.stop(now + duration + 0.02);
}

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
 * Does not initialize anonymously then identify — that is example 302.
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
 * The grid shows the bootstrap map through a lab countdown, then the live values.
 * LaunchDarkly: bootstrap, then variation
 * https://launchdarkly.com/docs/sdk/features/bootstrapping#javascript
 */
export function usePaintReport() {
  const init = useInitializationStatus();
  const status = typeof init === "string" ? init : init && init.status;
  const live = useGridFlags();
  const sdkReady = status === "complete" || status === "failed" || status === "timeout";
  const [secondsLeft, setSecondsLeft] = useState(STARTUP_DELAY_SEC);
  const [holding, setHolding] = useState(true);
  const first = useRef({
    highlight: BOOTSTRAP[FLAG_HIGHLIGHT],
    showCount: BOOTSTRAP[FLAG_COUNT],
  });

  useEffect(() => {
    playStartupTone(secondsLeft === 0 ? "finish" : "tick");
  }, [secondsLeft]);

  useEffect(() => {
    const id = setInterval(() => {
      setSecondsLeft((left) => {
        if (left <= 1) {
          clearInterval(id);
          setHolding(false);
          return 0;
        }
        return left - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, []);

  const showBootstrap = holding || !sdkReady;
  return {
    source: showBootstrap ? "bootstrap" : "stream",
    holding,
    secondsLeft,
    first: first.current,
    highlight: showBootstrap ? first.current.highlight : live.highlight,
    showCount: showBootstrap ? first.current.showCount : live.showCount,
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
