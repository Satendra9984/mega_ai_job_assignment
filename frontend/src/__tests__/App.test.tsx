/**
 * Tests for <App />.
 *
 * WebSocket is mocked as a class so new WebSocket(...) works.
 * getUserMedia and video.play are stubbed so start() can run.
 * requestAnimationFrame is replaced with a no-op so drawLoop doesn't recurse.
 */
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";

// ---------------------------------------------------------------------------
// Typed mock WS instance
// ---------------------------------------------------------------------------

interface MockWSInstance {
  send: ReturnType<typeof vi.fn>;
  close: ReturnType<typeof vi.fn>;
  readyState: number;
  binaryType: string;
  onmessage: ((ev: Partial<MessageEvent>) => void) | null;
  onopen: (() => void) | null;
  onerror: (() => void) | null;
  onclose: ((ev: CloseEvent) => void) | null;
}

let wsInstance: MockWSInstance;

// Mock WebSocket as a proper class so `new WebSocket(...)` returns wsInstance
class MockWebSocket {
  send = vi.fn();
  close = vi.fn();
  readyState = WebSocket.OPEN;
  binaryType = "arraybuffer";
  onmessage: ((ev: Partial<MessageEvent>) => void) | null = null;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;

  constructor(_url: string) {
    // Register this instance for test access
    wsInstance = this;
  }
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.stubGlobal("WebSocket", MockWebSocket);

  // RAF is a no-op — drawLoop fires once on mount but doesn't recurse
  vi.stubGlobal("requestAnimationFrame", vi.fn(() => 1));
  vi.stubGlobal("cancelAnimationFrame", vi.fn());

  // Stub getUserMedia so start() doesn't throw before reaching WebSocket
  const mockStream: Partial<MediaStream> = {
    getTracks: () => [],
  };
  vi.stubGlobal("navigator", {
    ...navigator,
    mediaDevices: {
      getUserMedia: vi.fn().mockResolvedValue(mockStream),
    },
  });

  // Stub video.play() so it doesn't throw "not implemented" in jsdom
  vi.spyOn(HTMLVideoElement.prototype, "play").mockResolvedValue(undefined);

  // Stub canvas.getContext so drawing calls don't error
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
    drawImage: vi.fn(),
    strokeRect: vi.fn(),
    clearRect: vi.fn(),
    strokeStyle: "",
    lineWidth: 0,
  } as unknown as CanvasRenderingContext2D);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Helper: simulate clicking Start webcam and waiting for WS to open
// ---------------------------------------------------------------------------

async function startAndOpenWS() {
  const btn = screen.getByRole("button", { name: /start webcam/i });
  await act(async () => {
    btn.click();
    // Flush the async getUserMedia + video.play
    await Promise.resolve();
    await Promise.resolve();
  });
  // Simulate WS onopen which sets running=true
  act(() => {
    wsInstance?.onopen?.();
  });
}

// ---------------------------------------------------------------------------
// Render tests
// ---------------------------------------------------------------------------

