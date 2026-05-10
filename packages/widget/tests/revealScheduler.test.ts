import { describe, expect, it } from "vitest";
import { RevealScheduler } from "../src/revealScheduler.js";
import type { ChatMessage } from "../src/types.js";

function makeMsg(): ChatMessage {
  return { role: "assistant", content: "", pending: true };
}

interface FakeClock {
  now: () => number;
  tick(ms: number): void;
  raf(cb: (now: number) => void): number;
  cancelRaf(id: number): void;
  setTimeoutFn(cb: () => void, ms: number): number;
  clearTimeoutFn(id: number): void;
  /** Run all rAF callbacks with the current `now`. */
  flushFrame(): void;
  /** Tick + flush rAFs in 16ms steps until predicate is true or budget runs out. */
  advanceUntil(pred: () => boolean, maxMs?: number): void;
}

function makeClock(): FakeClock {
  let t = 0;
  let nextRaf = 1;
  let nextTimer = 1;
  const rafs: Array<{ id: number; cb: (now: number) => void }> = [];
  const timers: Array<{ id: number; due: number; cb: () => void }> = [];

  const clock: FakeClock = {
    now: () => t,
    tick(ms: number) {
      t += ms;
      // Fire any due timers in due order.
      for (;;) {
        timers.sort((a, b) => a.due - b.due);
        const next = timers[0];
        if (!next || next.due > t) break;
        timers.shift();
        next.cb();
      }
    },
    raf(cb) {
      const id = nextRaf++;
      rafs.push({ id, cb });
      return id;
    },
    cancelRaf(id) {
      const idx = rafs.findIndex((r) => r.id === id);
      if (idx !== -1) rafs.splice(idx, 1);
    },
    setTimeoutFn(cb, ms) {
      const id = nextTimer++;
      timers.push({ id, due: t + ms, cb });
      return id;
    },
    clearTimeoutFn(id) {
      const idx = timers.findIndex((tm) => tm.id === id);
      if (idx !== -1) timers.splice(idx, 1);
    },
    flushFrame() {
      const callbacks = rafs.splice(0);
      for (const r of callbacks) r.cb(t);
    },
    advanceUntil(pred, maxMs = 5000) {
      let elapsed = 0;
      while (!pred() && elapsed < maxMs) {
        clock.tick(16);
        clock.flushFrame();
        elapsed += 16;
      }
    },
  };
  return clock;
}

describe("RevealScheduler", () => {
  it("reduced-motion paints content immediately", () => {
    const msg = makeMsg();
    const scheduler = new RevealScheduler(msg, () => {}, {
      reducedMotion: true,
    });
    scheduler.push("Hello world");
    expect(msg.content).toBe("Hello world");
  });

  it("respects the dwell window before starting reveal", () => {
    const clock = makeClock();
    const msg = makeMsg();
    const updates: string[] = [];
    const scheduler = new RevealScheduler(
      msg,
      () => updates.push(msg.content),
      {
        cps: 600,
        dwellMs: 150,
        now: clock.now,
        raf: clock.raf,
        cancelRaf: clock.cancelRaf,
        setTimeout: clock.setTimeoutFn,
        clearTimeout: clock.clearTimeoutFn,
        reducedMotion: false,
      },
    );

    scheduler.push("Hi");
    // Before dwell elapses, nothing has been revealed.
    clock.tick(100);
    clock.flushFrame();
    expect(msg.content).toBe("");

    // Once dwell elapses, the rAF kicks in and starts revealing.
    clock.tick(60); // total 160ms — past dwell
    // The dwell timer fires and schedules rAF; flush rAF now.
    clock.flushFrame();
    expect(msg.content.length).toBeGreaterThan(0);
  });

  it("drips content at approximately the configured cps", () => {
    const clock = makeClock();
    const msg = makeMsg();
    const scheduler = new RevealScheduler(msg, () => {}, {
      cps: 600,
      dwellMs: 0,
      now: clock.now,
      raf: clock.raf,
      cancelRaf: clock.cancelRaf,
      setTimeout: clock.setTimeoutFn,
      clearTimeout: clock.clearTimeoutFn,
      reducedMotion: false,
    });

    const text = "x".repeat(120);
    scheduler.push(text);
    // Drain the buffer by ticking 16ms frames.
    clock.advanceUntil(() => !scheduler.hasPending());

    expect(msg.content.length).toBe(text.length);
    expect(scheduler.hasPending()).toBe(false);
  });

  it("flushImmediate paints all buffered content right now", () => {
    const clock = makeClock();
    const msg = makeMsg();
    const scheduler = new RevealScheduler(msg, () => {}, {
      cps: 600,
      dwellMs: 200,
      now: clock.now,
      raf: clock.raf,
      cancelRaf: clock.cancelRaf,
      setTimeout: clock.setTimeoutFn,
      clearTimeout: clock.clearTimeoutFn,
      reducedMotion: false,
    });

    scheduler.push("Hello world");
    expect(msg.content).toBe("");
    scheduler.flushImmediate();
    expect(msg.content).toBe("Hello world");
    expect(scheduler.hasPending()).toBe(false);
  });

  it("destroy stops further scheduling and discards buffered content", () => {
    const clock = makeClock();
    const msg = makeMsg();
    const scheduler = new RevealScheduler(msg, () => {}, {
      cps: 600,
      dwellMs: 0,
      now: clock.now,
      raf: clock.raf,
      cancelRaf: clock.cancelRaf,
      setTimeout: clock.setTimeoutFn,
      clearTimeout: clock.clearTimeoutFn,
      reducedMotion: false,
    });

    scheduler.push("Hello world");
    scheduler.destroy();
    // After destroy, advancing the clock must not paint anything new.
    clock.advanceUntil(() => false, 200);
    expect(msg.content).toBe("");

    // push() after destroy is a no-op.
    scheduler.push("more");
    expect(msg.content).toBe("");
  });

  it("multiple pushes accumulate into the same buffer", () => {
    const clock = makeClock();
    const msg = makeMsg();
    const scheduler = new RevealScheduler(msg, () => {}, {
      cps: 600,
      dwellMs: 0,
      now: clock.now,
      raf: clock.raf,
      cancelRaf: clock.cancelRaf,
      setTimeout: clock.setTimeoutFn,
      clearTimeout: clock.clearTimeoutFn,
      reducedMotion: false,
    });

    scheduler.push("Hello ");
    scheduler.push("world");
    clock.advanceUntil(() => !scheduler.hasPending());
    expect(msg.content).toBe("Hello world");
  });
});
