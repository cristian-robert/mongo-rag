"use client";

import * as React from "react";
import { Menu as MenuPrimitive } from "@base-ui/react/menu";

import { cn } from "@/lib/utils";

const DropdownMenu = MenuPrimitive.Root;
const DropdownMenuTrigger = MenuPrimitive.Trigger;
const DropdownMenuPortal = MenuPrimitive.Portal;

function DropdownMenuContent({
  className,
  sideOffset = 4,
  align = "end",
  ...props
}: React.ComponentProps<typeof MenuPrimitive.Popup> & {
  sideOffset?: number;
  align?: "start" | "center" | "end";
}) {
  return (
    <DropdownMenuPortal>
      <MenuPrimitive.Positioner sideOffset={sideOffset} align={align}>
        <MenuPrimitive.Popup
          className={cn(
            "z-50 min-w-[10rem] overflow-hidden rounded-lg border border-border/60 bg-popover p-1 text-popover-foreground shadow-lg outline-none",
            "data-[starting-style]:scale-95 data-[starting-style]:opacity-0 data-[ending-style]:opacity-0 transition-all duration-150",
            className,
          )}
          {...props}
        />
      </MenuPrimitive.Positioner>
    </DropdownMenuPortal>
  );
}

function DropdownMenuItem({
  className,
  variant = "default",
  ...props
}: React.ComponentProps<typeof MenuPrimitive.Item> & {
  variant?: "default" | "destructive";
}) {
  return (
    <MenuPrimitive.Item
      className={cn(
        "relative flex cursor-pointer select-none items-center gap-2 rounded-md px-2 py-1.5 text-sm outline-none transition-colors",
        "data-[highlighted]:bg-muted data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
        variant === "destructive" &&
          "text-destructive data-[highlighted]:bg-destructive/10",
        className,
      )}
      {...props}
    />
  );
}

function DropdownMenuSeparator({
  className,
  ...props
}: React.ComponentProps<typeof MenuPrimitive.Separator>) {
  return (
    <MenuPrimitive.Separator
      className={cn("-mx-1 my-1 h-px bg-border/60", className)}
      {...props}
    />
  );
}

export {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
};
