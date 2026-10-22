/**
 * 305-client-bootstrap Vue SDK helpers.
 * LaunchDarkly: useLDFlag (string + boolean), streaming change:
 * https://launchdarkly.com/docs/sdk/client-side/vue
 */

// LaunchDarkly: flag key=enable-client-bootstrap-highlight
// https://app.launchdarkly.com/projects/lunch-marcoly/features/enable-client-bootstrap-highlight

export const FLAG_HIGHLIGHT = "enable-client-bootstrap-highlight";
// LaunchDarkly: flag key=show-client-bootstrap-move-count
// https://app.launchdarkly.com/projects/lunch-marcoly/features/show-client-bootstrap-move-count

export const FLAG_COUNT = "show-client-bootstrap-move-count";

/**
 * First-paint values. The grid keeps these through the lab startup delay.
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
export const STARTUP_DELAY_SEC = 8;

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

export function playStartupTone(kind) {
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

export function formatChangeDetail(payload) {
  if (payload == null) return "";
  if (Array.isArray(payload)) return payload.join(", ");
  if (typeof payload === "object") return Object.keys(payload).join(", ");
  return String(payload);
}
