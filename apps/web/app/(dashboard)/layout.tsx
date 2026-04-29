import { redirect } from "next/navigation";

import { auth } from "@/lib/auth";

import { Sidebar } from "./_components/sidebar";
import { Topbar } from "./_components/topbar";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  if (!session?.user) {
    redirect("/login");
  }

  const tenantName = session.user.tenant_id;

  return (
    <div className="flex min-h-screen w-full bg-background text-foreground">
      <Sidebar tenantName={tenantName} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar
          tenantName={tenantName}
          email={session.user.email}
          name={session.user.name}
        />
        <main
          id="main"
          className="flex-1 px-4 py-6 sm:px-6 lg:px-8"
          tabIndex={-1}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
