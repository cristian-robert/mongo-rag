import { Suspense } from "react";

import { DocumentUploadDialog } from "@/components/documents/upload-dialog";
import { DocumentsPagination } from "@/components/documents/pagination";
import { DocumentsTable } from "@/components/documents/documents-table";
import { DocumentsToolbar } from "@/components/documents/documents-toolbar";
import {
  ApiError,
  listDocuments,
  type DocumentStatus,
  type ListDocumentsParams,
} from "@/lib/api/documents";

export const dynamic = "force-dynamic";

const DEFAULT_PAGE_SIZE = 25;

const VALID_STATUS = new Set<DocumentStatus>([
  "pending",
  "processing",
  "ready",
  "failed",
]);

function parseParams(
  raw: Record<string, string | string[] | undefined>,
): ListDocumentsParams {
  const page = Number(raw.page);
  const status = typeof raw.status === "string" ? raw.status : undefined;
  const sort = typeof raw.sort === "string" ? raw.sort : undefined;
  const order = typeof raw.order === "string" ? raw.order : undefined;
  const search = typeof raw.search === "string" ? raw.search : undefined;

  return {
    page: Number.isFinite(page) && page > 0 ? page : 1,
    pageSize: DEFAULT_PAGE_SIZE,
    status:
      status && VALID_STATUS.has(status as DocumentStatus)
        ? (status as DocumentStatus)
        : undefined,
    search: search?.trim() || undefined,
    sort:
      sort === "title" || sort === "status" || sort === "updated_at"
        ? sort
        : "created_at",
    order: order === "asc" ? "asc" : "desc",
  };
}

type LoadResult =
  | { ok: true; data: Awaited<ReturnType<typeof listDocuments>> }
  | { ok: false; message: string };

async function loadDocuments(
  params: ListDocumentsParams,
): Promise<LoadResult> {
  try {
    const data = await listDocuments(params);
    return { ok: true, data };
  } catch (err) {
    return {
      ok: false,
      message:
        err instanceof ApiError
          ? err.message
          : "Could not load documents. Please try again.",
    };
  }
}

async function DocumentsList({ params }: { params: ListDocumentsParams }) {
  const result = await loadDocuments(params);
  if (!result.ok) {
    return (
      <div
        role="alert"
        className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-6 text-sm text-destructive"
      >
        {result.message}
      </div>
    );
  }
  return (
    <>
      <DocumentsTable items={result.data.items} />
      <DocumentsPagination
        page={result.data.page}
        pageSize={result.data.page_size}
        total={result.data.total}
      />
    </>
  );
}

export default async function DocumentsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const raw = await searchParams;
  const params = parseParams(raw);

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 md:px-8 md:py-10">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
            Knowledge base
          </p>
          <h1 className="mt-1 font-heading text-2xl font-medium tracking-tight">
            Documents
          </h1>
          <p className="mt-1 max-w-prose text-sm text-muted-foreground">
            Upload, monitor, and manage the documents your bot answers from.
          </p>
        </div>
        <DocumentUploadDialog />
      </header>

      <DocumentsToolbar />

      <Suspense
        fallback={
          <div className="rounded-xl border border-border/40 bg-card/50 px-4 py-8 text-sm text-muted-foreground">
            Loading documents…
          </div>
        }
      >
        <DocumentsList params={params} />
      </Suspense>
    </div>
  );
}
