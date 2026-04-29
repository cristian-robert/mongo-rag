import type { MetadataRoute } from "next";

function getBase(): string {
  return (
    process.env.NEXT_PUBLIC_SITE_URL ||
    process.env.NEXTAUTH_URL ||
    "http://localhost:3100"
  ).replace(/\/+$/, "");
}

export default function robots(): MetadataRoute.Robots {
  const base = getBase();
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/dashboard/", "/onboarding/", "/api/"],
      },
    ],
    sitemap: `${base}/sitemap.xml`,
  };
}
