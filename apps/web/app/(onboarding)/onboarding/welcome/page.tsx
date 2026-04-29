import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRightIcon,
  FileTextIcon,
  KeyRoundIcon,
  SparkleIcon,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { getSession } from "@/lib/auth";

export const metadata: Metadata = {
  title: "Welcome — MongoRAG onboarding",
  description: "Get your tenant set up in under five minutes.",
};

export const dynamic = "force-dynamic";

const STEPS = [
  {
    icon: FileTextIcon,
    title: "Upload your first document",
    body: "PDF, Word, Markdown, or HTML — Docling normalizes and chunks it for retrieval.",
  },
  {
    icon: KeyRoundIcon,
    title: "Mint an API key",
    body: "A tenant-scoped key for the embed widget and any programmatic access.",
  },
  {
    icon: SparkleIcon,
    title: "Copy your embed snippet",
    body: "Four lines. Drop it on any page — no SDK, no build step.",
  },
];

export default async function WelcomePage() {
  const session = await getSession();
  const name = session?.user?.name?.trim() || session?.user?.email || "there";

  return (
    <section aria-labelledby="onboarding-welcome" className="space-y-8">
      <header className="space-y-3">
        <p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
          Onboarding
        </p>
        <h1
          id="onboarding-welcome"
          className="text-balance text-3xl font-light tracking-tight sm:text-4xl"
        >
          Welcome, {name}.
        </h1>
        <p className="max-w-prose text-muted-foreground">
          Your tenant is provisioned. Three quick steps and you&apos;ll have a
          live retrieval-grounded chatbot you can drop on any page.
        </p>
      </header>

      <ol className="space-y-3">
        {STEPS.map((step, idx) => (
          <li
            key={step.title}
            className="flex items-start gap-4 rounded-xl border border-border bg-background p-5"
          >
            <span
              aria-hidden
              className="grid size-9 shrink-0 place-items-center rounded-md border border-border bg-muted/40"
            >
              <step.icon className="size-4" />
            </span>
            <div className="space-y-1">
              <p className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                Step {String(idx + 1).padStart(2, "0")}
              </p>
              <h2 className="text-base font-medium">{step.title}</h2>
              <p className="text-sm text-muted-foreground">{step.body}</p>
            </div>
          </li>
        ))}
      </ol>

      <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs text-muted-foreground">
          You can leave at any time and pick up where you left off.
        </p>
        <Button asChild size="lg" className="h-11 sm:w-auto">
          <Link href="/onboarding/document">
            Start with a document
            <ArrowRightIcon aria-hidden className="ml-1.5" />
          </Link>
        </Button>
      </div>
    </section>
  );
}
