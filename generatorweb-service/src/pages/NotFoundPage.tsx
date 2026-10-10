import { CircleAlert } from "lucide-react";
import { Link } from "react-router-dom";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function NotFoundPage() {
  return (
    <section
      className="flex w-full items-center"
      aria-labelledby="not-found-title"
    >
      <Card className="mx-auto w-full max-w-2xl text-center">
        <CardHeader className="justify-items-center">
          <CircleAlert
            className="text-muted-foreground size-10"
            aria-hidden="true"
          />
          <p className="text-accent text-sm font-semibold">Erreur 404</p>
          <CardTitle id="not-found-title">Page introuvable</CardTitle>
        </CardHeader>
        <CardContent>
          <Link
            to="/"
            className="bg-primary text-primary-foreground hover:bg-primary/90 inline-flex min-h-11 items-center rounded-lg px-5 py-2 text-sm font-semibold transition-colors"
          >
            Revenir à l'accueil
          </Link>
        </CardContent>
      </Card>
    </section>
  );
}
