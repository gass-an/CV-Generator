import { CircleAlert } from "lucide-react";
import { Link } from "react-router-dom";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function NotFoundPage() {
  return (
    <section className="w-full" aria-labelledby="not-found-title">
      <Card className="mx-auto max-w-2xl text-center">
        <CardHeader className="justify-items-center">
          <CircleAlert
            className="text-muted-foreground size-10"
            aria-hidden="true"
          />
          <p className="text-primary text-sm font-semibold">Erreur 404</p>
          <CardTitle id="not-found-title">Page introuvable</CardTitle>
        </CardHeader>
        <CardContent>
          <Link
            to="/"
            className="bg-primary text-primary-foreground inline-flex rounded-md px-4 py-2 text-sm font-medium"
          >
            Revenir à l'accueil
          </Link>
        </CardContent>
      </Card>
    </section>
  );
}
