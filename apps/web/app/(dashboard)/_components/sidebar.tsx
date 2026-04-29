import Link from "next/link";

import { SidebarNav } from "./sidebar-nav";

export function Sidebar({ tenantName }: { tenantName: string }) {
  return (
    <aside
      aria-label="Primary"
      className="hidden lg:flex lg:w-60 lg:shrink-0 lg:flex-col lg:border-r lg:border-sidebar-border lg:bg-sidebar"
    >
      <div className="flex h-14 items-center gap-2 border-b border-sidebar-border px-4">
        <Link
          href="/dashboard"
          className="flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring rounded-md"
        >
          <div
            aria-hidden="true"
            className="grid size-7 place-items-center rounded-md bg-sidebar-foreground text-sidebar font-mono text-[0.7rem] font-semibold tracking-tight"
          >
            MR
          </div>
          <span className="font-heading text-[0.95rem] font-semibold tracking-tight text-sidebar-foreground">
            MongoRAG
          </span>
        </Link>
      </div>

      <div className="flex-1 overflow-y-auto">
        <SidebarNav />
      </div>

      <div className="border-t border-sidebar-border px-4 py-3">
        <p className="text-[0.7rem] uppercase tracking-wide text-sidebar-foreground/50">
          Workspace
        </p>
        <p className="mt-0.5 truncate text-[0.84rem] font-medium text-sidebar-foreground">
          {tenantName}
        </p>
      </div>
    </aside>
  );
}
