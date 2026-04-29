"use client";

import { useRef, useState } from "react";
import { LogOut } from "lucide-react";

import { cn } from "@/lib/utils";

function getInitials(input: string): string {
  const trimmed = input.trim();
  if (!trimmed) return "?";
  const parts = trimmed.split(/[\s@.]+/).filter(Boolean);
  if (parts.length === 0) return trimmed[0]!.toUpperCase();
  if (parts.length === 1) return parts[0]!.slice(0, 2).toUpperCase();
  return (parts[0]![0]! + parts[1]![0]!).toUpperCase();
}

export function UserMenu({
  email,
  name,
}: {
  email: string;
  name?: string | null;
}) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const initials = getInitials(name || email);

  return (
    <div className="relative">
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
        onClick={() => setOpen((v) => !v)}
        onBlur={(e) => {
          if (!e.currentTarget.parentElement?.contains(e.relatedTarget as Node)) {
            setOpen(false);
          }
        }}
        className={cn(
          "flex items-center gap-2 rounded-lg border border-border bg-background px-1.5 py-1 text-sm",
          "transition-colors hover:bg-muted",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        )}
      >
        <span
          aria-hidden="true"
          className="grid size-7 place-items-center rounded-md bg-foreground font-mono text-[0.7rem] font-semibold text-background"
        >
          {initials}
        </span>
        <span className="hidden max-w-[12rem] truncate pr-1 text-foreground/80 sm:inline">
          {email}
        </span>
      </button>

      {open ? (
        <div
          role="menu"
          aria-label="Account"
          className={cn(
            "absolute right-0 top-full z-50 mt-1.5 w-60 origin-top-right rounded-xl bg-popover p-1.5 text-popover-foreground shadow-lg ring-1 ring-foreground/10",
          )}
        >
          <div className="px-2 py-1.5">
            {name ? (
              <p className="truncate text-sm font-medium text-foreground">
                {name}
              </p>
            ) : null}
            <p className="truncate text-[0.8rem] text-muted-foreground">
              {email}
            </p>
          </div>
          <div className="my-1 h-px bg-border" />
          {/*
            Sign-out is a POST form (CSRF surface). The route handler clears
            Supabase cookies and redirects to /login.
          */}
          <form method="POST" action="/auth/signout">
            <button
              role="menuitem"
              type="submit"
              onClick={() => setOpen(false)}
              className={cn(
                "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-foreground",
                "transition-colors hover:bg-muted",
                "focus-visible:outline-none focus-visible:bg-muted",
              )}
            >
              <LogOut className="size-4" aria-hidden="true" />
              Sign out
            </button>
          </form>
        </div>
      ) : null}
    </div>
  );
}
