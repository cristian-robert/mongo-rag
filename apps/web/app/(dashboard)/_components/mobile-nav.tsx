"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";

import { cn } from "@/lib/utils";

import { SidebarNav } from "./sidebar-nav";

export function MobileNav({ tenantName }: { tenantName: string }) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const [lastPathname, setLastPathname] = useState(pathname);

  // Close drawer on route change without an effect.
  if (pathname !== lastPathname) {
    setLastPathname(pathname);
    if (open) setOpen(false);
  }

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open navigation"
        aria-expanded={open}
        aria-controls="mobile-nav-drawer"
        className={cn(
          "inline-flex size-8 items-center justify-center rounded-lg border border-border bg-background lg:hidden",
          "transition-colors hover:bg-muted",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        )}
      >
        <Menu className="size-4" aria-hidden="true" />
      </button>

      {open ? (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true">
          <div
            className="absolute inset-0 bg-foreground/40 backdrop-blur-[2px]"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          <div
            id="mobile-nav-drawer"
            className="absolute inset-y-0 left-0 flex w-[17rem] max-w-[85vw] flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground"
          >
            <div className="flex h-14 items-center justify-between border-b border-sidebar-border px-4">
              <div className="flex items-center gap-2">
                <div
                  aria-hidden="true"
                  className="grid size-7 place-items-center rounded-md bg-sidebar-foreground text-sidebar font-mono text-[0.7rem] font-semibold"
                >
                  MR
                </div>
                <span className="font-heading text-[0.95rem] font-semibold tracking-tight">
                  MongoRAG
                </span>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close navigation"
                className={cn(
                  "inline-flex size-8 items-center justify-center rounded-lg",
                  "transition-colors hover:bg-sidebar-accent",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring",
                )}
              >
                <X className="size-4" aria-hidden="true" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              <SidebarNav onNavigate={() => setOpen(false)} />
            </div>
            <div className="border-t border-sidebar-border px-4 py-3">
              <p className="text-[0.7rem] uppercase tracking-wide text-sidebar-foreground/50">
                Workspace
              </p>
              <p className="mt-0.5 truncate text-[0.84rem] font-medium">
                {tenantName}
              </p>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
