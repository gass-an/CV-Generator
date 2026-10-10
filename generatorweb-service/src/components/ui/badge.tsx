import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

type BadgeProps = ComponentProps<"span"> & {
  variant?: "default" | "muted" | "outline" | "accent";
};

const variants = {
  default: "bg-primary/10 text-primary",
  muted: "bg-muted text-muted-foreground",
  outline: "border-border bg-card text-muted-foreground border",
  accent: "bg-accent/10 text-accent",
} as const;

export function Badge({
  className,
  variant = "default",
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex w-fit items-center rounded-full px-2.5 py-1 text-xs font-semibold",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
