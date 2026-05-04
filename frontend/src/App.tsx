import { useCallback, useEffect, useRef, useState } from "react";

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

export function App() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const capRef = useRef<HTMLCanvasElement>(null);
  const dispRef = useRef<HTMLCanvasElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const sendTimerRef = useRef<number | null>(null);
  const rafRef = useRef<number | null>(null);

  const [running, setRunning] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [roi, setRoi] = useState<RoiMsg | null>(null);
  const [historyTotal, setHistoryTotal] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

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
    setRunning(false);
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
    setError(null);
    setInfo(null);
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

      ws.onerror = () => setError("WebSocket error");
      ws.onclose = () => setInfo("Disconnected");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const fetchHistory = async () => {
    if (!sessionId) return;
    const r = await fetch(
      `${apiRoot()}/api/roi?session_id=${encodeURIComponent(sessionId)}&limit=5`,
    );
    if (!r.ok) {
      setError(`ROI API ${r.status}`);
      return;
    }
    const data = (await r.json()) as { total: number };
    setHistoryTotal(data.total);
  };

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: "1.5rem" }}>
      <header style={{ marginBottom: "1rem" }}>
        <h1 style={{ margin: "0 0 0.25rem", fontWeight: 600 }}>
          MegaAI — Face ROI Stream
        </h1>
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
            style={{ padding: "0.5rem 1rem", cursor: "pointer" }}
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
          disabled={!sessionId}
          style={{
            padding: "0.5rem 1rem",
            cursor: sessionId ? "pointer" : "not-allowed",
          }}
        >
          Fetch ROI history (sample)
        </button>
      </div>

      {sessionId && (
        <p style={{ fontSize: "0.9rem", opacity: 0.9 }}>
          Session: <code>{sessionId}</code>
          {roi && (
            <>
              {" "}
              · Frame {roi.frame_index}
              {roi.face_detected && roi.confidence != null && (
                <>
                  {" "}
                  · confidence {(roi.confidence * 100).toFixed(1)}%
                </>
              )}
            </>
          )}
          {historyTotal != null && <> · DB records (total): {historyTotal}</>}
        </p>
      )}

      {error && <p style={{ color: "#f87171" }}>{error}</p>}
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
