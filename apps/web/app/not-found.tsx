import Link from "next/link";

export default function NotFound() {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        fontFamily: "system-ui, sans-serif",
        padding: "2rem",
      }}
    >
      <div style={{ maxWidth: 480, textAlign: "center" }}>
        <h1 style={{ fontSize: "1.5rem", fontWeight: 600, marginBottom: 8 }}>
          Page not found
        </h1>
        <p style={{ color: "#666", marginBottom: 16 }}>
          The page you are looking for does not exist.
        </p>
        <Link
          href="/"
          style={{
            display: "inline-block",
            padding: "0.5rem 1rem",
            border: "1px solid #ccc",
            borderRadius: 6,
            color: "inherit",
            textDecoration: "none",
          }}
        >
          Go home
        </Link>
      </div>
    </div>
  );
}
