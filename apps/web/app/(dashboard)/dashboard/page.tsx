import { auth } from "@/lib/auth";

export default async function DashboardPage() {
  const session = await auth();

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-center flex flex-col gap-4">
        <h1 className="text-3xl font-extralight tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Welcome, {session?.user?.email}
        </p>
        <p className="text-sm text-muted-foreground">
          Tenant: {session?.user?.tenant_id}
        </p>
      </div>
    </div>
  );
}
