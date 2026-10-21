import { useCallback, useEffect, useRef, useState } from "react";
import { LdSession, useGridFlags, useIdentifyContext } from "./ld-session.jsx";

const ROWS = ["t", "m", "b"];
const COLS = ["l", "m", "r"];
const BANNER = "32-client-identify[react]";

function formatPos(r, c) {
  return `${ROWS[r]}/${COLS[c]}`;
}

function App() {
  const [clientSideId, setClientSideId] = useState(null);
  const [authKey, setAuthKey] = useState("");
  const [username, setUsername] = useState("");
  const [loginValue, setLoginValue] = useState("");
  const [loginError, setLoginError] = useState(false);
  const [closed, setClosed] = useState(false);
  const [nav, setNav] = useState({ row: 1, col: 1, previous: null, moveCount: 0 });
  const [sdkCallLog, setSdkCallLog] = useState([]);
  const [initializeCount, setInitializeCount] = useState(0);
  const [identifyCount, setIdentifyCount] = useState(0);
  const [controls, setControls] = useState(null);
  const [controlsWarn, setControlsWarn] = useState("");
  const logRef = useRef(null);

  const onSdkEvent = useCallback((kind, detail) => {
    const line = { t: new Date().toISOString().slice(11, 23), kind, detail };
    console.log(`[32 identify][react] ${kind}${detail ? " " + detail : ""}`);
    setSdkCallLog((prev) => {
      const next = [...prev, line];
      return next.length > 40 ? next.slice(-40) : next;
    });
    if (kind === "initialize") setInitializeCount((n) => n + 1);
    if (kind === "identify") setIdentifyCount((n) => n + 1);
  }, []);

  useEffect(() => {
    fetch("/api/config", { cache: "no-store" })
      .then((res) => res.json())
      .then((cfg) => {
        setClientSideId(cfg.clientSideId);
        refreshControls();
      })
      .catch(() => setClientSideId(null));
  }, []);

  useEffect(() => {
    document.body.classList.toggle("grid-active", Boolean(authKey) && !closed);
  }, [authKey, closed]);

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [sdkCallLog]);

  async function refreshControls() {
    try {
      const res = await fetch("/api/flag-controls", { cache: "no-store" });
      const data = await res.json();
      setControls(data);
      if (!data.configured) {
        setControlsWarn(
          "Controls need " + (data.missing || []).join(", ") + " on the Vite host (not in the page)."
        );
      } else {
        setControlsWarn("");
      }
    } catch (err) {
      setControlsWarn(String(err.message || err));
    }
  }

  async function postControl(key, body) {
    const res = await fetch("/api/flag-controls", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key, ...body }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || res.statusText);
    await refreshControls();
  }

  function tryMove(dr, dc) {
    setNav((cur) => {
      const nr = Math.max(0, Math.min(2, cur.row + dr));
      const nc = Math.max(0, Math.min(2, cur.col + dc));
      if (nr === cur.row && nc === cur.col) return cur;
      return {
        row: nr,
        col: nc,
        previous: { row: cur.row, col: cur.col },
        moveCount: cur.moveCount + 1,
      };
    });
  }

  function handleGridKey(e) {
    const key = e.key.toLowerCase();
    if (key === "q") {
      e.preventDefault();
      quit();
      return;
    }
    if (key === "l") {
      e.preventDefault();
      logout();
      return;
    }
    if (e.key === "ArrowUp" || key === "w") tryMove(-1, 0);
    else if (e.key === "ArrowDown" || key === "s") tryMove(1, 0);
    else if (e.key === "ArrowLeft" || key === "a") tryMove(0, -1);
    else if (e.key === "ArrowRight" || key === "d") tryMove(0, 1);
    else return;
    e.preventDefault();
  }

  function startGrid(name) {
    setAuthKey(name);
    setUsername(name);
    setNav({ row: 1, col: 1, previous: null, moveCount: 0 });
    if (!clientSideId) {
      onSdkEvent("skip", "no client-side ID — did not initialize the React Web SDK");
    }
  }

  function logout() {
    onSdkEvent("session", "logged out — next login will initialize again (count kept)");
    setAuthKey("");
    setUsername("");
    setNav({ row: 1, col: 1, previous: null, moveCount: 0 });
    setLoginValue("");
    setLoginError(false);
    document.body.classList.remove("highlight-on");
  }

  function quit() {
    window.close();
    setClosed(true);
  }

  if (closed) {
    return <p>Application closed. You may close this tab.</p>;
  }

  const loggedIn = Boolean(authKey);
  const shellProps = {
    username,
    onContextKey: setUsername,
    onSdkEvent,
    row: nav.row,
    col: nav.col,
    previous: nav.previous,
    moveCount: nav.moveCount,
    onKeyDown: handleGridKey,
    clientSideId,
    sdkCallLog,
    initializeCount,
    identifyCount,
    logRef,
    controls,
    controlsWarn,
    onRefresh: refreshControls,
    onPostControl: postControl,
  };

  const shell = loggedIn ? (
    clientSideId ? (
      <LdSession clientSideId={clientSideId} initialKey={authKey} onSdkEvent={onSdkEvent}>
        <FlaggedShell {...shellProps} />
      </LdSession>
    ) : (
      <LoggedInUI {...shellProps} highlight="none" showCount={false} ldClient={null} />
    )
  ) : null;

  return (
    <>
      {!loggedIn && (
        <LoginScreen
          loginValue={loginValue}
          loginError={loginError}
          setLoginValue={setLoginValue}
          onContinue={() => {
            const name = loginValue.trim();
            if (!name) {
              setLoginError(true);
              return;
            }
            setLoginError(false);
            startGrid(name);
          }}
        />
      )}
      {shell}
    </>
  );
}

