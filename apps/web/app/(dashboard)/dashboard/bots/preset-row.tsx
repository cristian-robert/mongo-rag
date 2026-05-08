"use client";

import { Button } from "@/components/ui/button";
import { THEME_PRESETS, type ThemePreset } from "./presets";

interface PresetRowProps {
  onApply: (preset: ThemePreset) => void;
  onUndo?: () => void;
  canUndo?: boolean;
}

/**
 * Inline row of theme preset chips. Click applies the preset's
 * widget_config overrides; "Undo" rewinds the last apply (one step).
 */
export function PresetRow({ onApply, onUndo, canUndo = false }: PresetRowProps) {
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">Start from a preset</p>
      <p className="text-xs text-muted-foreground">
        Click to apply. Customizes everything below — your previous values can
        be restored once with the undo button.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        {THEME_PRESETS.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => onApply(p)}
            className="group relative rounded-lg border border-border/60 bg-card px-3 py-2 text-left transition hover:border-foreground/30 hover:bg-muted/50"
          >
            <PresetSwatch preset={p} />
            <div className="text-xs font-medium">{p.label}</div>
            <div className="text-[10px] text-muted-foreground line-clamp-2 max-w-[180px]">
              {p.description}
            </div>
          </button>
        ))}
        {onUndo && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onUndo}
            disabled={!canUndo}
            className="ml-auto self-end"
          >
            Undo preset
          </Button>
        )}
      </div>
    </div>
  );
}

function PresetSwatch({ preset }: { preset: ThemePreset }) {
  const primary = preset.apply.primary_color ?? "#0f172a";
  const bg = preset.apply.background ?? "#ffffff";
  const fg = preset.apply.foreground ?? "#0f172a";
  return (
    <div
      className="mb-1.5 flex h-10 w-10 items-center justify-center rounded-md border border-border/60"
      style={{ background: bg, color: fg }}
      aria-hidden="true"
    >
      <div
        className="h-5 w-5 rounded-full"
        style={{ background: primary }}
      />
    </div>
  );
}
