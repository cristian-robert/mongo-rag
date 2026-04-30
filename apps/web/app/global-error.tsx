"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html>
      <body>
        <div
          style={{
            minHeight: "100vh",
            display: "grid",
            placeItems: "center",
            fontFamily: "system-ui, sans-serif",
            padding: "2rem",
          }}
        >
          <div style={{ maxWidth: 480 }}>
            <h1 style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: 8 }}>
              Something went wrong
            </h1>
            <p style={{ color: "#666", marginBottom: 16 }}>
              An unexpected error occurred. Please try again.
            </p>
            {error?.digest ? (
              <p style={{ color: "#999", fontSize: "0.75rem", marginBottom: 16 }}>
                Error ID: {error.digest}
              </p>
            ) : null}
            <button
              type="button"
              onClick={reset}
              style={{
                padding: "0.5rem 1rem",
                border: "1px solid #ccc",
                borderRadius: 6,
                background: "white",
                cursor: "pointer",
              }}
            >
              Try again
            </button>
          </div>
        </div>
      </body>
    </html>
  );
}
