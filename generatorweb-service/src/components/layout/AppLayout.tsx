import { useRef } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { navigationItems } from "@/app/navigation";
import { BrandLogo } from "@/components/BrandLogo";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export function AppLayout() {
  const mainContent = useRef<HTMLElement>(null);

  return (
    <div className="flex min-h-svh flex-col">
      <a
        href="#contenu-principal"
        onClick={() =>
          requestAnimationFrame(() => mainContent.current?.focus())
        }
        className="bg-primary text-primary-foreground fixed top-3 left-3 z-50 -translate-y-20 rounded-md px-4 py-2 text-sm font-semibold transition-transform focus:translate-y-0"
      >
        Aller au contenu
      </a>

      <header className="border-border/80 bg-card/95 sticky top-0 z-40 border-b backdrop-blur-md">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-3 px-4 py-3 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:gap-8 lg:px-8">
          <NavLink
            to="/"
            className="flex max-w-full items-center gap-3 rounded-lg"
            aria-label="CV-Generator — accueil"
          >
            <BrandLogo brand="cv-generator" />
            <span className="min-w-0">
              <span className="block text-lg font-bold tracking-tight">
                CV-Generator
              </span>
              <span className="text-muted-foreground hidden text-xs sm:block">
                Votre candidature, mieux préparée
              </span>
            </span>
          </NavLink>

          <div className="flex w-full min-w-0 items-center gap-3 lg:ml-auto lg:w-auto">
            <Badge variant="outline" className="hidden xl:inline-flex">
              Projet HackAVP
            </Badge>
            <nav
              className="w-full min-w-0 lg:w-auto lg:flex-none"
              aria-label="Navigation principale"
            >
              <ul className="grid grid-cols-3 gap-1 lg:flex">
                {navigationItems.map(({ label, to, icon: Icon, end }) => (
                  <li key={to}>
                    <NavLink
                      to={to}
                      end={end}
                      className={({ isActive }) =>
                        cn(
                          "text-muted-foreground hover:bg-primary/6 hover:text-primary relative flex min-h-12 min-w-0 flex-col items-center justify-center gap-0.5 rounded-lg px-1 py-1.5 text-xs font-semibold transition-colors sm:min-h-11 sm:flex-row sm:gap-2 sm:px-4 sm:py-2 sm:text-sm",
                          isActive &&
                            "bg-primary/10 text-primary after:bg-primary after:absolute after:inset-x-4 after:-bottom-3 after:h-0.5 after:rounded-full lg:after:-bottom-3.5",
                        )
                      }
                    >
                      <Icon className="size-4" aria-hidden="true" />
                      {label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </nav>
          </div>
        </div>
      </header>

      <main
        ref={mainContent}
        id="contenu-principal"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 sm:py-10 lg:px-8 lg:py-12"
      >
        <Outlet />
      </main>

      <footer className="border-border/80 bg-card border-t">
        <div className="mx-auto flex w-full max-w-7xl flex-col items-center gap-5 px-4 py-6 sm:flex-row sm:justify-between sm:px-6 lg:px-8">
          <div className="text-center sm:text-left">
            <p className="text-sm font-semibold">CV-Generator</p>
            <p className="text-muted-foreground mt-1 text-xs">
              Une application développée dans le cadre de HackAVP.
            </p>
          </div>
          <div
            className="flex items-center gap-6 rounded-xl px-3 py-2"
            aria-label="Organisations du projet"
          >
            <BrandLogo brand="opt" />
            <span className="bg-border h-9 w-px" aria-hidden="true" />
            <BrandLogo brand="iae" />
          </div>
        </div>
      </footer>
    </div>
  );
}
