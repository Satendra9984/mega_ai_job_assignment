/**
 * Tests for the canvas ROI overlay.
 *
 * The canvas draw logic in App.tsx runs inside a requestAnimationFrame loop
 * and accesses video/canvas refs directly — hard to spy on in jsdom.
 * These tests focus on what IS reliably testable:
 *
 *   1. ROI state updates when a `roi` WS message is received.
 *   2. Correct values (x, y, w, h, confidence) reach the component state.
 *   3. The confidence badge renders when face is detected.
 *   4. The canvas element is present in the DOM.
 *
 * The `strokeRect` call itself is an implementation detail of `drawLoop`
 * (runs in RAF, reads from React state + DOM refs). Its correctness is
 * verified in Sprint 3 E2E tests against a live Compose stack.
 */
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";

// ---------------------------------------------------------------------------
// Shared WS mock (same pattern as App.test.tsx)
// ---------------------------------------------------------------------------

let wsInstance: {
  onmessage: ((ev: Partial<MessageEvent>) => void) | null;
  onopen: (() => void) | null;
  send: ReturnType<typeof vi.fn>;
  close: ReturnType<typeof vi.fn>;
  readyState: number;
  binaryType: string;
};

class MockWebSocket {
  onmessage: ((ev: Partial<MessageEvent>) => void) | null = null;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  send = vi.fn();
  close = vi.fn();
  readyState = WebSocket.OPEN;
  binaryType = "arraybuffer";
  static OPEN = 1;

  constructor(_url: string) {
    wsInstance = this;
  }
}

beforeEach(() => {
  vi.stubGlobal("WebSocket", MockWebSocket);
  // Non-recursive RAF — drawLoop runs once but doesn't self-schedule
  vi.stubGlobal("requestAnimationFrame", vi.fn(() => 1));
  vi.stubGlobal("cancelAnimationFrame", vi.fn());

  vi.stubGlobal("navigator", {
    ...navigator,
    mediaDevices: {
      getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [] }),
    },
  });
  vi.spyOn(HTMLVideoElement.prototype, "play").mockResolvedValue(undefined);
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
    drawImage: vi.fn(),
    strokeRect: vi.fn(),
    strokeStyle: "",
    lineWidth: 0,
  } as unknown as CanvasRenderingContext2D);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

async function startWS() {
  const btn = screen.getByRole("button", { name: /start webcam/i });
  await act(async () => {
    btn.click();
    await Promise.resolve();
    await Promise.resolve();
  });
  act(() => {
    wsInstance?.onopen?.();
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Canvas ROI overlay", () => {
  it("display canvas is rendered in the DOM", () => {
    const { container } = render(<App />);
    const canvases = container.querySelectorAll("canvas");
    expect(canvases.length).toBeGreaterThanOrEqual(1);
    // The first visible canvas is the display canvas
    const displayCanvas = Array.from(canvases).find(
      (c) => c.style.display !== "none"
    );
    expect(displayCanvas).toBeTruthy();
  });

  it("ROI state has correct values after receiving a roi message with face", async () => {
    render(<App />);
    await startWS();

    // Set session first so the ROI info panel shows
    act(() => {
      wsInstance.onmessage?.({
        data: JSON.stringify({ type: "session", session_id: "test-sess" }),
      });
    });

    act(() => {
      wsInstance.onmessage?.({
        data: JSON.stringify({
          type: "roi",
          session_id: "test-sess",
          frame_index: 3,
          face_detected: true,
          x: 100,
          y: 50,
          w: 80,
          h: 90,
          confidence: 0.95,
        }),
      });
    });

    const live = await screen.findByRole("region", { name: "Current ROI" });
    expect(live).toHaveTextContent(/Frame index\s*3/);
    expect(live).toHaveTextContent(/x=\s*100/);
    expect(live).toHaveTextContent(/95\.0%/);
  });

  it("confidence badge does NOT appear when face_detected is false", async () => {
    render(<App />);
    await startWS();

    act(() => {
      wsInstance.onmessage?.({
        data: JSON.stringify({ type: "session", session_id: "test-sess-2" }),
      });
    });

    act(() => {
      wsInstance.onmessage?.({
        data: JSON.stringify({
          type: "roi",
          session_id: "test-sess-2",
          frame_index: 0,
          face_detected: false,
          x: null,
          y: null,
          w: null,
          h: null,
          confidence: null,
        }),
      });
    });

    const live = await screen.findByRole("region", { name: "Current ROI" });
    expect(live).toHaveTextContent(/Frame index\s*0/);
    expect(live).toHaveTextContent(/Face\s*no/);
    // No percentage when confidence is null (em dash only, not a % badge)
    expect(screen.queryByText(/%/)).toBeNull();
  });

  it("roi state updates frame_index on consecutive frames", async () => {
    render(<App />);
    await startWS();

    act(() => {
      wsInstance.onmessage?.({
        data: JSON.stringify({ type: "session", session_id: "sess-frames" }),
      });
    });

    for (let i = 0; i < 3; i++) {
      act(() => {
        wsInstance.onmessage?.({
          data: JSON.stringify({
            type: "roi",
            session_id: "sess-frames",
            frame_index: i,
            face_detected: false,
            x: null,
            y: null,
            w: null,
            h: null,
            confidence: null,
          }),
        });
      });
    }

    expect(await screen.findByRole("region", { name: "Current ROI" })).toHaveTextContent(
      /Frame index\s*2/,
    );
  });
});
