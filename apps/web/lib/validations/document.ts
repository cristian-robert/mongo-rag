import { z } from "zod/v3";

export const MAX_UPLOAD_BYTES = 50 * 1024 * 1024; // 50 MB

export const ACCEPTED_EXTENSIONS = [
  "pdf",
  "txt",
  "md",
  "markdown",
  "docx",
  "doc",
  "pptx",
  "ppt",
  "xlsx",
  "xls",
  "html",
  "htm",
] as const;

export const ACCEPT_ATTRIBUTE = ACCEPTED_EXTENSIONS.map((e) => `.${e}`).join(
  ",",
);

export function isAcceptedExtension(filename: string): boolean {
  const idx = filename.lastIndexOf(".");
  if (idx === -1) return false;
  const ext = filename.slice(idx + 1).toLowerCase();
  return (ACCEPTED_EXTENSIONS as readonly string[]).includes(ext);
}

export const documentMetaSchema = z.object({
  title: z
    .string()
    .trim()
    .min(1, "Title is required")
    .max(200, "Title is too long"),
  metadataJson: z
    .string()
    .trim()
    .optional()
    .refine(
      (v) => {
        if (!v) return true;
        try {
          const parsed = JSON.parse(v);
          return (
            parsed !== null &&
            typeof parsed === "object" &&
            !Array.isArray(parsed)
          );
        } catch {
          return false;
        }
      },
      { message: "Must be a valid JSON object" },
    ),
});

export type DocumentMetaFormData = z.infer<typeof documentMetaSchema>;
