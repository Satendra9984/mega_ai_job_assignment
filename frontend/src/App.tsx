import { useCallback, useEffect, useRef, useState } from "react";

type ConnectionStatus = "idle" | "connecting" | "live" | "disconnected";

type SessionMsg = { type: "session"; session_id: string };
type RoiMsg = {
  type: "roi";
  session_id: string;
  frame_index: number;
  face_detected: boolean;
  x: number | null;
  y: number | null;
  w: number | null;
  h: number | null;
  confidence: number | null;
};
type ErrMsg = { type: "error"; code: string; detail: string };

/** Mirrors backend `ROIRecordRead` / `ROIListResponse` (docs/API.md). */
type ROIRecordRead = {
  id: number;
  frame_index: number;
  detected_at: string;
  face_detected: boolean;
  x: number | null;
  y: number | null;
  w: number | null;
  h: number | null;
  confidence: number | null;
};

type ROIListResponse = {
  session_id: string;
  total: number;
  limit: number;
  offset: number;
  records: ROIRecordRead[];
};

type ConfidenceTier = "high" | "med" | "low";

function fmtPx(n: number | null): string {
  return n == null ? "—" : String(n);
}

function fmtConfidence(c: number | null): string {
  return c == null ? "—" : `${(c * 100).toFixed(1)}%`;
}

function confidenceTier(c: number | null): ConfidenceTier | null {
  if (c == null) return null;
  if (c >= 0.85) return "high";
  if (c >= 0.5) return "med";
  return "low";
}

function confidenceTierLabel(t: ConfidenceTier): string {
  switch (t) {
    case "high":
      return "High";
    case "med":
      return "Med";
    case "low":
      return "Low";
  }
}

/** Human-readable hint for common WebSocket close codes (RFC 6455). */
function wsCloseHint(code: number): string {
  switch (code) {
    case 1000:
      return "Normal closure.";
    case 1001:
      return "Going away (e.g. navigation or server shutdown).";
    case 1006:
      return "Abnormal closure (no close frame — often network drop, proxy reset, or crashed server).";
    case 1011:
      return "Server encountered an exception.";
    default:
      return "";
  }
}

function wsRoot(): string {
  const v = import.meta.env.VITE_WS_BASE;
  if (v) return v.replace(/\/$/, "");
  return `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}`;
}

function apiRoot(): string {
  const v = import.meta.env.VITE_API_BASE;
  if (v) return v.replace(/\/$/, "");
  return `${location.protocol}//${location.host}`;
}

function mediaErrorMessage(err: unknown): string {
  if (!(err instanceof Error)) return String(err);
  const { name, message } = err;
  if (name === "NotAllowedError" || name === "PermissionDeniedError") {
    return "Camera permission denied. Allow the camera for this site and try again.";
  }
  if (name === "NotFoundError" || name === "DevicesNotFoundError") {
    return "No camera found. Connect a webcam and try again.";
  }
  if (name === "NotReadableError" || name === "TrackStartError") {
    return "Camera is in use by another application or cannot be read.";
  }
  if (name === "OverconstrainedError" || name === "ConstraintError") {
    return "Camera does not support the requested settings.";
  }
  return message;
}

function connectionLabel(s: ConnectionStatus): string {
  switch (s) {
    case "idle":
      return "Idle";
    case "connecting":
      return "Connecting…";
    case "live":
      return "Live";
    case "disconnected":
      return "Disconnected";
  }
}

async function roiApiErrorMessage(r: Response): Promise<string> {
  let detail = "";
  try {
    const j = (await r.json()) as {
      detail?: string | Array<{ msg?: string } | string>;
    };
    if (typeof j?.detail === "string") {
      detail = j.detail;
    } else if (Array.isArray(j?.detail)) {
      detail = j.detail
        .map((item) =>
          typeof item === "string" ? item : (item?.msg ?? JSON.stringify(item)),
        )
        .join("; ");
    }
  } catch {
    /* ignore non-JSON body */
  }
  if (r.status === 404) {
    return detail ? `Session not found: ${detail}` : "Session not found (404).";
  }
  if (r.status === 422) {
    return detail ? `Invalid request: ${detail}` : "Invalid request (422).";
  }
  if (r.status >= 500) {
    return detail
      ? `Server error (${r.status}): ${detail}`
      : `Server error (${r.status}). Try again later.`;
  }
  return detail
    ? `ROI API failed (${r.status}): ${detail}`
    : `ROI API failed (${r.status}).`;
}

