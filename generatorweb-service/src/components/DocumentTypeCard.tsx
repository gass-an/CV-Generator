import { Check, type LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { DocumentType } from "@/types/document";

type DocumentTypeCardProps = {
  icon: LucideIcon;
  title: string;
  description: string;
  accent: "blue" | "cyan" | "red";
  value: DocumentType;
  selected?: boolean;
  disabled?: boolean;
  onSelect: (value: DocumentType) => void;
};

const accents = {
  blue: "bg-blue-50 text-blue-700 ring-blue-100 dark:bg-blue-400/15 dark:text-blue-300 dark:ring-blue-400/25",
  cyan: "bg-cyan-50 text-cyan-700 ring-cyan-100 dark:bg-cyan-400/15 dark:text-cyan-300 dark:ring-cyan-400/25",
  red: "bg-red-50 text-red-700 ring-red-100 dark:bg-red-400/15 dark:text-red-300 dark:ring-red-400/25",
} as const;

export function DocumentTypeCard({
  icon: Icon,
  title,
  description,
  accent,
  value,
  selected = false,
  disabled = false,
  onSelect,
}: DocumentTypeCardProps) {
  return (
    <label
      className={cn(
        "border-border bg-card has-[:focus-visible]:ring-primary relative flex min-h-44 cursor-pointer flex-col rounded-xl border p-4 shadow-sm transition-[border-color,box-shadow,transform] has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-offset-2 sm:p-5",
        selected && "border-primary bg-primary/[0.025] ring-primary/15 ring-2",
        disabled
          ? "cursor-not-allowed opacity-60"
          : "hover:border-primary/40 hover:-translate-y-0.5 hover:shadow-md",
      )}
      aria-disabled={disabled || undefined}
    >
      <input
        type="radio"
        name="document-type"
        value={value}
        checked={selected}
        disabled={disabled}
        onChange={() => onSelect(value)}
        className="sr-only"
      />
      {selected ? (
        <span className="bg-primary text-primary-foreground absolute top-3 right-3 flex size-6 items-center justify-center rounded-full">
          <Check className="size-3.5" aria-hidden="true" />
          <span className="sr-only">Sélectionné</span>
        </span>
      ) : null}
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
      {selected ? (
        <Badge variant="default" className="mt-4">
          Sélectionné
        </Badge>
      ) : disabled ? (
        <Badge variant="muted" className="mt-4">
          Indisponible
        </Badge>
      ) : (
        <span className="text-muted-foreground mt-4 text-xs font-semibold">
          Choisir ce document
        </span>
      )}
    </label>
  );
}
