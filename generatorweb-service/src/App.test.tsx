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
  it("affiche le layout partagé et la page de génération", () => {
    renderApplication();

    expect(screen.getByText("CV-Generator")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Génération de documents" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("navigation", { name: "Navigation principale" }),
    ).toBeInTheDocument();
  });

  it("permet de naviguer vers les pages principales", async () => {
    const user = userEvent.setup();
    renderApplication();

    await user.click(screen.getByRole("link", { name: /Historique/ }));
    expect(
      screen.getByRole("heading", { name: "Historique" }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: /Paramètres/ }));
    expect(
      screen.getByRole("heading", { name: "Paramètres" }),
    ).toBeInTheDocument();
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
