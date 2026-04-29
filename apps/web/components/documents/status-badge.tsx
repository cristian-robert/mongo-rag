import { CheckIcon, CircleIcon, Loader2Icon, XIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { DocumentStatus } from "@/lib/api/documents";

const CONFIG: Record<
  DocumentStatus,
  {
    label: string;
    variant: "default" | "success" | "warning" | "destructive" | "info" | "muted";
    icon: React.ComponentType<{ className?: string }>;
    spin?: boolean;
  }
> = {
  pending: {
    label: "Pending",
    variant: "muted",
    icon: CircleIcon,
  },
  processing: {
    label: "Processing",
    variant: "info",
    icon: Loader2Icon,
    spin: true,
  },
  ready: {
    label: "Ready",
    variant: "success",
    icon: CheckIcon,
  },
  failed: {
    label: "Failed",
    variant: "destructive",
    icon: XIcon,
  },
  unknown: {
    label: "Unknown",
    variant: "muted",
    icon: CircleIcon,
  },
};

export function DocumentStatusBadge({ status }: { status: DocumentStatus }) {
  const cfg = CONFIG[status] ?? CONFIG.unknown;
  const Icon = cfg.icon;
  return (
    <Badge variant={cfg.variant} aria-label={`Status: ${cfg.label}`}>
      <Icon className={`size-3 ${cfg.spin ? "animate-spin" : ""}`} />
      <span>{cfg.label}</span>
    </Badge>
  );
}
