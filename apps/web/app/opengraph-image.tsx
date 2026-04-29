import { ImageResponse } from "next/og";

export const runtime = "nodejs";
export const alt = "MongoRAG — Grounded AI chat for your docs";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OgImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: 72,
          background: "#fafafa",
          backgroundImage:
            "radial-gradient(circle at 1px 1px, #d4d4d4 1px, transparent 0)",
          backgroundSize: "32px 32px",
          color: "#0a0a0a",
          fontFamily: "ui-sans-serif, system-ui, sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div
            style={{
              width: 44,
              height: 44,
              border: "1px solid #d4d4d4",
              borderRadius: 10,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: "ui-monospace, SFMono-Regular, monospace",
              fontWeight: 700,
              fontSize: 16,
              background: "#ffffff",
            }}
          >
            MR
          </div>
          <div style={{ fontSize: 28, fontWeight: 600 }}>MongoRAG</div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div
            style={{
              fontSize: 76,
              lineHeight: 1.05,
              letterSpacing: "-0.02em",
              fontWeight: 300,
              maxWidth: 1000,
            }}
          >
            Grounded AI chat for your docs.
          </div>
          <div style={{ fontSize: 28, color: "#525252", maxWidth: 900 }}>
            Upload, embed, ship — multi-tenant RAG on MongoDB Atlas.
          </div>
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontFamily: "ui-monospace, SFMono-Regular, monospace",
            fontSize: 18,
            color: "#737373",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
          }}
        >
          <span>mongorag.dev</span>
          <span>Free plan available</span>
        </div>
      </div>
    ),
    size,
  );
}
