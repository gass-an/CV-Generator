import type { LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type DocumentTypeCardProps = {
  icon: LucideIcon;
  title: string;
  description: string;
  accent: "blue" | "cyan" | "red";
  selected?: boolean;
  disabled?: boolean;
};

const accents = {
  blue: "bg-blue-50 text-blue-700 ring-blue-100",
  cyan: "bg-cyan-50 text-cyan-700 ring-cyan-100",
  red: "bg-red-50 text-red-700 ring-red-100",
} as const;

export function DocumentTypeCard({
  icon: Icon,
  title,
  description,
  accent,
  selected = false,
  disabled = true,
}: DocumentTypeCardProps) {
  return (
    <article
      className={cn(
        "border-border bg-card relative flex min-h-44 flex-col rounded-xl border p-4 shadow-sm transition-[border-color,box-shadow,transform] sm:p-5",
        selected && "border-primary ring-primary/15 ring-2",
        disabled
          ? "opacity-90"
          : "hover:border-primary/40 hover:-translate-y-0.5 hover:shadow-md",
      )}
      aria-disabled={disabled || undefined}
    >
      <div
        className={cn(
          "flex size-10 items-center justify-center rounded-xl ring-1",
          accents[accent],
        )}
      >
        <Icon className="size-5" aria-hidden="true" />
      </div>
      <h3 className="mt-4 font-semibold">{title}</h3>
      <p className="text-muted-foreground mt-1.5 flex-1 text-sm leading-6">
        {description}
      </p>
      {disabled ? (
        <Badge variant="muted" className="mt-4">
          Bientôt disponible
        </Badge>
      ) : null}
    </article>
  );
}
