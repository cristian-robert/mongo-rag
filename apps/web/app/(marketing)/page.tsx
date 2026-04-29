import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRightIcon,
  DatabaseIcon,
  FileTextIcon,
  KeyRoundIcon,
  ShieldCheckIcon,
  SparkleIcon,
  ZapIcon,
} from "lucide-react";

import { CodeSnippet } from "@/components/marketing/code-snippet";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "MongoRAG — Grounded AI chat for your docs",
  description:
    "Upload your documentation, get a script tag, ship a chatbot grounded in your own content. Multi-tenant RAG built on MongoDB Atlas Vector Search.",
  openGraph: {
    title: "MongoRAG — Grounded AI chat for your docs",
    description:
      "Upload your documentation, get a script tag, ship a chatbot grounded in your own content.",
    type: "website",
  },
};

const STEPS = [
  {
    icon: FileTextIcon,
    title: "Upload your docs",
    body: "PDF, Word, Markdown, HTML, audio. Docling chunks them at semantic boundaries; we embed and index them.",
  },
  {
    icon: KeyRoundIcon,
    title: "Get your script tag",
    body: "Issue an API key from the dashboard. Copy the four-line snippet — no SDK, no build step required.",
  },
  {
    icon: SparkleIcon,
    title: "Chat on your site",
    body: "Visitors get answers grounded in your own documentation, with citations back to the source chunk.",
  },
];

const FEATURES = [
  {
    icon: ZapIcon,
    title: "Hybrid retrieval",
    body: "RRF fuses vector and full-text scores, so synonym-heavy questions and exact-phrase lookups both land.",
  },
  {
    icon: ShieldCheckIcon,
    title: "Tenant isolation by default",
    body: "Every query is scoped to your tenant_id at the data layer. Your content never leaks across customers.",
  },
  {
    icon: DatabaseIcon,
    title: "MongoDB Atlas native",
    body: "Vector Search and Atlas Search run on the same cluster as your operational data. One database, no glue.",
  },
  {
    icon: KeyRoundIcon,
    title: "Pluggable models",
    body: "Bring OpenAI, OpenRouter, Gemini, or self-host with Ollama. Swap models per bot without redeploying.",
  },
];

const FAQS = [
  {
    q: "How is this different from a generic ChatGPT plugin?",
    a: "MongoRAG only answers from your own documents. The agent retrieves chunks via hybrid search (vector + full-text fusion) and the LLM is prompted to refuse when there is no grounding evidence. You get citations back to the source chunk every time.",
  },
  {
    q: "What document formats are supported?",
    a: "PDF, Word, PowerPoint, Excel, HTML, Markdown, plain text, and audio transcripts. Docling normalizes everything to markdown and chunks it semantically using heading context.",
  },
  {
    q: "Can I self-host?",
    a: "Yes. The whole stack — FastAPI backend, Next.js dashboard, MongoDB Atlas — can run in your own infrastructure. The Pro and Enterprise plans include the production-grade Docker images and deploy guides.",
  },
  {
    q: "Which LLM providers do you support?",
    a: "OpenAI, OpenRouter (Claude, Llama, Mistral, etc.), Google Gemini, and any OpenAI-compatible endpoint including Ollama. Pick your provider per bot from the dashboard.",
  },
  {
    q: "Is there a free plan?",
    a: "Yes — the Free plan includes 100 queries per month, up to 50 documents, and a single bot. Enough to ship a real product on a side project.",
  },
];

