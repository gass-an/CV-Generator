import { render, screen } from "@testing-library/react";
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

    await user.click(screen.getByRole("link", { name: /Historique/ }));
    expect(
      screen.getByRole("heading", { name: "Historique des documents" }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: /Paramètres/ }));
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
