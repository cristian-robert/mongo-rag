"use client";

import { useCallback, useEffect, useState, useTransition } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { SearchIcon } from "lucide-react";

import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const STATUS_OPTIONS = [
  { value: "all", label: "All statuses" },
  { value: "ready", label: "Ready" },
  { value: "processing", label: "Processing" },
  { value: "pending", label: "Pending" },
  { value: "failed", label: "Failed" },
] as const;

const SORT_OPTIONS = [
  { value: "created_at:desc", label: "Newest first" },
  { value: "created_at:asc", label: "Oldest first" },
  { value: "title:asc", label: "Title A→Z" },
  { value: "title:desc", label: "Title Z→A" },
  { value: "status:asc", label: "Status" },
] as const;

export function DocumentsToolbar() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [search, setSearch] = useState(params.get("search") ?? "");
  const [, startTransition] = useTransition();

  const replaceParam = useCallback(
    (mutator: (sp: URLSearchParams) => void) => {
      const sp = new URLSearchParams(params.toString());
      mutator(sp);
      sp.delete("page"); // reset paging when filters change
      startTransition(() => {
        const qs = sp.toString();
        router.replace(qs ? `${pathname}?${qs}` : pathname);
      });
    },
    [params, pathname, router],
  );

  useEffect(() => {
    const t = setTimeout(() => {
      const current = params.get("search") ?? "";
      if (search.trim() !== current) {
        replaceParam((sp) => {
          if (search.trim()) sp.set("search", search.trim());
          else sp.delete("search");
        });
      }
    }, 300);
    return () => clearTimeout(t);
  }, [search, params, replaceParam]);

  const status = params.get("status") ?? "all";
  const sort = params.get("sort") ?? "created_at";
  const order = params.get("order") ?? "desc";
  const sortValue = `${sort}:${order}`;

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
      <label className="relative flex-1 max-w-sm">
        <span className="sr-only">Search documents</span>
        <SearchIcon className="pointer-events-none absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by title…"
          className="pl-7"
          autoComplete="off"
        />
      </label>
      <div className="flex items-center gap-2">
        <Select
          value={status}
          onValueChange={(v) =>
            replaceParam((sp) => {
              if (v === "all") sp.delete("status");
              else sp.set("status", v as string);
            })
          }
        >
          <SelectTrigger className="w-36" aria-label="Filter by status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={sortValue}
          onValueChange={(v) => {
            const [s, o] = (v as string).split(":");
            replaceParam((sp) => {
              sp.set("sort", s);
              sp.set("order", o);
            });
          }}
        >
          <SelectTrigger className="w-40" aria-label="Sort documents">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SORT_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
