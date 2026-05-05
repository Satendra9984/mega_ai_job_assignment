# API Reference

Base URLs (local Docker):
- Backend: `http://localhost:8000` / `ws://localhost:8000`
- Via nginx proxy (frontend container): `http://localhost:3000`

---

## 1. WebSocket — Ingest Feed

**Endpoint:** `WS /ws/ingest`

The primary endpoint. The client (browser webcam) connects, receives a session handshake,
then sends video frames and receives ROI detections in return.

### Connection

```
ws://localhost:8000/ws/ingest
```

No query parameters required.

### On Connect — Server → Client (handshake)

The server immediately sends a JSON text frame:

```json
{
  "type": "session",
  "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

The client should store `session_id` to correlate `/api/roi` history queries.

### Client → Server (each frame)

Send raw JPEG bytes as a **binary WebSocket message**.

| Constraint | Value |
|------------|-------|
| Format | JPEG |
| Max size | `MAX_FRAME_BYTES` env var (default 1 MB) |
| Recommended rate | ≤ 10 fps (100 ms interval) |

### Server → Client (ROI message — per frame)

The server responds with a **text JSON frame** after each binary frame received:

**Face detected:**

```json
{
  "type": "roi",
  "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "frame_index": 42,
  "face_detected": true,
  "x": 120,
  "y": 80,
  "w": 200,
  "h": 240,
  "confidence": 0.97
}
```

**No face detected:**

```json
{
  "type": "roi",
  "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "frame_index": 43,
  "face_detected": false,
  "x": null,
  "y": null,
  "w": null,
  "h": null,
  "confidence": null
}
```

### Server → Client (error message)

```json
{
  "type": "error",
  "code": "FRAME_TOO_LARGE",
  "detail": "Frame exceeds 1048576 bytes"
}
```

Error codes:

| Code | Meaning |
|------|---------|
| `FRAME_TOO_LARGE` | Binary message exceeds `MAX_FRAME_BYTES` |
| `INVALID_FRAME` | Could not decode as JPEG |
| `DETECTION_ERROR` | Internal detector failure (frame skipped) |

### Disconnect

The server cleans up the session on disconnect. No explicit close message needed.

---

## 2. WebSocket — Stream Feed

**Endpoint:** `WS /ws/stream`

Passive viewer endpoint. Connects and receives raw (unannotated) JPEG frames that were
published by the active ingest session. Useful for secondary viewers or testing.

### Connection

```
ws://localhost:8000/ws/stream
```

Optional query parameter:

| Param | Type | Description |
|-------|------|-------------|
| `session_id` | UUID string | If provided, only frames from that session are forwarded (future enhancement; currently all frames are broadcast) |

### Server → Client

Each message is a **binary WebSocket frame** containing raw JPEG bytes (same as ingest
input — no bounding box drawn server-side).

### Notes

- Uses a bounded queue (maxsize=2). If the client is slow, frames are dropped silently to
  avoid unbounded buffering.
- Multiple viewers can connect simultaneously.

---

## 3. REST — Query ROI Data

**Endpoint:** `GET /api/roi`

Returns persisted ROI records for a given session. Used by the frontend history panel and
any external tooling.

### Request

```
GET /api/roi?session_id={uuid}&limit={n}&offset={n}
```

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `session_id` | UUID string | Yes | — | Session to query |
| `limit` | integer | No | 100 | Max records to return (1–1000) |
| `offset` | integer | No | 0 | Offset for compatibility mode |
| `use_cursor` | boolean | No | `false` | Enables cursor pagination mode |
| `cursor` | string | No | `null` | Opaque token for the next cursor page |
| `snapshot` | string | No | `null` | Opaque frozen-snapshot boundary token |

### Pagination modes

- **Offset compatibility mode** (`use_cursor=false`): retains historical `limit/offset` behavior.
- **Cursor mode** (`use_cursor=true`): uses deterministic order `detected_at DESC, id DESC` and is stable under live writes.
- In cursor mode, the first page returns `snapshot` and `next_cursor`; pass both for subsequent pages.

### Response 200 OK

```json
{
  "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "total": 312,
  "limit": 100,
  "offset": 0,
  "has_more": true,
  "next_cursor": "eyJkZXRlY3RlZF9hdCI6IjIwMjYtMDUtMDRUMDQ6MzA6MDAuMjIzKzAwOjAwIiwiaWQiOjJ9",
  "snapshot": "eyJtYXhfaWQiOjMxMn0",
  "records": [
    {
      "id": 1,
      "frame_index": 0,
      "detected_at": "2026-05-04T04:30:00.123Z",
      "face_detected": true,
      "x": 120,
      "y": 80,
      "w": 200,
      "h": 240,
      "confidence": 0.97
    },
    {
      "id": 2,
      "frame_index": 1,
      "detected_at": "2026-05-04T04:30:00.223Z",
      "face_detected": false,
      "x": null,
      "y": null,
      "w": null,
      "h": null,
      "confidence": null
    }
  ]
}
```

### Cursor page follow-up example

```
GET /api/roi?session_id={uuid}&limit=100&use_cursor=true&cursor={next_cursor}&snapshot={snapshot}
```

### Response 422 Unprocessable Entity

```json
{
  "detail": [
    {
      "loc": ["query", "session_id"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### Response 404 Not Found

```json
{
  "detail": "Session not found"
}
```

---

## Interactive Docs

FastAPI exposes Swagger UI at `http://localhost:8000/docs` and ReDoc at
`http://localhost:8000/redoc` — covering the REST endpoint fully. WebSocket endpoints
are documented here because OpenAPI does not yet natively describe WS message schemas.

---

## WebSocket Message Type Summary

| Direction | Transport | `"type"` field | Payload |
|-----------|-----------|----------------|---------|
| Server → Client | Text JSON | `"session"` | `session_id` |
| Client → Server | Binary | — | JPEG bytes |
| Server → Client | Text JSON | `"roi"` | detection result |
| Server → Client | Text JSON | `"error"` | error code + detail |
| `/ws/stream` S→C | Binary | — | JPEG bytes |
