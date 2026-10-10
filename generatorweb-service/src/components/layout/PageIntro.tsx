import type { LucideIcon } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type PageIntroProps = {
  title: string;
  description: string;
  icon: LucideIcon;
};

export function PageIntro({ title, description, icon: Icon }: PageIntroProps) {
  return (
    <section className="w-full" aria-labelledby="page-title">
      <Card className="mx-auto max-w-3xl">
        <CardHeader>
          <div className="bg-muted text-primary mb-2 flex size-11 items-center justify-center rounded-xl">
            <Icon className="size-5" aria-hidden="true" />
          </div>
          <CardTitle id="page-title">{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground text-sm">
            Cette fonctionnalité sera disponible prochainement.
          </p>
        </CardContent>
      </Card>
    </section>
  );
}
