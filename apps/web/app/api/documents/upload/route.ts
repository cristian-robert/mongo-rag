import { NextResponse } from "next/server";

import { mintBackendToken } from "@/lib/api/token";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8100";

const MAX_BYTES = 50 * 1024 * 1024; // 50 MB
const ACCEPTED_EXTENSIONS = new Set([
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
]);

const ACCEPTED_MIME_PREFIXES = [
  "application/pdf",
  "text/plain",
  "text/markdown",
  "text/html",
  "application/vnd.openxmlformats-officedocument",
  "application/msword",
  "application/vnd.ms-",
];

function extOf(name: string): string {
  const idx = name.lastIndexOf(".");
  return idx === -1 ? "" : name.slice(idx + 1).toLowerCase();
}

function isAcceptedMime(mime: string): boolean {
  if (!mime) return true; // browsers sometimes omit; rely on extension
  return ACCEPTED_MIME_PREFIXES.some((p) => mime.startsWith(p));
}

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const minted = await mintBackendToken();
  if (!minted) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const incoming = await request.formData();
  const file = incoming.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json(
      { error: "Missing file in form data" },
      { status: 400 },
    );
  }

  const ext = extOf(file.name);
  if (!ACCEPTED_EXTENSIONS.has(ext)) {
    return NextResponse.json(
      { error: `Unsupported file extension: .${ext || "unknown"}` },
      { status: 415 },
    );
  }

  if (!isAcceptedMime(file.type)) {
    return NextResponse.json(
      { error: `Unsupported MIME type: ${file.type}` },
      { status: 415 },
    );
  }

  if (file.size > MAX_BYTES) {
    return NextResponse.json(
      {
        error: `File too large. Maximum is ${MAX_BYTES / 1024 / 1024}MB`,
      },
      { status: 413 },
    );
  }

  // Forward as multipart/form-data — let undici build a fresh boundary.
  const forwarded = new FormData();
  forwarded.append("file", file, file.name);
  const title = incoming.get("title");
  if (typeof title === "string" && title.trim()) {
    forwarded.append("title", title.trim());
  }
  const metadata = incoming.get("metadata");
  if (typeof metadata === "string" && metadata.trim()) {
    forwarded.append("metadata", metadata.trim());
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_URL}/api/v1/documents/ingest`, {
      method: "POST",
      headers: { Authorization: `Bearer ${minted.token}` },
      body: forwarded,
    });
  } catch (err) {
    console.error("[documents/upload] upstream fetch failed", {
      tenantId: minted.tenantId,
      filename: file.name,
      err: err instanceof Error ? err.message : String(err),
    });
    return NextResponse.json(
      { error: "Upload service unavailable" },
      { status: 502 },
    );
  }

  if (!upstream.ok) {
    console.warn("[documents/upload] upstream rejected", {
      tenantId: minted.tenantId,
      filename: file.name,
      status: upstream.status,
    });
  }

  const text = await upstream.text();
  return new NextResponse(text, {
    status: upstream.status,
    headers: {
      "Content-Type":
        upstream.headers.get("Content-Type") ?? "application/json",
    },
  });
}