export default function LandingPage() {
  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden border-b border-border/60">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.18] [mask-image:radial-gradient(ellipse_at_top,black,transparent_70%)]"
          style={{
            backgroundImage:
              "radial-gradient(circle, currentColor 1px, transparent 1px)",
            backgroundSize: "28px 28px",
            color: "var(--foreground)",
          }}
        />
        <div className="relative mx-auto flex max-w-6xl flex-col items-center gap-10 px-4 py-20 sm:px-6 lg:py-28">
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-background/60 px-3 py-1 text-xs font-medium text-muted-foreground">
            <span aria-hidden className="size-1.5 rounded-full bg-emerald-500" />
            Now with hybrid RRF search and per-bot model routing
          </div>
          <h1 className="max-w-3xl text-balance text-center text-4xl font-extralight tracking-tight sm:text-5xl lg:text-6xl">
            Ship a chatbot grounded in{" "}
            <span className="font-serif italic text-foreground/90">
              your own documentation
            </span>
            .
          </h1>
          <p className="max-w-2xl text-balance text-center text-lg text-muted-foreground">
            MongoRAG turns your PDFs, wikis, and help docs into a typed,
            multi-tenant retrieval API — and an embeddable widget that drops
            onto any page in four lines.
          </p>
          <div className="flex flex-col items-center gap-3 sm:flex-row">
            <Button asChild size="lg" className="h-11 px-5">
              <Link href="/signup">
                Get started free
                <ArrowRightIcon aria-hidden className="ml-1.5" />
              </Link>
            </Button>
            <Button asChild variant="outline" size="lg" className="h-11 px-5">
              <Link href="/pricing">See pricing</Link>
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Free plan available · No credit card required
          </p>
        </div>
      </section>

      {/* Code snippet showcase */}
      <section className="border-b border-border/60 bg-muted/20">
        <div className="mx-auto grid max-w-6xl items-center gap-10 px-4 py-16 sm:px-6 md:grid-cols-2">
          <div className="space-y-4">
            <p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
              The whole integration
            </p>
            <h2 className="text-3xl font-light tracking-tight sm:text-4xl">
              Four lines. One script tag. No build step.
            </h2>
            <p className="text-muted-foreground">
              Drop the widget on any page — landing site, docs portal, customer
              dashboard — and it picks up your bot, theme, and rate limits from
              the API key.
            </p>
            <ul className="space-y-2 text-sm text-foreground/80">
              <li className="flex gap-2">
                <span aria-hidden className="text-foreground">
                  ·
                </span>
                Works in any framework (Next, Astro, Rails, plain HTML)
              </li>
              <li className="flex gap-2">
                <span aria-hidden className="text-foreground">
                  ·
                </span>
                Streamed responses with citations back to source chunks
              </li>
              <li className="flex gap-2">
                <span aria-hidden className="text-foreground">
                  ·
                </span>
                Rate-limited and tenant-scoped at the API layer
              </li>
            </ul>
          </div>
          <CodeSnippet />
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="scroll-mt-20 border-b border-border/60">
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <div className="mb-12 max-w-2xl space-y-3">
            <p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
              How it works
            </p>
            <h2 className="text-3xl font-light tracking-tight sm:text-4xl">
              From document upload to live chatbot in three steps.
            </h2>
          </div>
          <ol className="grid gap-6 md:grid-cols-3">
            {STEPS.map((step, idx) => (
              <li
                key={step.title}
                className="relative rounded-xl border border-border bg-background p-6"
              >
                <div className="flex items-center gap-3">
                  <span className="grid size-9 place-items-center rounded-md border border-border bg-muted/40">
                    <step.icon aria-hidden className="size-4" />
                  </span>
                  <span className="font-mono text-xs text-muted-foreground">
                    Step {String(idx + 1).padStart(2, "0")}
                  </span>
                </div>
                <h3 className="mt-4 text-lg font-medium">{step.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  {step.body}
                </p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="scroll-mt-20 border-b border-border/60 bg-muted/20">
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <div className="mb-12 max-w-2xl space-y-3">
            <p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
              Why teams choose MongoRAG
            </p>
            <h2 className="text-3xl font-light tracking-tight sm:text-4xl">
              Production-grade retrieval. No glue code.
            </h2>
          </div>
          <ul className="grid gap-px overflow-hidden rounded-xl border border-border bg-border md:grid-cols-2">
            {FEATURES.map((feature) => (
              <li
                key={feature.title}
                className="flex flex-col gap-3 bg-background p-6"
              >
                <span className="grid size-9 place-items-center rounded-md border border-border bg-muted/40">
                  <feature.icon aria-hidden className="size-4" />
                </span>
                <h3 className="text-lg font-medium">{feature.title}</h3>
                <p className="text-sm text-muted-foreground">{feature.body}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Pricing teaser */}
      <section className="border-b border-border/60">
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <div className="rounded-2xl border border-border bg-foreground/[0.02] p-8 sm:p-12">
            <div className="flex flex-col items-start gap-6 md:flex-row md:items-end md:justify-between">
              <div className="max-w-xl space-y-3">
                <p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
                  Pricing
                </p>
                <h2 className="text-3xl font-light tracking-tight sm:text-4xl">
                  Free forever for side projects. Pay only when you scale.
                </h2>
                <p className="text-muted-foreground">
                  Free covers 100 queries per month and 50 documents. Pro lifts
                  the caps and unlocks premium model tiers. Enterprise adds
                  SSO, audit logs, and a dedicated VPC.
                </p>
              </div>
              <Button asChild size="lg" className="h-11">
                <Link href="/pricing">
                  Compare plans
                  <ArrowRightIcon aria-hidden className="ml-1.5" />
                </Link>
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="scroll-mt-20 border-b border-border/60 bg-muted/20">
        <div className="mx-auto max-w-3xl px-4 py-20 sm:px-6">
          <div className="mb-10 space-y-3">
            <p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
              Frequently asked
            </p>
            <h2 className="text-3xl font-light tracking-tight sm:text-4xl">
              Answers to the questions we hear most.
            </h2>
          </div>
          <ul className="space-y-3">
            {FAQS.map((faq) => (
              <li
                key={faq.q}
                className="overflow-hidden rounded-xl border border-border bg-background"
              >
                <details className="group">
                  <summary className="flex cursor-pointer items-center justify-between gap-4 px-5 py-4 text-left text-base font-medium [&::-webkit-details-marker]:hidden">
                    {faq.q}
                    <span
                      aria-hidden
                      className="grid size-6 shrink-0 place-items-center rounded-full border border-border text-muted-foreground transition-transform group-open:rotate-45"
                    >
                      +
                    </span>
                  </summary>
                  <div className="border-t border-border/70 px-5 py-4 text-sm text-muted-foreground">
                    {faq.a}
                  </div>
                </details>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Final CTA */}
      <section>
        <div className="mx-auto max-w-4xl px-4 py-20 text-center sm:px-6">
          <h2 className="text-3xl font-light tracking-tight sm:text-4xl">
            Your docs deserve a better front door.
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-muted-foreground">
            Spin up a tenant, upload a PDF, paste the script tag. You can
            measure the difference in five minutes.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button asChild size="lg" className="h-11 px-5">
              <Link href="/signup">Get started free</Link>
            </Button>
            <Button asChild variant="outline" size="lg" className="h-11 px-5">
              <Link href="/login">I already have an account</Link>
            </Button>
          </div>
        </div>
      </section>
    </>
  );
}
