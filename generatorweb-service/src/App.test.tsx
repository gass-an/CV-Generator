import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { App } from "@/App";

function renderApplication(initialPath = "/") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <App />
    </MemoryRouter>,
  );
}

describe("App", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("affiche le layout partagé, les logos et une navigation accessible", () => {
    renderApplication();

    expect(screen.getByRole("img", { name: "CV-Generator" })).toHaveAttribute(
      "src",
      "/logos/CV_Generator.png",
    );
    expect(
      screen.getByRole("img", { name: "OPT Nouvelle-Calédonie" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "IAE Nouvelle-Calédonie" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "STATION N" })).toHaveAttribute(
      "src",
      "/logos/statioN.png",
    );
    expect(
      screen.getByRole("navigation", { name: "Navigation principale" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Générer/ })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(
      screen.getByRole("link", { name: "Aller au contenu" }),
    ).toHaveAttribute("href", "#contenu-principal");
  });

  it("relie les logos des partenaires à leurs sites officiels", async () => {
    const user = userEvent.setup();
    renderApplication();
    const partners = [
      ["Visiter le site de l'OPT", "https://www.opt.nc/"],
      ["Visiter le site de l'IAE", "https://iae.unc.nc/"],
      ["Visiter le site de STATION N", "https://www.station-n.nc/"],
    ] as const;

    const links = partners.map(([name, href]) => {
      const link = screen.getByRole("link", { name });
      expect(link).toHaveAttribute("href", href);
      expect(link).toHaveAttribute("target", "_blank");
      expect(link).toHaveAttribute("rel", "noopener noreferrer");
      return link;
    });

    links[0].focus();
    expect(links[0]).toHaveFocus();
    await user.tab();
    expect(links[1]).toHaveFocus();
    await user.tab();
    expect(links[2]).toHaveFocus();
    expect(
      screen.getByText("Une application développée dans le cadre de HackAVP."),
    ).toBeInTheDocument();
  });

  it("conserve le nom de l'application et toute la navigation sur mobile", () => {
    renderApplication();
    const homeLink = screen.getByRole("link", {
      name: "CV-Generator — accueil",
    });
    const applicationName = within(homeLink).getByText("CV-Generator");

    expect(applicationName).not.toHaveClass("hidden");
    expect(
      screen.getByRole("navigation", { name: "Navigation principale" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Générer/ })).toBeVisible();
    expect(screen.getByRole("link", { name: /Historique/ })).toBeVisible();
    expect(screen.getByRole("link", { name: /Paramètres/ })).toBeVisible();
  });

  it("transfère le focus du lien d'évitement vers le contenu principal", async () => {
    const user = userEvent.setup();
    renderApplication();

    await user.tab();
    const skipLink = screen.getByRole("link", { name: "Aller au contenu" });
    expect(skipLink).toHaveFocus();
    await user.keyboard("{Enter}");

    await waitFor(() =>
      expect(document.getElementById("contenu-principal")).toHaveFocus(),
    );
  });

  it("présente les trois types de documents sans action factice", () => {
    renderApplication();

    expect(
      screen.getByRole("heading", {
        name: "Préparez une candidature qui vous ressemble",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Curriculum vitæ" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Lettre de motivation" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Préparation à l'entretien" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Aucun document à prévisualiser"),
    ).toBeInTheDocument();
  });

  it("permet de naviguer vers les pages principales", async () => {
    const user = userEvent.setup();
    renderApplication();

    screen.getByRole("link", { name: /Historique/ }).focus();
    await user.keyboard("{Enter}");
    expect(
      screen.getByRole("heading", { name: "Historique des documents" }),
    ).toBeInTheDocument();

    screen.getByRole("link", { name: /Paramètres/ }).focus();
    await user.keyboard("{Enter}");
    expect(
      screen.getByRole("heading", { name: "Paramètres" }),
    ).toBeInTheDocument();
  });

  it("invite à configurer une clé avant d'afficher l'historique", () => {
    renderApplication("/historique");

    expect(
      screen.getByText("Une clé API valide est nécessaire."),
    ).toBeInTheDocument();
  });

  it("présente les paramètres sans simuler une clé enregistrée", () => {
    renderApplication("/parametres");

    expect(
      screen.getByRole("heading", { name: "Paramètres" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Non configurée")).toBeInTheDocument();
    expect(screen.getByLabelText("Clé API")).toBeEnabled();
    expect(screen.getByLabelText("Clé API")).toHaveValue("");
  });

  it("affiche une page 404 pour une route inconnue", () => {
    renderApplication("/route-inconnue");

    expect(
      screen.getByRole("heading", { name: "Page introuvable" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Revenir à l'accueil" }),
    ).toHaveAttribute("href", "/");
  });
});
