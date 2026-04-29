import Link from "next/link";

import {
  Table,
  TableBody,
  TableCell,
  TableEmpty,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { DocumentRecord } from "@/lib/api/documents";

import { DocumentRowActions } from "./document-row-actions";
import { DocumentStatusBadge } from "./status-badge";

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function formatSize(bytes: number | null): string {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function DocumentsTable({ items }: { items: DocumentRecord[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead className="w-24">Format</TableHead>
          <TableHead className="w-20 text-right">Chunks</TableHead>
          <TableHead className="w-28">Status</TableHead>
          <TableHead className="w-44">Uploaded</TableHead>
          <TableHead className="w-16" aria-label="Actions" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.length === 0 ? (
          <TableEmpty colSpan={6}>
            No documents yet. Upload one to get started.
          </TableEmpty>
        ) : (
          items.map((doc) => (
            <TableRow key={doc.document_id}>
              <TableCell className="max-w-[28ch]">
                <Link
                  href={`/dashboard/documents/${encodeURIComponent(doc.document_id)}`}
                  className="block truncate font-medium text-foreground hover:underline"
                  title={doc.title}
                >
                  {doc.title}
                </Link>
                <p
                  className="truncate text-xs text-muted-foreground"
                  title={doc.source}
                >
                  {doc.source}
                </p>
              </TableCell>
              <TableCell>
                <code className="rounded bg-muted px-1.5 py-0.5 text-[0.7rem] uppercase text-muted-foreground">
                  {doc.format || "—"}
                </code>
                <p className="mt-0.5 text-[0.7rem] text-muted-foreground">
                  {formatSize(doc.size_bytes)}
                </p>
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {doc.chunk_count}
              </TableCell>
              <TableCell>
                <DocumentStatusBadge status={doc.status} />
                {doc.error_message && doc.status === "failed" && (
                  <p
                    className="mt-1 max-w-[20ch] truncate text-[0.7rem] text-destructive"
                    title={doc.error_message}
                  >
                    {doc.error_message}
                  </p>
                )}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {formatDate(doc.created_at)}
              </TableCell>
              <TableCell className="text-right">
                <DocumentRowActions
                  documentId={doc.document_id}
                  documentTitle={doc.title}
                />
              </TableCell>
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  );
}
