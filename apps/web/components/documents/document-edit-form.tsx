"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  documentMetaSchema,
  type DocumentMetaFormData,
} from "@/lib/validations/document";
import type { DocumentRecord } from "@/lib/api/documents";

interface Props {
  document: DocumentRecord;
}

export function DocumentEditForm({ document }: Props) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  const {
    register,
    handleSubmit,
    formState: { errors, isDirty },
    reset,
  } = useForm<DocumentMetaFormData>({
    resolver: zodResolver(documentMetaSchema),
    defaultValues: {
      title: document.title,
      metadataJson: Object.keys(document.metadata).length
        ? JSON.stringify(document.metadata, null, 2)
        : "",
    },
  });

  function onSubmit(data: DocumentMetaFormData) {
    startTransition(async () => {
      const payload: { title: string; metadata?: Record<string, unknown> } = {
        title: data.title,
      };
      if (data.metadataJson?.trim()) {
        try {
          payload.metadata = JSON.parse(data.metadataJson) as Record<
            string,
            unknown
          >;
        } catch {
          toast.error("Metadata must be a JSON object");
          return;
        }
      } else {
        payload.metadata = {};
      }

      try {
        const res = await fetch(
          `/api/documents/${encodeURIComponent(document.document_id)}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          },
        );
        if (!res.ok) {
          const body = (await res.json().catch(() => ({}))) as {
            error?: string;
            detail?: string;
          };
          toast.error(body.error ?? body.detail ?? "Update failed");
          return;
        }
        toast.success("Document updated");
        const updated = (await res.json()) as DocumentRecord;
        reset({
          title: updated.title,
          metadataJson: Object.keys(updated.metadata).length
            ? JSON.stringify(updated.metadata, null, 2)
            : "",
        });
        router.refresh();
      } catch {
        toast.error("Network error");
      }
    });
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <Label htmlFor="title">Title</Label>
        <Input
          id="title"
          {...register("title")}
          aria-invalid={!!errors.title}
          aria-describedby={errors.title ? "title-error" : undefined}
        />
        {errors.title && (
          <p id="title-error" className="text-sm text-destructive">
            {errors.title.message}
          </p>
        )}
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor="metadataJson">
          Metadata
          <span className="text-xs font-normal text-muted-foreground">
            JSON object — used as filters when searching
          </span>
        </Label>
        <Textarea
          id="metadataJson"
          rows={6}
          spellCheck={false}
          {...register("metadataJson")}
          placeholder={`{\n  "tags": ["onboarding", "policy"],\n  "owner": "ops"\n}`}
          className="font-mono text-xs"
          aria-invalid={!!errors.metadataJson}
          aria-describedby={
            errors.metadataJson ? "metadata-error" : undefined
          }
        />
        {errors.metadataJson && (
          <p id="metadata-error" className="text-sm text-destructive">
            {errors.metadataJson.message}
          </p>
        )}
      </div>

      <div className="flex justify-end gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={() =>
            reset({
              title: document.title,
              metadataJson: Object.keys(document.metadata).length
                ? JSON.stringify(document.metadata, null, 2)
                : "",
            })
          }
          disabled={!isDirty || isPending}
        >
          Reset
        </Button>
        <Button type="submit" disabled={!isDirty || isPending}>
          {isPending ? "Saving…" : "Save changes"}
        </Button>
      </div>
    </form>
  );
}
