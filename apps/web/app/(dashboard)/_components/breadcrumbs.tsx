"use client";

import { Fragment } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight } from "lucide-react";

const LABEL_OVERRIDES: Record<string, string> = {
  dashboard: "Overview",
  "api-keys": "API Keys",
};

function humanize(slug: string): string {
  if (LABEL_OVERRIDES[slug]) return LABEL_OVERRIDES[slug]!;
  return slug
    .split("-")
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(" ");
}

type Crumb = { href: string; label: string };

function buildCrumbs(pathname: string): Crumb[] {
  const segments = pathname.split("/").filter(Boolean);
  if (segments.length === 0 || segments[0] !== "dashboard") return [];

  const crumbs: Crumb[] = [];
  let acc = "";
  for (const seg of segments) {
    acc += `/${seg}`;
    crumbs.push({ href: acc, label: humanize(seg) });
  }
  return crumbs;
}

export function Breadcrumbs() {
  const pathname = usePathname();
  const crumbs = buildCrumbs(pathname);

  if (crumbs.length === 0) return null;

  return (
    <nav aria-label="Breadcrumb" className="hidden md:flex">
      <ol className="flex items-center gap-1 text-[0.8rem] text-muted-foreground">
        {crumbs.map((crumb, i) => {
          const isLast = i === crumbs.length - 1;
          return (
            <Fragment key={crumb.href}>
              <li>
                {isLast ? (
                  <span
                    aria-current="page"
                    className="font-medium text-foreground"
                  >
                    {crumb.label}
                  </span>
                ) : (
                  <Link
                    href={crumb.href}
                    className="rounded transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {crumb.label}
                  </Link>
                )}
              </li>
              {!isLast ? (
                <li aria-hidden="true" className="text-muted-foreground/60">
                  <ChevronRight className="size-3.5" />
                </li>
              ) : null}
            </Fragment>
          );
        })}
      </ol>
    </nav>
  );
}
