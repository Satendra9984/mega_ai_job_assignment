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

function fmtPx(n: number | null): string {
  return n == null ? "—" : String(n);
}

function fmtConfidence(c: number | null): string {
  return c == null ? "—" : `${(c * 100).toFixed(1)}%`;
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
      dctx.strokeStyle = "#22d3ee";
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
    if (sendTimerRef.current) {
      window.clearInterval(sendTimerRef.current);
      sendTimerRef.current = null;
    }
    wsRef.current?.close();
    wsRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const start = async () => {
    intentionalStopRef.current = false;
    setError(null);
    setInfo(null);
    setHistoryRecords(null);
    setHistoryTotal(null);
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
          else if (msg.type === "roi") setRoi(msg);
          else if (msg.type === "error") setError(`${msg.code}: ${msg.detail}`);
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
        // compose default: host port 3000 -> nginx:80 (see docker-compose.yml)
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

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: "1.5rem" }}>
      <header style={{ marginBottom: "1rem" }}>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: "0.75rem",
            marginBottom: "0.35rem",
          }}
        >
          <h1 style={{ margin: 0, fontWeight: 600 }}>MegaAI — Face ROI Stream</h1>
          <span
            role="status"
            aria-live="polite"
            style={{
              fontSize: "0.8rem",
              padding: "0.2rem 0.55rem",
              borderRadius: 999,
              border: "1px solid #475569",
              background: "#1e293b",
              color: "#e2e8f0",
            }}
          >
            {connectionLabel(connectionStatus)}
          </span>
        </div>
        <p style={{ margin: 0, opacity: 0.85 }}>
          Webcam frames are sent over <code>WS /ws/ingest</code>. The ROI rectangle is
          drawn on the canvas in your browser (not on the server).
        </p>
      </header>

      <div
        style={{
          display: "flex",
          gap: "0.75rem",
          flexWrap: "wrap",
          marginBottom: "1rem",
        }}
      >
        {!running ? (
          <button
            type="button"
            onClick={() => void start()}
            disabled={connectionStatus === "connecting"}
            aria-busy={connectionStatus === "connecting"}
            style={{
              padding: "0.5rem 1rem",
              cursor: connectionStatus === "connecting" ? "wait" : "pointer",
            }}
          >
            Start webcam
          </button>
        ) : (
          <button
            type="button"
            onClick={stop}
            style={{ padding: "0.5rem 1rem", cursor: "pointer" }}
          >
            Stop
          </button>
        )}
        <button
          type="button"
          onClick={() => void fetchHistory()}
          disabled={!sessionId || historyLoading}
          aria-busy={historyLoading}
          style={{
            padding: "0.5rem 1rem",
            cursor:
              sessionId && !historyLoading ? "pointer" : "not-allowed",
          }}
        >
          {historyLoading ? "Loading history…" : "Fetch ROI history (sample)"}
        </button>
      </div>

      {sessionId && (
        <p style={{ fontSize: "0.9rem", opacity: 0.9 }}>
          Session: <code>{sessionId}</code>
          {historyTotal != null && <> · DB records (total): {historyTotal}</>}
        </p>
      )}

      {sessionId && roi && (
        <section
          aria-label="Current ROI"
          style={{
            marginBottom: "1rem",
            padding: "0.75rem 1rem",
            borderRadius: 8,
            border: "1px solid #334155",
            background: "#0f172a",
            fontSize: "0.9rem",
          }}
        >
          <h2 style={{ margin: "0 0 0.5rem", fontSize: "0.95rem", fontWeight: 600 }}>
            Current ROI (live)
          </h2>
          <p style={{ margin: "0.25rem 0" }}>
            Frame <strong>{roi.frame_index}</strong>
            {" · "}
            Face{" "}
            <strong>{roi.face_detected ? "yes" : "no"}</strong>
            {" · "}
            Box (px) x={fmtPx(roi.x)} y={fmtPx(roi.y)} w={fmtPx(roi.w)} h={fmtPx(roi.h)}
            {" · "}
            Confidence <strong>{fmtConfidence(roi.confidence)}</strong>
          </p>
        </section>
      )}

      {historyRecords !== null && (
        <section
          aria-label="ROI history"
          style={{ marginBottom: "1rem", overflowX: "auto" }}
        >
          <h2 style={{ margin: "0 0 0.5rem", fontSize: "0.95rem", fontWeight: 600 }}>
            ROI history (last fetch: {historyRecords.length} row
            {historyRecords.length === 1 ? "" : "s"})
          </h2>
          {historyTotal != null &&
            historyTotal > 0 &&
            historyRecords.length === 0 && (
              <p style={{ fontSize: "0.85rem", opacity: 0.85 }}>
                No rows in this page (try a different offset on the API).
              </p>
            )}
          {historyRecords.length > 0 && (
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: "0.8rem",
                border: "1px solid #334155",
              }}
            >
              <caption
                style={{
                  captionSide: "top",
                  textAlign: "left",
                  fontSize: "0.8rem",
                  paddingBottom: "0.35rem",
                  opacity: 0.9,
                }}
              >
                Persisted ROI rows returned by{" "}
                <code>GET /api/roi</code> (last fetch).
              </caption>
              <thead>
                <tr style={{ background: "#1e293b", textAlign: "left" }}>
                  <th style={{ padding: "0.35rem 0.5rem" }}>Frame</th>
                  <th style={{ padding: "0.35rem 0.5rem" }}>Face</th>
                  <th style={{ padding: "0.35rem 0.5rem" }}>x</th>
                  <th style={{ padding: "0.35rem 0.5rem" }}>y</th>
                  <th style={{ padding: "0.35rem 0.5rem" }}>w</th>
                  <th style={{ padding: "0.35rem 0.5rem" }}>h</th>
                  <th style={{ padding: "0.35rem 0.5rem" }}>Conf.</th>
                  <th style={{ padding: "0.35rem 0.5rem" }}>detected_at</th>
                </tr>
              </thead>
              <tbody>
                {historyRecords.map((rec) => (
                  <tr
                    key={rec.id}
                    style={{ borderTop: "1px solid #334155" }}
                  >
                    <td style={{ padding: "0.35rem 0.5rem" }}>{rec.frame_index}</td>
                    <td style={{ padding: "0.35rem 0.5rem" }}>
                      {rec.face_detected ? "yes" : "no"}
                    </td>
                    <td style={{ padding: "0.35rem 0.5rem" }}>{fmtPx(rec.x)}</td>
                    <td style={{ padding: "0.35rem 0.5rem" }}>{fmtPx(rec.y)}</td>
                    <td style={{ padding: "0.35rem 0.5rem" }}>{fmtPx(rec.w)}</td>
                    <td style={{ padding: "0.35rem 0.5rem" }}>{fmtPx(rec.h)}</td>
                    <td style={{ padding: "0.35rem 0.5rem" }}>
                      {fmtConfidence(rec.confidence)}
                    </td>
                    <td style={{ padding: "0.35rem 0.5rem", whiteSpace: "nowrap" }}>
                      {new Date(rec.detected_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {historyRecords.length === 0 && historyTotal === 0 && (
            <p style={{ fontSize: "0.85rem", opacity: 0.85 }}>
              No persisted ROI rows for this session yet.
            </p>
          )}
        </section>
      )}

      {error && (
        <div
          role="alert"
          style={{
            marginBottom: "1rem",
            padding: "0.75rem 1rem",
            borderRadius: 8,
            border: "1px solid #b91c1c",
            background: "#450a0a",
            color: "#fecaca",
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: "0.75rem",
          }}
        >
          <p style={{ margin: 0, flex: "1 1 12rem" }}>{error}</p>
          <button
            type="button"
            onClick={() => setError(null)}
            style={{
              padding: "0.35rem 0.75rem",
              cursor: "pointer",
              borderRadius: 6,
              border: "1px solid #f87171",
              background: "transparent",
              color: "#fecaca",
            }}
          >
            Dismiss
          </button>
        </div>
      )}
      {info && <p style={{ opacity: 0.75 }}>{info}</p>}

      <div
        style={{
          position: "relative",
          display: "inline-block",
          border: "1px solid #334155",
          borderRadius: 8,
          overflow: "hidden",
          background: "#020617",
        }}
      >
        <video ref={videoRef} playsInline muted style={{ display: "none" }} />
        <canvas
          ref={dispRef}
          style={{ display: "block", maxWidth: "100%", height: "auto" }}
        />
        <canvas ref={capRef} style={{ display: "none" }} />
      </div>

      <footer style={{ marginTop: "1.5rem", fontSize: "0.85rem", opacity: 0.7 }}>
        <p style={{ margin: "0.25rem 0" }}>
          Endpoints: <code>WS /ws/ingest</code>, <code>WS /ws/stream</code>,{" "}
          <code>GET /api/roi</code>
        </p>
      </footer>
    </div>
  );
}
