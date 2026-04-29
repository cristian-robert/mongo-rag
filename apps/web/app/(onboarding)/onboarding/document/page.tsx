import type { Metadata } from "next";

import { DocumentUploadStep } from "@/components/onboarding/document-upload-step";

export const metadata: Metadata = {
  title: "Upload your first document — MongoRAG",
  description: "Upload one document so your chatbot has something to talk about.",
};

export const dynamic = "force-dynamic";

export default function OnboardingDocumentPage() {
  return (
    <section aria-labelledby="onboarding-document" className="space-y-6">
      <header className="space-y-2">
        <p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
          Step 02 — First document
        </p>
        <h1
          id="onboarding-document"
          className="text-3xl font-light tracking-tight sm:text-4xl"
        >
          Give your bot something to talk about.
        </h1>
        <p className="max-w-prose text-muted-foreground">
          Upload a PDF, Markdown file, Word document, or HTML page. We&apos;ll
          chunk and embed it in the background — you can keep going without
          waiting.
        </p>
      </header>

      <DocumentUploadStep />
    </section>
  );
}
