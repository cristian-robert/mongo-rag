import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { ApiError } from "@/lib/api-client";
import { getBot } from "@/lib/bots";

import { BotForm } from "../bot-form";
import { EmbedSnippet } from "../embed-snippet";

export const metadata: Metadata = {
  title: "Edit bot — MongoRAG",
};

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function EditBotPage({ params }: Props) {
  const { id } = await params;

  let bot;
  try {
    bot = await getBot(id);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      notFound();
    }
    throw err;
  }

  return (
    <div className="mx-auto w-full max-w-3xl space-y-8 px-6 py-10">
      <header className="space-y-2">
        <Link
          href="/dashboard/bots"
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          ← Back to bots
        </Link>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="font-heading text-2xl leading-tight font-medium tracking-tight">
            {bot.name}
          </h1>
          {bot.is_public ? (
            <Badge variant="success">Public</Badge>
          ) : (
            <Badge variant="muted">Private</Badge>
          )}
        </div>
        <p className="max-w-xl text-sm text-muted-foreground">
          Slug{" "}
          <code className="rounded-md bg-muted px-1 py-0.5 font-mono text-xs">
            {bot.slug}
          </code>{" "}
          — used by the embed snippet below.
        </p>
      </header>

      <section className="rounded-xl border border-border/60 bg-card p-5">
        <EmbedSnippet botId={bot.id} />
      </section>

      <BotForm mode="edit" bot={bot} />
    </div>
  );
}
