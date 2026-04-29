import Link from "next/link";

import { getSession } from "@/lib/auth";
import { redirect } from "next/navigation";

import { OnboardingProgress } from "@/components/onboarding/progress";

export default async function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getSession();
  if (!session?.user) {
    redirect("/login");
  }

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="border-b border-border/60 bg-background">
        <div className="mx-auto flex h-14 max-w-4xl items-center justify-between px-4 sm:px-6">
          <Link
            href="/"
            className="flex items-center gap-2 text-sm font-semibold tracking-tight"
          >
            <span
              aria-hidden
              className="grid size-6 place-items-center rounded-md border border-border bg-foreground/[0.04] font-mono text-[0.65rem] font-bold uppercase"
            >
              MR
            </span>
            MongoRAG
          </Link>
          <Link
            href="/dashboard"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Skip onboarding →
          </Link>
        </div>
      </header>
      <main className="flex flex-1 flex-col">
        <div className="mx-auto w-full max-w-2xl flex-1 px-4 py-10 sm:px-6 sm:py-14">
          <OnboardingProgress />
          <div className="mt-8">{children}</div>
        </div>
      </main>
    </div>
  );
}
