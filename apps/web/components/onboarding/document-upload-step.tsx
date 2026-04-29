"use client";

import {
  ArrowRightIcon,
  CheckCircle2Icon,
  CloudUploadIcon,
  FileIcon,
  XIcon,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useId, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  ACCEPT_ATTRIBUTE,
  MAX_UPLOAD_BYTES,
  isAcceptedExtension,
} from "@/lib/validations/document";

type Status = "idle" | "uploading" | "done" | "error";

interface UploadedDoc {
  id: string;
  name: string;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function DocumentUploadStep() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const dropZoneId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [uploaded, setUploaded] = useState<UploadedDoc | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const validate = useCallback((candidate: File): string | null => {
    if (!isAcceptedExtension(candidate.name)) {
      return `Unsupported file type: ${candidate.name}`;
    }
    if (candidate.size > MAX_UPLOAD_BYTES) {
      return `File is too large (max ${MAX_UPLOAD_BYTES / 1024 / 1024} MB).`;
    }
    return null;
  }, []);

  const onPick = useCallback(
    (next: File | undefined | null) => {
      if (!next) return;
      const err = validate(next);
      if (err) {
        toast.error(err);
        return;
      }
      setFile(next);
      setStatus("idle");
      setError(null);
      setUploaded(null);
    },
    [validate],
  );

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragging(false);
    const candidate = e.dataTransfer.files?.[0];
    if (candidate) onPick(candidate);
  }

  async function startUpload() {
    if (!file) return;
    setStatus("uploading");
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", file, file.name);
      const res = await fetch("/api/documents/upload", {
        method: "POST",
        body: formData,
      });
      const text = await res.text();
      let body: { document_id?: string; detail?: string; error?: string } = {};
      try {
        body = text ? JSON.parse(text) : {};
      } catch {
        // ignore — server returned non-JSON
      }

      if (!res.ok || !body.document_id) {
        const message =
          body.detail ?? body.error ?? `Upload failed (${res.status})`;
        setStatus("error");
        setError(message);
        toast.error(message);
        return;
      }

      setUploaded({ id: body.document_id, name: file.name });
      setStatus("done");
      toast.success("Uploaded — indexing in the background.");
      router.refresh();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Upload failed unexpectedly";
      setStatus("error");
      setError(message);
      toast.error(message);
    }
  }

  function clearFile() {
    setFile(null);
    setStatus("idle");
    setError(null);
    setUploaded(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  const isUploading = status === "uploading";
  const isDone = status === "done";

  return (
    <div className="space-y-5">
      <div
        id={dropZoneId}
        role="button"
        tabIndex={0}
        aria-label="Upload a document"
        aria-disabled={isUploading || isDone}
        onClick={() => {
          if (!isUploading && !isDone) inputRef.current?.click();
        }}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !isUploading && !isDone) {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!isUploading && !isDone) setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-border bg-background px-6 py-12 text-center transition-colors",
          "focus:outline-none focus-visible:border-foreground focus-visible:ring-2 focus-visible:ring-foreground/20",
          isDragging && "border-foreground bg-muted/40",
          (isUploading || isDone) && "cursor-default opacity-90",
        )}
      >
        <span
          aria-hidden
          className="grid size-10 place-items-center rounded-md border border-border bg-muted/40"
        >
          <CloudUploadIcon className="size-5" />
        </span>
        <div className="space-y-1">
          <p className="text-sm font-medium">
            {isDragging
              ? "Drop to upload"
              : "Drop a file here, or click to browse"}
          </p>
          <p className="text-xs text-muted-foreground">
            PDF, DOCX, MD, HTML, PPTX, XLSX — up to{" "}
            {MAX_UPLOAD_BYTES / 1024 / 1024} MB
          </p>
        </div>
        <input
          ref={inputRef}
          type="file"
          className="sr-only"
          accept={ACCEPT_ATTRIBUTE}
          onChange={(e) => onPick(e.target.files?.[0] ?? null)}
        />
      </div>

      {file ? (
        <div
          role="status"
          aria-live="polite"
          className="flex items-center justify-between gap-3 rounded-lg border border-border bg-muted/20 px-4 py-3"
        >
          <div className="flex min-w-0 items-center gap-3">
            <span
              aria-hidden
              className="grid size-9 shrink-0 place-items-center rounded-md border border-border bg-background"
            >
              {isDone ? (
                <CheckCircle2Icon className="size-4 text-emerald-600 dark:text-emerald-400" />
              ) : (
                <FileIcon className="size-4" />
              )}
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{file.name}</p>
              <p className="text-xs text-muted-foreground">
                {formatBytes(file.size)}
                {isUploading ? " · uploading…" : ""}
                {isDone && uploaded ? ` · queued (${uploaded.id.slice(0, 8)}…)` : ""}
                {error ? ` · ${error}` : ""}
              </p>
            </div>
          </div>
          {!isUploading ? (
            <Button
              variant="ghost"
              size="icon"
              aria-label="Remove file"
              onClick={clearFile}
              type="button"
            >
              <XIcon className="size-4" aria-hidden />
            </Button>
          ) : null}
        </div>
      ) : null}

      <div className="flex flex-col-reverse items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Button asChild variant="ghost" type="button">
          <Link href="/onboarding/api-key">Skip for now</Link>
        </Button>
        <div className="flex flex-col items-stretch gap-2 sm:flex-row sm:items-center">
          {!isDone ? (
            <Button
              type="button"
              onClick={startUpload}
              disabled={!file || isUploading}
              size="lg"
              className="h-11"
            >
              {isUploading ? "Uploading…" : "Upload document"}
            </Button>
          ) : (
            <Button asChild size="lg" className="h-11">
              <Link href="/onboarding/api-key">
                Continue
                <ArrowRightIcon aria-hidden className="ml-1.5" />
              </Link>
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