function LogoMark() {
  return (
    <svg
      className="brand-logo"
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <rect
        x="4"
        y="8"
        width="40"
        height="32"
        rx="4"
        stroke="currentColor"
        strokeWidth="2"
      />
      <ellipse cx="24" cy="22" rx="10" ry="12" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="20" cy="20" r="2" fill="currentColor" />
      <circle cx="28" cy="20" r="2" fill="currentColor" />
      <path
        d="M18 28c2 3 10 3 12 0"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function statusPillClass(connectionStatus: ConnectionStatus): string {
  const base = "status-pill";
  if (connectionStatus === "live") return `${base} status-pill--live`;
  if (connectionStatus === "connecting") return `${base} status-pill--connecting`;
  return base;
}

export function App() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const capRef = useRef<HTMLCanvasElement>(null);
  const dispRef = useRef<HTMLCanvasElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const sendTimerRef = useRef<number | null>(null);
  const rafRef = useRef<number | null>(null);
  const wsOpenedAtRef = useRef<number | null>(null);
  const intentionalStopRef = useRef(false);
  const roiMsgTimesRef = useRef<number[]>([]);

  const [running, setRunning] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [roi, setRoi] = useState<RoiMsg | null>(null);
  const [historyTotal, setHistoryTotal] = useState<number | null>(null);
  const [historyRecords, setHistoryRecords] = useState<ROIRecordRead[] | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("idle");
  const [effectiveFps, setEffectiveFps] = useState<number | null>(null);

  const recordRoiMessageForFps = useCallback(() => {
    const now = performance.now();
    const arr = roiMsgTimesRef.current;
    arr.push(now);
    const maxPoints = 11;
    if (arr.length > maxPoints) arr.splice(0, arr.length - maxPoints);
    if (arr.length < 2) {
      setEffectiveFps(null);
      return;
    }
    const deltas: number[] = [];
    for (let i = 1; i < arr.length; i++) deltas.push(arr[i] - arr[i - 1]!);
    const mean = deltas.reduce((a, b) => a + b, 0) / deltas.length;
    if (mean <= 0) return;
    setEffectiveFps(1000 / mean);
  }, []);

  const resetFps = useCallback(() => {
    roiMsgTimesRef.current = [];
    setEffectiveFps(null);
  }, []);

  const drawLoop = useCallback(() => {
    const video = videoRef.current;
    const cap = capRef.current;
    const disp = dispRef.current;
    if (!video || !cap || !disp) {
      rafRef.current = requestAnimationFrame(drawLoop);
      return;
    }
    if (video.readyState < 2) {
      rafRef.current = requestAnimationFrame(drawLoop);
      return;
    }
    const w = video.videoWidth;
    const h = video.videoHeight;
    if (w === 0 || h === 0) {
      rafRef.current = requestAnimationFrame(drawLoop);
      return;
    }
    cap.width = w;
    cap.height = h;
    disp.width = w;
    disp.height = h;
    const cctx = cap.getContext("2d");
    const dctx = disp.getContext("2d");
    if (!cctx || !dctx) {
      rafRef.current = requestAnimationFrame(drawLoop);
      return;
    }
    cctx.drawImage(video, 0, 0, w, h);
    dctx.drawImage(video, 0, 0, w, h);
    if (
      roi &&
      roi.face_detected &&
      roi.x != null &&
      roi.y != null &&
      roi.w != null &&
      roi.h != null
    ) {
      dctx.strokeStyle = "#4fd1ed";
      dctx.lineWidth = Math.max(2, Math.round(w / 200));
      dctx.strokeRect(roi.x, roi.y, roi.w, roi.h);
    }
    rafRef.current = requestAnimationFrame(drawLoop);
  }, [roi]);

  useEffect(() => {
    rafRef.current = requestAnimationFrame(drawLoop);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [drawLoop]);

  const stop = useCallback(() => {
    intentionalStopRef.current = true;
    setRunning(false);
    setConnectionStatus("idle");
    setHistoryRecords(null);
    setHistoryTotal(null);
    setRoi(null);
    resetFps();
    if (sendTimerRef.current) {
      window.clearInterval(sendTimerRef.current);
      sendTimerRef.current = null;
    }
    wsRef.current?.close();
    wsRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, [resetFps]);

  const start = async () => {
    intentionalStopRef.current = false;
    setError(null);
    setInfo(null);
    setHistoryRecords(null);
    setHistoryTotal(null);
    setRoi(null);
    resetFps();
    setConnectionStatus("connecting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: false,
      });
      streamRef.current = stream;
      const video = videoRef.current;
      if (video) {
        video.srcObject = stream;
        await video.play();
      }

      const ws = new WebSocket(`${wsRoot()}/ws/ingest`);
      ws.binaryType = "arraybuffer";
      wsRef.current = ws;

      ws.onmessage = (ev) => {
        if (typeof ev.data !== "string") return;
        try {
          const msg = JSON.parse(ev.data) as SessionMsg | RoiMsg | ErrMsg;
          if (msg.type === "session") setSessionId(msg.session_id);
          else if (msg.type === "roi") {
            setRoi(msg);
            recordRoiMessageForFps();
          } else if (msg.type === "error") setError(`${msg.code}: ${msg.detail}`);
        } catch {
          /* ignore malformed */
        }
      };

      ws.onopen = () => {
        wsOpenedAtRef.current = performance.now();
        setConnectionStatus("live");
        setRunning(true);
        sendTimerRef.current = window.setInterval(() => {
          const cap = capRef.current;
          const socket = wsRef.current;
          if (!cap || !socket || socket.readyState !== WebSocket.OPEN) return;
          cap.toBlob(
            (blob) => {
              if (!blob) return;
              const s = wsRef.current;
              if (!s || s.readyState !== WebSocket.OPEN) return;
              void blob.arrayBuffer().then((buf) => s.send(buf));
            },
            "image/jpeg",
            0.72,
          );
        }, 120);
      };

      ws.onerror = () => {
        const dockerNginxUi = location.port === "3000";
        const hint = dockerNginxUi
          ? " Port 3000 uses nginx inside Docker, which proxies to the backend *container* (service name `backend`), not to uvicorn on your host. Run `docker compose up` (including backend), or use `npm run dev` at http://localhost:5173 with local uvicorn on :8000."
          : "";
        setError(`WebSocket error (see close details below).${hint}`);
      };
      ws.onclose = (ev: CloseEvent) => {
        if (sendTimerRef.current) {
          window.clearInterval(sendTimerRef.current);
          sendTimerRef.current = null;
        }
        setRunning(false);
        resetFps();
        if (intentionalStopRef.current) {
          intentionalStopRef.current = false;
          setConnectionStatus("idle");
        } else {
          setConnectionStatus("disconnected");
        }
        const ms =
          wsOpenedAtRef.current != null
            ? Math.round(performance.now() - wsOpenedAtRef.current)
            : null;
        const hint = wsCloseHint(ev.code);
        const reason = ev.reason?.trim() ? ev.reason : "(no reason text)";
        const line = `Disconnected: code ${ev.code}, clean=${ev.wasClean}, reason: ${reason}${hint ? ` — ${hint}` : ""}${ms != null ? ` · session ~${ms} ms` : ""}`;
        setInfo(line);
        wsOpenedAtRef.current = null;
        wsRef.current = null;
      };
    } catch (e) {
      setConnectionStatus("idle");
      setError(mediaErrorMessage(e));
    }
  };

  const fetchHistory = async () => {
    if (!sessionId || historyLoading) return;
    setHistoryLoading(true);
    try {
      const r = await fetch(
        `${apiRoot()}/api/roi?session_id=${encodeURIComponent(sessionId)}&limit=5`,
      );
      if (!r.ok) {
        setError(await roiApiErrorMessage(r));
        return;
      }
      const data = (await r.json()) as ROIListResponse;
      if (
        typeof data.total !== "number" ||
        !Array.isArray(data.records)
      ) {
        setError("ROI API returned an unexpected response shape.");
        return;
      }
      setHistoryTotal(data.total);
      setHistoryRecords(data.records);
    } catch (e) {
      setError(
        e instanceof Error
          ? `Network error while fetching ROI history: ${e.message}`
          : "Network error while fetching ROI history.",
      );
    } finally {
      setHistoryLoading(false);
    }
  };

  const showLiveChrome = connectionStatus === "live" && running;
  const tier = confidenceTier(roi?.confidence ?? null);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-row">
          <LogoMark />
          <div className="brand-text">
            <h1 className="app-title">MegaAI Face ROI</h1>
            <p className="app-subtitle">
              Real-time face region detection and tracking
            </p>
          </div>
          <div className="header-meta">
            <span
              className={statusPillClass(connectionStatus)}
              role="status"
              aria-live="polite"
            >
              <span className="status-pill__dot" aria-hidden />
              {connectionLabel(connectionStatus)}
            </span>
          </div>
        </div>
        <p className="lead">
          Detects and tracks the primary face region on each frame. Webcam frames
          are sent over <code>WS /ws/ingest</code>; the ROI rectangle is drawn on
          the canvas in your browser (not on the server).
        </p>
      </header>

      <div className="toolbar" aria-label="Stream controls">
        {!running ? (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => void start()}
            disabled={connectionStatus === "connecting"}
            aria-busy={connectionStatus === "connecting"}
          >
            Start webcam
          </button>
        ) : (
          <button type="button" className="btn btn-secondary" onClick={stop}>
            Stop
          </button>
        )}
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => void fetchHistory()}
          disabled={!sessionId || historyLoading}
          aria-busy={historyLoading}
        >
          {historyLoading ? "Loading history…" : "Fetch ROI history (sample)"}
        </button>
      </div>

      {sessionId && (
        <p className="session-line">
          Session: <code>{sessionId}</code>
          {historyTotal != null && <> · DB records (total): {historyTotal}</>}
        </p>
      )}

      <section id="live" aria-label="Live video stream">
        <div className="video-card">
          <div className="video-stage">
            {showLiveChrome && (
              <div className="badge-live-corner" aria-hidden>
                <span className="badge-live-corner__dot" />
                LIVE
              </div>
            )}
            <div className="fps-readout">
              FPS{" "}
              <span>
                {effectiveFps == null
                  ? "—"
                  : effectiveFps >= 100
                    ? effectiveFps.toFixed(0)
                    : effectiveFps.toFixed(1)}
              </span>
            </div>
            <video ref={videoRef} playsInline muted className="canvas-hidden" />
            <canvas ref={dispRef} />
            <canvas ref={capRef} className="canvas-hidden" />
          </div>
        </div>
      </section>

      {sessionId && roi && (
        <section
          className="roi-live-card"
          role="region"
          aria-label="Current ROI"
        >
          <div className="roi-live-card__head">
            <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden>
              <path
                fill="currentColor"
                d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5S10.62 6.5 12 6.5s2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"
              />
            </svg>
            <h2 className="roi-live-card__title">Current ROI (live)</h2>
          </div>
          <div className="stat-grid">
            <div>
              <span className="stat-cell__label">Frame index</span>
              <div className="stat-cell__value">{roi.frame_index}</div>
            </div>
            <div>
              <span className="stat-cell__label">Confidence</span>
              <div className="stat-cell__row">
                <span className="stat-cell__value">{fmtConfidence(roi.confidence)}</span>
                {tier && (
                  <span className={`confidence-pill confidence-pill--${tier}`}>
                    {confidenceTierLabel(tier)}
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className="roi-meta-row">
            Box (px): x=<strong>{fmtPx(roi.x)}</strong> y=
            <strong>{fmtPx(roi.y)}</strong> w=<strong>{fmtPx(roi.w)}</strong> h=
            <strong>{fmtPx(roi.h)}</strong>
            {" · "}
            Face <strong>{roi.face_detected ? "yes" : "no"}</strong>
          </div>
        </section>
      )}

      <section
        id="history"
        className="history-section"
        role="region"
        aria-label="ROI history"
      >
        <h2 className="history-section__title">ROI history</h2>
        <p className="history-section__desc">
          Persisted ROI rows from <code>GET /api/roi</code> for the current
          session (sample: last 5).
        </p>

        {historyRecords === null && (
          <p className="history-empty">
            Use &quot;Fetch ROI history (sample)&quot; after a session is active to
            load rows.
          </p>
        )}

        {historyRecords !== null && historyTotal != null && historyTotal > 0 && historyRecords.length === 0 && (
          <p className="history-empty">
            No rows in this page (try a different offset on the API).
          </p>
        )}

        {historyRecords !== null && historyRecords.length > 0 && (
          <div className="data-table-wrap">
            <table className="data-table">
              <caption>
                Persisted ROI rows returned by <code>GET /api/roi</code> (last
                fetch).
              </caption>
              <thead>
                <tr>
                  <th scope="col">Frame</th>
                  <th scope="col">Face</th>
                  <th scope="col">x</th>
                  <th scope="col">y</th>
                  <th scope="col">w</th>
                  <th scope="col">h</th>
                  <th scope="col">Conf.</th>
                  <th scope="col">detected_at</th>
                </tr>
              </thead>
              <tbody>
                {historyRecords.map((rec) => (
                  <tr key={rec.id}>
                    <td>{rec.frame_index}</td>
                    <td>{rec.face_detected ? "yes" : "no"}</td>
                    <td>{fmtPx(rec.x)}</td>
                    <td>{fmtPx(rec.y)}</td>
                    <td>{fmtPx(rec.w)}</td>
                    <td>{fmtPx(rec.h)}</td>
                    <td>{fmtConfidence(rec.confidence)}</td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {new Date(rec.detected_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {historyRecords !== null && historyRecords.length === 0 && historyTotal === 0 && (
          <p className="history-empty">
            No persisted ROI rows for this session yet.
          </p>
        )}

        <div className="info-callout">
          <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden>
            <path
              fill="currentColor"
              d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"
            />
          </svg>
          <p style={{ margin: 0 }}>
            Coordinates (x, y, w, h) are in pixels relative to the original frame
            resolution.
          </p>
        </div>
      </section>

      {error && (
        <div className="alert-error" role="alert">
          <p>{error}</p>
          <button
            type="button"
            className="btn btn-ghost-danger"
            onClick={() => setError(null)}
          >
            Dismiss
          </button>
        </div>
      )}
      {info && <p className="disconnect-info">{info}</p>}

      <footer className="app-footer">
        <p>
          Endpoints: <code>WS /ws/ingest</code>, <code>WS /ws/stream</code>,{" "}
          <code>GET /api/roi</code>
        </p>
      </footer>
    </div>
  );
}