describe("App — initial render", () => {
  it("renders the page heading", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: /MegaAI/i })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Idle");
  });

  it("shows a 'Start webcam' button when not running", () => {
    render(<App />);
    expect(screen.getByRole("button", { name: /start webcam/i })).toBeInTheDocument();
  });

  it("renders at least one canvas element", () => {
    const { container } = render(<App />);
    expect(container.querySelectorAll("canvas").length).toBeGreaterThanOrEqual(1);
  });

  it("ROI history button is disabled when no session is active", () => {
    render(<App />);
    expect(screen.getByRole("button", { name: /fetch roi history/i })).toBeDisabled();
  });

  it("shows endpoint reference in the footer", () => {
    render(<App />);
    // "WS /ws/ingest" appears in both the header description and the footer
    expect(screen.getAllByText(/ws\/ingest/i).length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// WebSocket message handling
// ---------------------------------------------------------------------------

describe("App — WebSocket message handling", () => {
  it("sets session_id when a session message is received", async () => {
    render(<App />);
    await startAndOpenWS();

    act(() => {
      wsInstance.onmessage?.({
        data: JSON.stringify({ type: "session", session_id: "test-uuid-1234" }),
      });
    });

    expect(await screen.findByText(/test-uuid-1234/)).toBeInTheDocument();
  });

  it("ROI history button becomes enabled after session is set", async () => {
    render(<App />);
    await startAndOpenWS();

    act(() => {
      wsInstance.onmessage?.({
        data: JSON.stringify({ type: "session", session_id: "sess-abc" }),
      });
    });

    const btn = await screen.findByRole("button", { name: /fetch roi history/i });
    expect(btn).not.toBeDisabled();
  });

  it("shows error message when an error message is received", async () => {
    render(<App />);
    await startAndOpenWS();

    act(() => {
      wsInstance.onmessage?.({
        data: JSON.stringify({
          type: "error",
          code: "FRAME_TOO_LARGE",
          detail: "Frame exceeds limit",
        }),
      });
    });

    expect(await screen.findByText(/FRAME_TOO_LARGE/)).toBeInTheDocument();
  });

  it("ignores malformed JSON without crashing", async () => {
    render(<App />);
    await startAndOpenWS();
    expect(() => {
      act(() => {
        wsInstance.onmessage?.({ data: "{not valid json" });
      });
    }).not.toThrow();
  });

  it("ignores non-string messages without crashing", async () => {
    render(<App />);
    await startAndOpenWS();
    expect(() => {
      act(() => {
        wsInstance.onmessage?.({ data: new ArrayBuffer(8) });
      });
    }).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// Stop behaviour
// ---------------------------------------------------------------------------

describe("App — stop behaviour", () => {
  it("shows Stop button after starting", async () => {
    render(<App />);
    await startAndOpenWS();
    expect(await screen.findByRole("button", { name: /stop/i })).toBeInTheDocument();
  });

  it("closes the WebSocket when Stop is clicked", async () => {
    render(<App />);
    await startAndOpenWS();

    const stopBtn = await screen.findByRole("button", { name: /stop/i });
    await act(async () => {
      stopBtn.click();
    });

    expect(wsInstance.close).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// ROI REST history
// ---------------------------------------------------------------------------

describe("App — ROI history fetch", () => {
  it("renders persisted ROI rows from GET /api/roi", async () => {
    const sessionUuid = "550e8400-e29b-41d4-a716-446655440000";
    const apiBody = {
      session_id: sessionUuid,
      total: 1,
      limit: 5,
      offset: 0,
      records: [
        {
          id: 1,
          frame_index: 0,
          detected_at: "2026-05-04T12:00:00.000Z",
          face_detected: true,
          x: 120,
          y: 80,
          w: 200,
          h: 240,
          confidence: 0.97,
        },
      ],
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => apiBody,
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await startAndOpenWS();

    act(() => {
      wsInstance.onmessage?.({
        data: JSON.stringify({ type: "session", session_id: sessionUuid }),
      });
    });

    const histBtn = await screen.findByRole("button", { name: /fetch roi history/i });
    await act(async () => {
      histBtn.click();
      await Promise.resolve();
    });

    expect(fetchMock).toHaveBeenCalled();
    expect(screen.getByRole("columnheader", { name: /^Frame$/i })).toBeInTheDocument();
    expect(screen.getByText("120")).toBeInTheDocument();
    expect(screen.getByText("97.0%")).toBeInTheDocument();
  });

  it("shows a clear message when ROI history returns 404", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: "Session not found" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await startAndOpenWS();

    act(() => {
      wsInstance.onmessage?.({
        data: JSON.stringify({
          type: "session",
          session_id: "550e8400-e29b-41d4-a716-446655440000",
        }),
      });
    });

    const histBtn = await screen.findByRole("button", { name: /fetch roi history/i });
    await act(async () => {
      histBtn.click();
      await Promise.resolve();
    });

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/Session not found/i);
  });

  it("dismisses the error alert when Dismiss is clicked", async () => {
    render(<App />);
    await startAndOpenWS();

    act(() => {
      wsInstance.onmessage?.({
        data: JSON.stringify({
          type: "error",
          code: "FRAME_TOO_LARGE",
          detail: "Too big",
        }),
      });
    });

    expect(await screen.findByRole("alert")).toHaveTextContent(/FRAME_TOO_LARGE/);
    await act(async () => {
      screen.getByRole("button", { name: /^Dismiss$/i }).click();
    });
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
