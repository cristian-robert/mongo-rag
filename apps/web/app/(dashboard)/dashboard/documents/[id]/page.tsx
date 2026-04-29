import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeftIcon } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DocumentEditForm } from "@/components/documents/document-edit-form";
import { DocumentRowActions } from "@/components/documents/document-row-actions";
import { DocumentStatusBadge } from "@/components/documents/status-badge";
import { ApiError, getDocument } from "@/lib/api/documents";

export const dynamic = "force-dynamic";

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default async function DocumentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let doc;
  try {
    doc = await getDocument(id);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      notFound();
    }
    throw err;
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-6 md:px-8 md:py-10">
      <Link
        href="/dashboard/documents"
        className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeftIcon className="size-3.5" />
        All documents
      </Link>

      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
            Document
          </p>
          <h1
            className="mt-1 truncate font-heading text-2xl font-medium tracking-tight"
            title={doc.title}
          >
            {doc.title}
          </h1>
          <p
            className="mt-1 truncate text-sm text-muted-foreground"
            title={doc.source}
          >
            {doc.source}
          </p>
        </div>
        <DocumentRowActions
          documentId={doc.document_id}
          documentTitle={doc.title}
        />
      </div>

      <dl className="grid grid-cols-2 gap-4 rounded-xl border border-border/40 bg-card/50 p-4 sm:grid-cols-4">
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            Status
          </dt>
          <dd className="mt-1">
            <DocumentStatusBadge status={doc.status} />
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            Chunks
          </dt>
          <dd className="mt-1 tabular-nums">{doc.chunk_count}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            Format
          </dt>
          <dd className="mt-1 font-mono text-xs uppercase">
            {doc.format || "—"}
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            Uploaded
          </dt>
          <dd className="mt-1 text-sm">{formatDate(doc.created_at)}</dd>
        </div>
      </dl>

      {doc.status === "failed" && doc.error_message && (
        <div
          role="alert"
          className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive"
        >
          <p className="font-medium">Ingestion failed</p>
          <p className="mt-1 text-destructive/80">{doc.error_message}</p>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Metadata</CardTitle>
        </CardHeader>
        <CardContent>
          <DocumentEditForm document={doc} />
        </CardContent>
      </Card>
    </div>
  );
}
