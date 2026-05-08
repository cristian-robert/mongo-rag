"use client";

import { useState } from "react";

import { evaluateWarnings, type AntiSlopWarning, type ThemeShape } from "./anti-slop-warnings";

interface AntiSlopAsideProps {
  theme: ThemeShape;
  /** Show only warnings for this section. If omitted, render all. */
  section?: AntiSlopWarning["section"];
}

/**
 * Inline list of anti-slop warnings rendered as a small <aside>.
 * Non-blocking; each item can be dismissed for the session.
 */
export function AntiSlopAside({ theme, section }: AntiSlopAsideProps) {
  const [dismissed, setDismissed] = useState<Set<string>>(() => new Set());
  const all = evaluateWarnings(theme);
  const filtered = (section ? all.filter((w) => w.section === section) : all).filter(
    (w) => !dismissed.has(w.id),
  );

  if (filtered.length === 0) return null;

  return (
    <aside className="space-y-2 rounded-lg border border-border/60 bg-muted/30 p-3 text-xs">
      <div className="flex items-baseline justify-between">
        <span className="font-medium uppercase tracking-wide text-muted-foreground">
          {filtered.length === 1 ? "Heads up" : `${filtered.length} suggestions`}
        </span>
      </div>
      <ul className="space-y-2">
        {filtered.map((w) => (
          <li
            key={w.id}
            className={`flex items-start justify-between gap-3 rounded border-l-2 bg-background/40 p-2 leading-snug ${
              w.severity === "blocker"
                ? "border-l-destructive"
                : w.severity === "warning"
                  ? "border-l-amber-500"
                  : "border-l-foreground/40"
            }`}
          >
            <div className="space-y-0.5">
              <div className="font-medium">{w.title}</div>
              <div className="text-muted-foreground">{w.detail}</div>
            </div>
            <button
              type="button"
              onClick={() =>
                setDismissed((prev) => {
                  const next = new Set(prev);
                  next.add(w.id);
                  return next;
                })
              }
              className="self-start text-muted-foreground hover:text-foreground"
              aria-label="Dismiss"
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
