import type { NextConfig } from "next";

const isProd = process.env.NODE_ENV === "production";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8100";

/**
 * Build a Content-Security-Policy header.
 *
 * - Dashboard CSP locks `frame-ancestors` to none and constrains scripts to
 *   first-party + Stripe.
 * - In dev we allow `'unsafe-eval'` and `'unsafe-inline'` so React Refresh
 *   and Next.js HMR work; production scripts are tightly constrained.
 * - Inline styles are required by the Geist fonts loader and Tailwind
 *   in some cases — kept until we move to a nonce-based pipeline.
 */
function buildCsp(): string {
  const apiOrigin = (() => {
    try {
      return new URL(apiUrl).origin;
    } catch {
      return "http://localhost:8100";
    }
  })();

  const scriptSrc = isProd
    ? ["'self'", "https://js.stripe.com", "https://checkout.stripe.com"]
    : [
        "'self'",
        "'unsafe-inline'",
        "'unsafe-eval'",
        "https://js.stripe.com",
        "https://checkout.stripe.com",
      ];

  const directives: Record<string, string[]> = {
    "default-src": ["'self'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'", "https://checkout.stripe.com"],
    "frame-ancestors": ["'none'"],
    "object-src": ["'none'"],
    "img-src": ["'self'", "data:", "blob:", "https:"],
    "font-src": ["'self'", "data:", "https://fonts.gstatic.com"],
    "style-src": [
      "'self'",
      "'unsafe-inline'",
      "https://fonts.googleapis.com",
    ],
    "script-src": scriptSrc,
    "connect-src": [
      "'self'",
      apiOrigin,
      "https://api.stripe.com",
      "https://checkout.stripe.com",
      ...(isProd ? [] : ["ws:", "wss:"]),
    ],
    "frame-src": [
      "'self'",
      "https://js.stripe.com",
      "https://checkout.stripe.com",
    ],
    "worker-src": ["'self'", "blob:"],
    "manifest-src": ["'self'"],
  };

  if (isProd) {
    directives["upgrade-insecure-requests"] = [];
  }

  return Object.entries(directives)
    .map(([key, values]) => (values.length ? `${key} ${values.join(" ")}` : key))
    .join("; ");
}

const securityHeaders = [
  { key: "Content-Security-Policy", value: buildCsp() },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "geolocation=(), microphone=(), camera=(), payment=(self)",
  },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  { key: "Cross-Origin-Resource-Policy", value: "same-site" },
  ...(isProd
    ? [
        {
          key: "Strict-Transport-Security",
          value: "max-age=63072000; includeSubDomains; preload",
        },
      ]
    : []),
];

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
