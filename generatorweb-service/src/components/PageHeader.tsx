import type { ReactNode } from "react";

type PageHeaderProps = {
  eyebrow?: string;
  title: string;
  description: string;
  action?: ReactNode;
};

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: PageHeaderProps) {
  return (
    <header className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-3xl">
        {eyebrow ? (
          <p className="text-primary mb-2 text-sm font-bold tracking-wide uppercase">
            {eyebrow}
          </p>
        ) : null}
        <h1 className="text-foreground text-3xl font-bold tracking-tight sm:text-4xl">
          {title}
        </h1>
        <p className="text-muted-foreground mt-3 max-w-2xl text-base leading-7 sm:text-lg">
          {description}
        </p>
      </div>
      {action}
    </header>
  );
}
