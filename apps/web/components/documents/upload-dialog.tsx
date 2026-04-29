"use client";

import { useCallback, useId, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { CloudUploadIcon, FileIcon, XIcon } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import {
  ACCEPT_ATTRIBUTE,
  MAX_UPLOAD_BYTES,
  isAcceptedExtension,
} from "@/lib/validations/document";

interface QueuedFile {
  id: string;
  file: File;
  state: "queued" | "uploading" | "done" | "error";
  error?: string;
}

interface UploadResponse {
  document_id?: string;
  detail?: string;
  error?: string;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function DocumentUploadDialog({
  trigger,
}: {
  trigger?: React.ReactNode;
}) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<QueuedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const dropZoneId = useId();

  const validateAndAdd = useCallback((files: FileList | File[]) => {
    const next: QueuedFile[] = [];
    for (const file of Array.from(files)) {
      if (!isAcceptedExtension(file.name)) {
        toast.error(`Unsupported file type: ${file.name}`);
        continue;
      }
      if (file.size > MAX_UPLOAD_BYTES) {
        toast.error(
          `${file.name} is too large (max ${MAX_UPLOAD_BYTES / 1024 / 1024} MB)`,
        );
        continue;
      }
      next.push({
        id: `${file.name}-${file.size}-${Date.now()}-${Math.random()}`,
        file,
        state: "queued",
      });
    }
    if (next.length) {
      setItems((prev) => [...prev, ...next]);
    }
  }, []);

  function handleFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files) {
      validateAndAdd(e.target.files);
      e.target.value = "";
    }
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files?.length) {
      validateAndAdd(e.dataTransfer.files);
    }
  }

  function removeItem(id: string) {
    setItems((prev) => prev.filter((it) => it.id !== id));
  }

  async function uploadOne(item: QueuedFile): Promise<boolean> {
    const fd = new FormData();
    fd.append("file", item.file);
    try {
      const res = await fetch("/api/documents/upload", {
        method: "POST",
        body: fd,
      });
      const json = (await res.json().catch(() => ({}))) as UploadResponse;
      if (!res.ok) {
        const msg = json.error ?? json.detail ?? `Upload failed (${res.status})`;
        setItems((prev) =>
          prev.map((it) =>
            it.id === item.id ? { ...it, state: "error", error: msg } : it,
          ),
        );
        return false;
      }
      setItems((prev) =>
        prev.map((it) =>
          it.id === item.id ? { ...it, state: "done" } : it,
        ),
      );
      return true;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      setItems((prev) =>
        prev.map((it) =>
          it.id === item.id ? { ...it, state: "error", error: msg } : it,
        ),
      );
      return false;
    }
  }

  async function handleUploadAll() {
    if (!items.length) return;
    setIsUploading(true);
    setItems((prev) =>
      prev.map((it) =>
        it.state === "queued" ? { ...it, state: "uploading" } : it,
      ),
    );
    let successes = 0;
    for (const item of items) {
      if (item.state === "done") {
        successes += 1;
        continue;
      }
      const ok = await uploadOne({ ...item, state: "uploading" });
      if (ok) successes += 1;
    }
    setIsUploading(false);
    if (successes > 0) {
      toast.success(
        `${successes} document${successes === 1 ? "" : "s"} queued for processing`,
      );
      router.refresh();
    }
  }

  function handleClose(next: boolean) {
    if (isUploading) return;
    setOpen(next);
    if (!next) {
      setItems([]);
    }
  }

  const hasErrors = items.some((it) => it.state === "error");
  const allDone =
    items.length > 0 && items.every((it) => it.state === "done");

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogTrigger
        render={(props) => (trigger ? <span {...props}>{trigger}</span> : (
          <Button {...props}>
            <CloudUploadIcon className="size-4" />
            Upload document
          </Button>
        ))}
      />
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Upload documents</DialogTitle>
          <DialogDescription>
            Drop files or browse. PDF, DOCX, PPTX, XLSX, HTML, TXT, and Markdown
            are supported. Max {MAX_UPLOAD_BYTES / 1024 / 1024} MB per file.
          </DialogDescription>
        </DialogHeader>

        <div
          aria-labelledby={dropZoneId}
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          className={cn(
            "flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border/60 px-6 py-8 text-center transition-colors",
            isDragging && "border-primary/60 bg-primary/5",
          )}
        >
          <CloudUploadIcon className="size-7 text-muted-foreground" />
          <p id={dropZoneId} className="text-sm font-medium">
            Drop files here
          </p>
          <p className="text-xs text-muted-foreground">or</p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => inputRef.current?.click()}
          >
            Browse files
          </Button>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept={ACCEPT_ATTRIBUTE}
            onChange={handleFileInput}
            className="sr-only"
            aria-label="Choose documents to upload"
          />
        </div>

        {items.length > 0 && (
          <ul className="mt-4 flex max-h-56 flex-col gap-1 overflow-y-auto">
            {items.map((it) => (
              <li
                key={it.id}
                className="flex items-center gap-2 rounded-md border border-border/40 bg-card/50 px-2 py-1.5 text-sm"
              >
                <FileIcon className="size-3.5 shrink-0 text-muted-foreground" />
                <span className="flex-1 truncate" title={it.file.name}>
                  {it.file.name}
                </span>
                <span className="text-xs text-muted-foreground tabular-nums">
                  {formatBytes(it.file.size)}
                </span>
                <span
                  className={cn(
                    "text-xs",
                    it.state === "done" && "text-emerald-600 dark:text-emerald-400",
                    it.state === "error" && "text-destructive",
                    it.state === "uploading" && "text-sky-600 dark:text-sky-400",
                  )}
                >
                  {it.state === "queued"
                    ? "Ready"
                    : it.state === "uploading"
                      ? "Uploading…"
                      : it.state === "done"
                        ? "Queued"
                        : "Failed"}
                </span>
                {!isUploading && it.state !== "done" && (
                  <button
                    type="button"
                    onClick={() => removeItem(it.id)}
                    className="text-muted-foreground hover:text-destructive transition-colors"
                    aria-label={`Remove ${it.file.name}`}
                  >
                    <XIcon className="size-3.5" />
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}

        {hasErrors && (
          <p className="mt-2 text-xs text-destructive">
            Some files failed. Hover the row for details.
          </p>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleClose(false)}
            disabled={isUploading}
          >
            {allDone ? "Close" : "Cancel"}
          </Button>
          <Button
            onClick={handleUploadAll}
            disabled={
              isUploading ||
              items.length === 0 ||
              items.every((it) => it.state === "done")
            }
          >
            {isUploading
              ? "Uploading…"
              : allDone
                ? "Done"
                : `Upload ${items.length} ${items.length === 1 ? "file" : "files"}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
