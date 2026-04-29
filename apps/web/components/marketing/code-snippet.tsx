const SNIPPET_LINES: { kind: "tag" | "attr" | "value" | "text"; text: string }[][] = [
  [
    { kind: "text", text: "<!-- Drop this on any page -->" },
  ],
  [
    { kind: "tag", text: "<script" },
    { kind: "text", text: " " },
    { kind: "attr", text: "src" },
    { kind: "text", text: "=" },
    { kind: "value", text: '"https://cdn.mongorag.dev/widget.js"' },
  ],
  [
    { kind: "text", text: "        " },
    { kind: "attr", text: "data-bot" },
    { kind: "text", text: "=" },
    { kind: "value", text: '"bot_7Hc3p2"' },
  ],
  [
    { kind: "text", text: "        " },
    { kind: "attr", text: "data-key" },
    { kind: "text", text: "=" },
    { kind: "value", text: '"mr_pk_xxxxxxxx"' },
    { kind: "tag", text: "></script>" },
  ],
];

const COLOR_BY_KIND: Record<string, string> = {
  tag: "text-foreground",
  attr: "text-blue-600 dark:text-blue-400",
  value: "text-emerald-700 dark:text-emerald-400",
  text: "text-muted-foreground",
};

export function CodeSnippet() {
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-foreground/[0.02] shadow-[0_1px_0_0_rgb(0_0_0_/_0.04)]">
      <div className="flex items-center justify-between border-b border-border/70 bg-muted/40 px-4 py-2">
        <div className="flex items-center gap-1.5">
          <span aria-hidden className="size-2.5 rounded-full bg-foreground/20" />
          <span aria-hidden className="size-2.5 rounded-full bg-foreground/15" />
          <span aria-hidden className="size-2.5 rounded-full bg-foreground/10" />
        </div>
        <span className="font-mono text-[0.7rem] uppercase tracking-wider text-muted-foreground">
          index.html
        </span>
      </div>
      <pre className="overflow-x-auto p-5 font-mono text-[0.82rem] leading-6">
        <code>
          {SNIPPET_LINES.map((line, idx) => (
            <span key={idx} className="block">
              {line.map((part, partIdx) => (
                <span key={partIdx} className={COLOR_BY_KIND[part.kind]}>
                  {part.text}
                </span>
              ))}
            </span>
          ))}
        </code>
      </pre>
    </div>
  );
}
