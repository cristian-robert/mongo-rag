"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  MoreHorizontalIcon,
  PencilIcon,
  RefreshCwIcon,
  Trash2Icon,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface Props {
  documentId: string;
  documentTitle: string;
}

export function DocumentRowActions({ documentId, documentTitle }: Props) {
  const router = useRouter();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [isPending, startTransition] = useTransition();
  const [confirmInput, setConfirmInput] = useState("");

  function handleDelete() {
    startTransition(async () => {
      try {
        const res = await fetch(
          `/api/documents/${encodeURIComponent(documentId)}`,
          { method: "DELETE" },
        );
        if (!res.ok) {
          const body = (await res.json().catch(() => ({}))) as {
            error?: string;
          };
          toast.error(body.error ?? "Delete failed");
          return;
        }
        toast.success("Document deleted");
        setConfirmOpen(false);
        setConfirmInput("");
        router.refresh();
      } catch {
        toast.error("Network error");
      }
    });
  }

  function handleReingest() {
    startTransition(async () => {
      try {
        const res = await fetch(
          `/api/documents/${encodeURIComponent(documentId)}/reingest`,
          { method: "POST" },
        );
        if (!res.ok) {
          const body = (await res.json().catch(() => ({}))) as {
            error?: string;
          };
          toast.error(body.error ?? "Re-ingest failed");
          return;
        }
        toast.success("Re-ingest queued");
        router.refresh();
      } catch {
        toast.error("Network error");
      }
    });
  }

  const confirmRequired = "delete";
  const canConfirm = confirmInput.trim().toLowerCase() === confirmRequired;

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          render={(props) => (
            <Button
              {...props}
              variant="ghost"
              size="icon-sm"
              aria-label={`Actions for ${documentTitle}`}
            >
              <MoreHorizontalIcon className="size-4" />
            </Button>
          )}
        />
        <DropdownMenuContent>
          <DropdownMenuItem
            render={(props) => (
              <Link
                {...props}
                href={`/dashboard/documents/${encodeURIComponent(documentId)}`}
              >
                <PencilIcon className="size-3.5" />
                <span>Edit metadata</span>
              </Link>
            )}
          />
          <DropdownMenuItem onClick={handleReingest} disabled={isPending}>
            <RefreshCwIcon className="size-3.5" />
            <span>Re-ingest</span>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onClick={() => setConfirmOpen(true)}
            variant="destructive"
          >
            <Trash2Icon className="size-3.5" />
            <span>Delete…</span>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete document</DialogTitle>
            <DialogDescription>
              <span className="block">
                This permanently removes{" "}
                <span className="font-medium text-foreground">
                  {documentTitle}
                </span>{" "}
                and all of its chunks and embeddings. This cannot be undone.
              </span>
              <span className="mt-3 block">
                Type{" "}
                <code className="rounded bg-muted px-1 py-0.5 text-foreground">
                  delete
                </code>{" "}
                to confirm.
              </span>
            </DialogDescription>
          </DialogHeader>
          <input
            type="text"
            value={confirmInput}
            onChange={(e) => setConfirmInput(e.target.value)}
            placeholder="delete"
            aria-label="Type 'delete' to confirm"
            className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            autoFocus
          />
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setConfirmOpen(false)}
              disabled={isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={!canConfirm || isPending}
            >
              {isPending ? "Deleting…" : "Delete forever"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
