import { Breadcrumbs } from "./breadcrumbs";
import { MobileNav } from "./mobile-nav";
import { UserMenu } from "./user-menu";

export function Topbar({
  tenantName,
  email,
  name,
}: {
  tenantName: string;
  email: string;
  name?: string | null;
}) {
  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-3 border-b border-border bg-background/85 px-3 backdrop-blur supports-[backdrop-filter]:bg-background/70 sm:px-5">
      <MobileNav tenantName={tenantName} />
      <div className="flex items-center gap-2">
        <span className="hidden text-[0.7rem] uppercase tracking-wide text-muted-foreground sm:inline">
          Tenant
        </span>
        <span className="rounded-md border border-border bg-muted/40 px-2 py-0.5 text-[0.8rem] font-medium text-foreground">
          {tenantName}
        </span>
      </div>

      <div className="ml-2 hidden h-5 w-px bg-border md:block" aria-hidden="true" />
      <Breadcrumbs />

      <div className="ml-auto flex items-center gap-2">
        <UserMenu email={email} name={name} />
      </div>
    </header>
  );
}
