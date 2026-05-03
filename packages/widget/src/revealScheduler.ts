/**
 * Soft-reveal scheduler for streamed assistant tokens.
 *
 * Background: SSE token deltas can arrive in chunks of any size. Painting
 * a 200-character chunk in a single frame paints a whole sentence at once
 * and feels jarring — like the bot dropped a paragraph rather than typing.
 *
 * This module drips buffered content into the assistant message at a
 * bounded character-per-second rate via requestAnimationFrame, while:
 *
 *  - Honoring `prefers-reduced-motion` — chunks paint immediately.
 *  - Holding the typing-dots state for a minimum dwell window so the very
 *    first token (which can arrive within 50ms on fast paths) doesn't
 *    cause the dots to flash and disappear.
 *  - Cleaning up on destroy (panel close, new send) so we don't paint
 *    into a detached message after abort.
 *
 * The scheduler does NOT decide what counts as "received content" — it
 * just buffers strings pushed in via push() and drips them into a target.
 * Sources/done/error events should flushImmediate() and then bypass the
 * scheduler entirely.
 */

import type { ChatMessage } from "./types.js";

export interface RevealSchedulerOptions {
  /** Maximum characters revealed per second. Default: 600. */
  cps?: number;
  /** Minimum ms to keep the typing-dots state visible. Default: 150. */
  dwellMs?: number;
  /** Optional override of `prefers-reduced-motion` detection (testing). */
  reducedMotion?: boolean;
  /** Performance.now()-style clock (testing). */
  now?: () => number;
  /** rAF scheduler (testing). */
  raf?: (cb: (now: number) => void) => number;
  /** rAF canceller (testing). */
  cancelRaf?: (id: number) => void;
  /** setTimeout (testing). */
  setTimeout?: (cb: () => void, ms: number) => number;
  /** clearTimeout (testing). */
  clearTimeout?: (id: number) => void;
}

export class RevealScheduler {
  private buffer = "";
  private rafId: number | null = null;
  private timerId: number | null = null;
  private lastTick = 0;
  private destroyed = false;

  private readonly cps: number;
  private readonly dwellMs: number;
  private readonly startedAt: number;
  private readonly reduced: boolean;
  private readonly now: () => number;
  private readonly raf: (cb: (now: number) => void) => number;
  private readonly cancelRaf: (id: number) => void;
  private readonly setTimeoutFn: (cb: () => void, ms: number) => number;
  private readonly clearTimeoutFn: (id: number) => void;

  constructor(
    private readonly target: ChatMessage,
    private readonly onUpdate: () => void,
    options: RevealSchedulerOptions = {},
  ) {
    this.cps = options.cps ?? 600;
    this.dwellMs = options.dwellMs ?? 150;
    this.now = options.now ?? (() => performance.now());
    this.raf =
      options.raf ??
      ((cb) => requestAnimationFrame(cb));
    this.cancelRaf = options.cancelRaf ?? ((id) => cancelAnimationFrame(id));
    this.setTimeoutFn =
      options.setTimeout ??
      ((cb, ms) => setTimeout(cb, ms) as unknown as number);
    this.clearTimeoutFn = options.clearTimeout ?? ((id) => clearTimeout(id));
    this.reduced = options.reducedMotion ?? this.detectReducedMotion();
    this.startedAt = this.now();
  }

  /**
   * Append text to the reveal buffer. Paints immediately under
   * reduced-motion; otherwise schedules a rAF drip.
   *
   * No-op after destroy().
   */
  push(text: string): void {
    if (this.destroyed) return;
    if (!text) return;
    this.buffer += text;

    if (this.reduced) {
      this.flushImmediate();
      return;
    }
    this.scheduleStart();
  }

  /**
   * Synchronously paint everything in the buffer right now and clear
   * any pending rAF/timer. Use before applying terminal events
   * (sources / done / error) so the user sees the full token stream
   * before citations or error copy land.
   */
  flushImmediate(): void {
    if (this.destroyed) return;
    if (this.rafId !== null) {
      this.cancelRaf(this.rafId);
      this.rafId = null;
    }
    if (this.timerId !== null) {
      this.clearTimeoutFn(this.timerId);
      this.timerId = null;
    }
    if (this.buffer.length === 0) return;
    this.target.content += this.buffer;
    this.buffer = "";
    this.onUpdate();
  }

  /**
   * Stop all scheduled work without painting remaining buffer. Used
   * on panel close / new send / widget destroy where the in-flight
   * stream is abandoned.
   */
  destroy(): void {
    this.destroyed = true;
    if (this.rafId !== null) {
      this.cancelRaf(this.rafId);
      this.rafId = null;
    }
    if (this.timerId !== null) {
      this.clearTimeoutFn(this.timerId);
      this.timerId = null;
    }
    this.buffer = "";
  }

  /** True iff there is buffered content that hasn't been revealed yet. */
  hasPending(): boolean {
    return this.buffer.length > 0;
  }

  // --- private ---

  private scheduleStart(): void {
    if (this.rafId !== null || this.timerId !== null) return;
    const elapsed = this.now() - this.startedAt;
    if (elapsed >= this.dwellMs) {
      this.startTick();
      return;
    }
    const wait = this.dwellMs - elapsed;
    this.timerId = this.setTimeoutFn(() => {
      this.timerId = null;
      if (this.destroyed) return;
      this.startTick();
    }, wait);
  }

  private startTick(): void {
    this.lastTick = this.now();
    this.rafId = this.raf(this.tick);
  }

  private tick = (now: number): void => {
    if (this.destroyed) {
      this.rafId = null;
      return;
    }
    const dt = Math.max(0, (now - this.lastTick) / 1000);
    this.lastTick = now;
    // Reveal at least 1 character per frame — keeps progress visible
    // even at very low frame rates without overshooting the cps target
    // by much.
    const reveal = Math.max(1, Math.floor(this.cps * dt));
    if (this.buffer.length === 0) {
      this.rafId = null;
      return;
    }
    const chunk = this.buffer.slice(0, reveal);
    this.buffer = this.buffer.slice(reveal);
    this.target.content += chunk;
    this.onUpdate();
    if (this.buffer.length > 0) {
      this.rafId = this.raf(this.tick);
    } else {
      this.rafId = null;
    }
  };

  private detectReducedMotion(): boolean {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return false;
    }
    try {
      return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    } catch {
      return false;
    }
  }
}
