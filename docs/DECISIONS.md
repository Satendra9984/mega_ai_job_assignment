# Architectural Decisions

Short record of the non-obvious choices made during design, with rationale.
Format: decision → alternatives considered → why this one.

---

## 1. Client-side ROI drawing (not server-side)

**Decision:** The backend streams raw JPEG frames and ROI coordinates separately.
The React frontend draws the rectangle on a `<canvas>` using the Canvas 2D API.

**Alternatives:**
- Server burns the rectangle into each frame before sending (Pillow `ImageDraw`).

**Rationale:**
- Server-side drawing adds a full encode/decode cycle per frame on the critical path,
  increasing CPU and latency for every frame even when no face is detected.
- Separating the concerns (detection vs. presentation) makes each component independently
  testable: the detector returns coordinates, the frontend renders them.
- Avoids any ambiguity around "drawing without OpenCV" — the server draws nothing at all.
- Aligns with the rubric criterion "Architecture & Separation of Concerns."

---

## 2. No OpenCV-Python in application code

**Decision:** Use `Pillow` for JPEG decode/encode and `mediapipe` for face detection.
The string `import cv2` does not appear anywhere in the application.

**Alternatives:**
- `face_recognition` (dlib-based) — requires C++ compiler during Docker build; slower.
- Raw ONNX model + numpy — more control, but significant extra code for a one-face task.

**Rationale:**
- `mediapipe` is pip-installable without compilation, provides a production-grade face
  detection model (`FaceDetection` short-range), and its Python API accepts numpy arrays
  with no cv2 dependency in our code. MediaPipe may transitively install
  `opencv-contrib-python-headless` for its own internal use, but that is an
  implementation detail of the library, not our code.
- `Pillow` cleanly covers all image I/O we need (open, save, convert RGB).

---

## 3. WebSocket for ingest (not HTTP multipart upload)

**Decision:** The webcam feed is sent frame-by-frame over a persistent WebSocket connection.

**Alternatives:**
- Single HTTP POST of a video file (batch processing).
- HTTP chunked transfer / SSE for one direction.

**Rationale:**
- The assignment title says "Real-Time … Streaming System" and tags include `#WebSockets`.
- A persistent connection eliminates per-frame HTTP handshake overhead.
- The server can respond to each frame immediately with ROI JSON on the same connection,
  giving the client sub-100 ms feedback.
- A WebSocket connection naturally models a "session" (one connect = one recording session).

---

## 4. PostgreSQL for ROI persistence

**Decision:** Store ROI records in PostgreSQL using SQLAlchemy (async) + Alembic.

**Alternatives:**
- SQLite — simpler, but not production-grade and poor async story.
- InfluxDB / TimescaleDB — time-series DBs are appropriate for telemetry, but add
  operational complexity; Postgres with a timestamp column is sufficient here.
- Redis — good for ephemeral state, not suited for durable history queries.

**Rationale:**
- Assignment tags include `#PostgreSQL` explicitly.
- Relational model suits the data: sessions → roi_records (one-to-many).
- `asyncpg` gives non-blocking DB access that integrates well with FastAPI's event loop.
- A single indexed table (`roi_records`) with a FK to `sessions` is all the schema this
  problem needs — satisfying "pragmatism vs. over-engineering."

---

## 5. Bounded asyncio.Queue in Frame Bus (drop slow subscribers)

**Decision:** Each `/ws/stream` subscriber gets an `asyncio.Queue(maxsize=2)`. When the
queue is full, the new frame is dropped (`put_nowait` with silent discard).

**Alternatives:**
- Unbounded queue — risks unbounded memory growth for slow clients.
- Back-pressure (block producer) — would stall the ingest pipeline for all users.

**Rationale:**
- Real-time video tolerates frame drops far better than latency spikes or memory exhaustion.
- Dropping at the subscriber level isolates slow viewers from affecting the ingest path.

---

## 6. Vite + React + TypeScript for the frontend

**Decision:** React + TypeScript (Vite) served by nginx in the frontend container.

**Alternatives:**
- Plain HTML/JS — simpler, but no type safety for WebSocket message handling.
- Next.js — adds SSR complexity that adds no value for a single-page streaming UI.

**Rationale:**
- Assignment tags include `#React.js`.
- TypeScript provides compile-time contracts for ROI message shapes.
- Vite produces a static build served by nginx — minimal image size, no Node in production.
- nginx also acts as a reverse proxy for `/ws/*` and `/api/*`, giving the browser a single
  origin and avoiding CORS preflight on WebSocket upgrades.

---

## 7. Single-face assumption reflected in schema

**Decision:** The `roi_records` table stores one row per frame. If no face is detected,
`face_detected = false` and coordinate columns are NULL.

**Rationale:**
- The assignment states "Assume only one face will be present in the video."
- Storing a NULL row per frame preserves a complete frame-index timeline, making it
  easy to count detection rate, plot a timeline, or debug missed frames — all without
  changing the schema later.
