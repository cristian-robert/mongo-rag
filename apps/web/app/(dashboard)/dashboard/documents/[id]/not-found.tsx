import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function DocumentNotFound() {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 px-4 py-20 text-center">
      <p className="font-mono text-xs uppercase tracking-[0.18em] text-muted-foreground">
        404
      </p>
      <h1 className="font-heading text-2xl tracking-tight">
        Document not found
      </h1>
      <p className="text-sm text-muted-foreground">
        It may have been deleted, or you may not have permission to view it.
      </p>
      <Button render={(props) => <Link {...props} href="/dashboard/documents" />}>
        Back to documents
      </Button>
    </div>
  );
}