function LoginScreen({ loginValue, loginError, setLoginValue, onContinue }) {
  return (
    <section id="login-screen">
      <div className="app-banner">{BANNER}</div>
      <h1>Login</h1>
      <label htmlFor="username">Username</label>
      <input
        id="username"
        type="text"
        autoComplete="username"
        autoFocus
        value={loginValue}
        onChange={(e) => setLoginValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") onContinue();
        }}
      />
      <p className={loginError ? "error" : "error hidden"}>Username is required.</p>
      <button id="login-btn" type="button" onClick={onContinue}>
        Continue
      </button>
    </section>
  );
}

function FlaggedShell(props) {
  const { highlight, showCount } = useGridFlags();
  const ldClient = useIdentifyContext();
  return <LoggedInUI {...props} highlight={highlight} showCount={showCount} ldClient={ldClient} />;
}

function LoggedInUI({
  username,
  onContextKey,
  onSdkEvent,
  highlight,
  showCount,
  ldClient,
  row,
  col,
  previous,
  moveCount,
  onKeyDown,
  clientSideId,
  sdkCallLog,
  initializeCount,
  identifyCount,
  logRef,
  controls,
  controlsWarn,
  onRefresh,
  onPostControl,
}) {
  const gridRef = useRef(null);
  const [switchName, setSwitchName] = useState(username);
  const [identifyBusy, setIdentifyBusy] = useState(false);

  useEffect(() => {
    document.body.classList.toggle("highlight-on", highlight !== "none");
    gridRef.current?.focus();
  }, [highlight]);

  useEffect(() => {
    setSwitchName(username);
  }, [username]);

  async function identifyUser(name) {
    const next = (name || "").trim();
    if (!next || identifyBusy) return;
    if (!ldClient || typeof ldClient.identify !== "function") {
      onContextKey(next);
      return;
    }
    setIdentifyBusy(true);
    try {
      onSdkEvent("identify", `key=${next}  (no initialize)`);
      await ldClient.identify({ kind: "user", key: next });
      onContextKey(next);
      gridRef.current?.focus();
    } finally {
      setIdentifyBusy(false);
    }
  }

  return (
    <div id="app-shell">
      <section id="grid-screen" tabIndex={0} ref={gridRef} onKeyDown={onKeyDown}>
        <div className="header">
          <div className="app-banner">{BANNER}</div>
          <div>
            Name:{" "}
            <span className={highlight !== "none" ? `color-${highlight}` : ""}>{username}</span>
          </div>
          <div>Current position: {formatPos(row, col)}</div>
          <div>Previous position: {previous ? formatPos(previous.row, previous.col) : "—"}</div>
          {showCount ? <div>Count: {moveCount}</div> : null}
        </div>
        <div className="grid" aria-label="3 by 3 grid">
          {Array.from({ length: 9 }, (_, i) => {
            const r = Math.floor(i / 3);
            const c = i % 3;
            const selected = r === row && c === col;
            const cls = ["cell"];
            if (selected) {
              cls.push("selected");
              if (highlight !== "none") cls.push(`highlight-${highlight}`);
            }
            return (
              <div key={i} className={cls.join(" ")}>
                {selected ? "X" : ""}
              </div>
            );
          })}
        </div>
        <p className="hint">
          Use arrow keys or WASD to move. Press L to log out, Q to quit. Switch user in the lab rail
          (identify — no reload).
        </p>
      </section>
      <aside className="ld-rail" aria-label="LaunchDarkly lab">
        <h2>LaunchDarkly · lab</h2>
        <div style={{ fontWeight: 650 }}>Identify</div>
        <p className="ld-about-p" style={{ marginTop: "0.35rem" }}>
          Same SDK client. <code>{'identify({ kind: "user", key })'}</code> changes targeting
          without reload. Grid position and Count persist.
        </p>
        <div className="identify-row">
          <input
            type="text"
            autoComplete="username"
            aria-label="Context key"
            value={switchName}
            onChange={(e) => setSwitchName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                identifyUser(switchName);
              }
            }}
          />
          <button type="button" onClick={() => identifyUser(switchName)}>
            Identify
          </button>
          <button type="button" onClick={() => identifyUser("alice")}>
            Alice
          </button>
          <button type="button" onClick={() => identifyUser("bob")}>
            Bob
          </button>
        </div>
        <div style={{ fontWeight: 650 }}>SDK calls</div>
        <p className="sdk-call-counts">
          initialize ×{initializeCount} · identify ×{identifyCount}
        </p>
        <SdkLog sdkCallLog={sdkCallLog} logRef={logRef} />
        <p className="ld-controls-meta">
          {clientSideId
            ? `Client-side ID loaded (${clientSideId.slice(0, 6)}…). Highlight=${highlight} count=${showCount}.`
            : "No LD_CLIENT_SIDE_ID — using code defaults (none / hidden)."}
        </p>
        <p className="ld-controls-meta">
          {controls?.projectKey
            ? `Project ${controls.projectKey} · env ${controls.environmentKey}`
            : "REST controls unavailable."}
        </p>
        {controlsWarn ? <div className="ld-controls-warn">{controlsWarn}</div> : null}
        <div className="ld-toolbar">
          <button type="button" onClick={() => onRefresh().catch(() => {})}>
            Refresh status
          </button>
        </div>
        <FlagCards flags={controls?.flags} onPostControl={onPostControl} />
        <p className="ld-about-p">
          This example teaches <strong>identify</strong>, not a second <code>initialize</code>. Keys:{" "}
          <code>alice</code> (green + count), <code>bob</code> (blue, no count), anything else (none).
          Docs:{" "}
          <a href="https://launchdarkly.com/docs/sdk/features/identify">identify</a>
          {" · "}
          <a href="https://launchdarkly.com/docs/sdk/client-side/react/react-web">React Web</a>.
        </p>
        <div style={{ marginTop: "1rem", fontWeight: 650 }}>Context</div>
        <pre className="context-pre">
          {username
            ? JSON.stringify({ kind: "user", key: username }, null, 2)
            : "Log in to set the evaluation context."}
        </pre>
      </aside>
    </div>
  );
}

function SdkLog({ sdkCallLog, logRef }) {
  return (
    <div className="sdk-log" ref={logRef} aria-live="polite">
      {!sdkCallLog.length
        ? "No SDK client calls yet."
        : sdkCallLog.map((entry, i) => (
            <div key={i} className={"sdk-log-line kind-" + entry.kind}>
              {entry.t} {entry.kind === "change" ? "change:" : entry.kind}
              {entry.detail ? `  ${entry.detail}` : ""}
            </div>
          ))}
    </div>
  );
}

function FlagCards({ flags, onPostControl }) {
  return (
    <div>
      {(flags || []).map((f) => {
        const onLabel = f.on === true ? "On" : f.on === false ? "Off" : "?";
        return (
          <div key={f.key} className="flag-card">
            <div className="flag-card-top">
              <div>
                <h3>{f.label}</h3>
                <div className="flag-key">{f.key}</div>
                <p className="flag-summary">{f.summary || ""}</p>
                <p className="flag-hint">{f.targetingHint || ""}</p>
              </div>
              <button
                type="button"
                className={"flag-toggle " + (f.on ? "on" : "off")}
                onClick={() => onPostControl(f.key, { on: !f.on })}
              >
                {onLabel}
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default App;
