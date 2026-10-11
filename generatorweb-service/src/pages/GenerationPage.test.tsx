import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { App } from "@/App";

function renderGeneration() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );
}

function fileFrom(value: unknown, name = "camille.json") {
  return new File([JSON.stringify(value)], name, { type: "application/json" });
}

const directResume = {
  basics: {
    name: "Camille Exemple",
    label: "Assistante qualité",
    location: { city: "Nouméa", region: "Province Sud" },
  },
  work: [{ name: "Entreprise A" }, { name: "Entreprise B" }],
  education: [{ institution: "IAE" }],
  skills: [{ name: "Qualité" }, { name: "Organisation" }],
};

describe("préparation de la génération", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("importe un JSON Resume direct et affiche son récapitulatif", async () => {
    const user = userEvent.setup();
    renderGeneration();

    await user.upload(
      screen.getByLabelText("Choisir un fichier"),
      fileFrom(directResume),
    );

    expect(await screen.findByText("Camille Exemple")).toBeInTheDocument();
    expect(screen.getByText("Assistante qualité")).toBeInTheDocument();
    expect(screen.getByText("Nouméa, Province Sud")).toBeInTheDocument();
    expect(screen.getByText(/camille\.json ·/)).toBeInTheDocument();
    expect(
      screen.getByText("Expériences").nextElementSibling,
    ).toHaveTextContent("2");
    expect(screen.getByText("Formations").nextElementSibling).toHaveTextContent(
      "1",
    );
    expect(
      screen.getByText("Compétences").nextElementSibling,
    ).toHaveTextContent("2");
  });

  it("rend visible le focus clavier de l'import de fichier", async () => {
    const user = userEvent.setup();
    renderGeneration();
    const input = screen.getByLabelText("Choisir un fichier");

    for (let index = 0; index < 6; index += 1) {
      await user.tab();
    }

    expect(input).toHaveFocus();
    expect(screen.getByText("Choisir un fichier")).toHaveClass("ring-2");
  });

  it("extrait le numéro AVP d'une enveloppe", async () => {
    const user = userEvent.setup();
    renderGeneration();

    await user.upload(
      screen.getByLabelText("Choisir un fichier"),
      fileFrom({ avp_number: " 3134-26-1382/SR ", resume: directResume }),
    );

    expect(await screen.findByLabelText("Numéro AVP")).toHaveValue(
      "3134-26-1382/SR",
    );
  });

  it("conserve un AVP saisi manuellement si le nouvel import n'en contient pas", async () => {
    const user = userEvent.setup();
    renderGeneration();
    const avpInput = screen.getByLabelText("Numéro AVP");

    await user.type(avpInput, "AVP-MANUEL/2026");
    await user.upload(
      screen.getByLabelText("Choisir un fichier"),
      fileFrom(directResume),
    );

    expect(avpInput).toHaveValue("AVP-MANUEL/2026");
  });

  it("préserve le dernier profil valide après un remplacement incorrect", async () => {
    const user = userEvent.setup();
    renderGeneration();
    await user.upload(
      screen.getByLabelText("Choisir un fichier"),
      fileFrom(directResume),
    );
    await screen.findByText("Camille Exemple");

    await user.upload(
      screen.getByLabelText("Remplacer"),
      new File(["{"], "incorrect.json", { type: "application/json" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /profil déjà chargé est conservé/i,
    );
    expect(screen.getByText("Camille Exemple")).toBeInTheDocument();
  });

  it("permet de retirer puis remplacer le profil", async () => {
    const user = userEvent.setup();
    renderGeneration();
    await user.upload(
      screen.getByLabelText("Choisir un fichier"),
      fileFrom(directResume),
    );
    await screen.findByText("Camille Exemple");

    const remove = screen.getByRole("button", { name: "Retirer" });
    remove.focus();
    await user.keyboard("{Enter}");

    expect(screen.queryByText("Camille Exemple")).not.toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByLabelText("Choisir un fichier")).toHaveFocus(),
    );
    expect(screen.getByText("Choisir un fichier")).toHaveClass("ring-2");
  });

  it("valide un numéro AVP vide et limite sa longueur", async () => {
    const user = userEvent.setup();
    renderGeneration();
    const input = screen.getByLabelText("Numéro AVP");

    await user.click(input);
    await user.tab();
    expect(
      await screen.findByText("Renseignez un numéro AVP."),
    ).toBeInTheDocument();
    expect(input).toHaveAttribute("maxlength", "128");
  });

  it("retire les espaces extérieurs du numéro AVP à la validation", async () => {
    const user = userEvent.setup();
    renderGeneration();
    const input = screen.getByLabelText("Numéro AVP");

    await user.type(input, " 3134-26-1382/SR ");
    await user.tab();

    expect(input).toHaveValue("3134-26-1382/SR");
  });

  it("conserve le profil et l'AVP pendant la navigation", async () => {
    const user = userEvent.setup();
    renderGeneration();
    await user.upload(
      screen.getByLabelText("Choisir un fichier"),
      fileFrom(directResume),
    );
    await user.type(screen.getByLabelText("Numéro AVP"), "AVP-PERSISTANT");

    await user.click(screen.getByRole("link", { name: /Paramètres/ }));
    await user.click(screen.getByRole("link", { name: /Générer/ }));

    expect(screen.getByText("Camille Exemple")).toBeInTheDocument();
    expect(screen.getByLabelText("Numéro AVP")).toHaveValue("AVP-PERSISTANT");
  });

  it("sélectionne un seul type de document et explique les prérequis manquants", async () => {
    const user = userEvent.setup();
    renderGeneration();
    const cv = screen.getByRole("radio", { name: /Curriculum vitæ/ });
    const letter = screen.getByRole("radio", { name: /Lettre de motivation/ });

    expect(
      screen.getByRole("button", { name: "Générer le document" }),
    ).toBeDisabled();
    expect(screen.getByText("Clé API vérifiée")).toBeInTheDocument();
    expect(screen.getByText("Profil JSON Resume importé")).toBeInTheDocument();

    await user.click(cv);
    expect(cv).toBeChecked();
    expect(letter).not.toBeChecked();

    await user.click(letter);
    expect(letter).toBeChecked();
    expect(cv).not.toBeChecked();
  });

  it("sélectionne les types de document avec le clavier", async () => {
    const user = userEvent.setup();
    renderGeneration();
    const cv = screen.getByRole("radio", { name: /Curriculum vitæ/ });
    const letter = screen.getByRole("radio", { name: /Lettre de motivation/ });

    cv.focus();
    await user.keyboard(" ");
    expect(cv).toBeChecked();
    await user.keyboard("{ArrowRight}");
    expect(letter).toBeChecked();
    expect(letter.closest("label")).toHaveClass("has-[:focus-visible]:ring-2");
  });
});
