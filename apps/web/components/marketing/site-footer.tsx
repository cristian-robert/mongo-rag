import Link from "next/link";

const COLUMNS = [
  {
    heading: "Product",
    links: [
      { href: "/#features", label: "Features" },
      { href: "/pricing", label: "Pricing" },
      { href: "/#how", label: "How it works" },
      { href: "/#faq", label: "FAQ" },
    ],
  },
  {
    heading: "Developers",
    links: [
      { href: "/docs", label: "Documentation" },
      { href: "/docs#api", label: "API reference" },
      { href: "/docs#widget", label: "Widget embed" },
    ],
  },
  {
    heading: "Company",
    links: [
      { href: "mailto:hello@mongorag.dev", label: "Contact" },
      { href: "/legal/terms", label: "Terms" },
      { href: "/legal/privacy", label: "Privacy" },
    ],
  },
];

export function SiteFooter() {
  return (
    <footer className="border-t border-border/60 bg-muted/20">
      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
        <div className="grid gap-8 md:grid-cols-4">
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <span
                aria-hidden
                className="grid size-6 place-items-center rounded-md border border-border bg-foreground/[0.04] font-mono text-[0.65rem] font-bold uppercase"
              >
                MR
              </span>
              MongoRAG
            </div>
            <p className="text-sm text-muted-foreground">
              Grounded answers for your customers — built on your own
              documentation.
            </p>
          </div>
          {COLUMNS.map((col) => (
            <div key={col.heading} className="space-y-3">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {col.heading}
              </h3>
              <ul className="space-y-2 text-sm">
                {col.links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="text-foreground/80 transition-colors hover:text-foreground"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-10 flex flex-col items-start justify-between gap-3 border-t border-border/60 pt-6 text-xs text-muted-foreground sm:flex-row sm:items-center">
          <p>© {new Date().getFullYear()} MongoRAG. All rights reserved.</p>
          <p className="font-mono uppercase tracking-wider">
            Built on MongoDB Atlas Vector Search
          </p>
        </div>
      </div>
    </footer>
  );
}
