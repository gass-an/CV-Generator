import { FileText } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { navigationItems } from "@/app/navigation";
import { cn } from "@/lib/utils";

export function AppLayout() {
  return (
    <div className="flex min-h-svh flex-col">
      <header className="border-border/80 bg-card border-b">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <NavLink
            to="/"
            className="flex w-fit items-center gap-2 rounded-md font-semibold tracking-tight"
          >
            <span className="bg-primary text-primary-foreground flex size-9 items-center justify-center rounded-lg">
              <FileText className="size-5" aria-hidden="true" />
            </span>
            <span>CV-Generator</span>
          </NavLink>

          <nav aria-label="Navigation principale">
            <ul className="flex flex-wrap gap-1">
              {navigationItems.map(({ label, to, icon: Icon, end }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    end={end}
                    className={({ isActive }) =>
                      cn(
                        "text-muted-foreground hover:bg-muted hover:text-foreground flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                        isActive && "bg-muted text-foreground",
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
      </header>

      <main className="mx-auto flex w-full max-w-6xl flex-1 px-4 py-10 sm:px-6 lg:px-8 lg:py-14">
        <Outlet />
      </main>

      <footer className="border-border/80 text-muted-foreground border-t px-4 py-5 text-center text-sm">
        CV-Generator — outil de préparation des candidatures HackAVP
      </footer>
    </div>
  );
}
