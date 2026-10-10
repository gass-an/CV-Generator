import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

type EmptyStateProps = {
  icon: LucideIcon;
  title: string;
  description: string;
  children?: ReactNode;
};

export function EmptyState({
  icon: Icon,
  title,
  description,
  children,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center px-5 py-12 text-center sm:py-16">
      <div className="bg-primary/8 text-primary ring-primary/10 flex size-14 items-center justify-center rounded-2xl ring-8">
        <Icon className="size-7" aria-hidden="true" />
      </div>
      <h2 className="mt-6 text-lg font-semibold">{title}</h2>
      <p className="text-muted-foreground mt-2 max-w-md text-sm leading-6">
        {description}
      </p>
      {children}
    </div>
  );
}
