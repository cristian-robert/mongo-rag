import type { Metadata } from "next";
import Link from "next/link";

import { BotForm } from "../bot-form";

export const metadata: Metadata = {
  title: "New bot — MongoRAG",
};

export const dynamic = "force-dynamic";

export default function NewBotPage() {
  return (
    <div className="mx-auto w-full max-w-3xl space-y-6 px-6 py-10">
      <header className="space-y-2">
        <Link
          href="/dashboard/bots"
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          ← Back to bots
        </Link>
        <h1 className="font-heading text-2xl leading-tight font-medium tracking-tight">
          New bot
        </h1>
        <p className="max-w-xl text-sm text-muted-foreground">
          Configure how the bot greets visitors, what documents it can search,
          and how the widget looks. You can change everything except the slug
          later.
        </p>
      </header>

      <BotForm mode="create" />
    </div>
  );
}
