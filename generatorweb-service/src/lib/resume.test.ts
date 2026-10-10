import {
  MAX_RESUME_FILE_SIZE,
  parseResumeFile,
  ResumeValidationError,
  validateAvpNumber,
} from "@/lib/resume";

function jsonFile(value: unknown, name = "resume.json") {
  return new File([JSON.stringify(value)], name, { type: "application/json" });
}

describe("parseResumeFile", () => {
  it("importe directement un JSON Resume et conserve ses propriétés", async () => {
    const file = jsonFile({
      basics: { name: "Camille Exemple", label: "Assistante qualité" },
      work: [{ name: "OPT" }],
      education: [],
      skills: [{ name: "Qualité" }],
      custom: { preserved: true },
    });

    const result = await parseResumeFile(file);

    expect(result.avpNumber).toBeNull();
    expect(result.metadata.candidateName).toBe("Camille Exemple");
    expect(result.metadata.workCount).toBe(1);
    expect(result.resume.custom).toEqual({ preserved: true });
  });

  it("normalise une enveloppe API et extrait le numéro AVP", async () => {
    const result = await parseResumeFile(
      jsonFile({
        avp_number: " 3134-26-1382/SR ",
        resume: { basics: { name: "Camille" }, skills: [] },
      }),
    );

    expect(result.avpNumber).toBe("3134-26-1382/SR");
    expect(result.resume).toEqual({
      basics: { name: "Camille" },
      skills: [],
    });
    expect(result.resume).not.toHaveProperty("avp_number");
  });

  it("accepte les métadonnées facultatives absentes", async () => {
    const result = await parseResumeFile(
      jsonFile({ volunteer: [{ name: "Aide" }] }),
    );

    expect(result.metadata).toMatchObject({
      candidateName: null,
      professionalTitle: null,
      location: null,
      workCount: 0,
      educationCount: 0,
      skillCount: 0,
    });
  });

  it.each([
    [
      "un JSON invalide",
      new File(["{"], "resume.json", { type: "application/json" }),
    ],
    ["un tableau à la racine", jsonFile([{ basics: {} }])],
    ["une enveloppe invalide", jsonFile({ resume: [], avp_number: "123" })],
    ["un objet vide", jsonFile({})],
  ])("refuse %s", async (_label, file) => {
    await expect(parseResumeFile(file)).rejects.toBeInstanceOf(
      ResumeValidationError,
    );
  });

  it("refuse un fichier trop volumineux", async () => {
    const file = new File(
      [new Uint8Array(MAX_RESUME_FILE_SIZE + 1)],
      "resume.json",
      {
        type: "application/json",
      },
    );

    await expect(parseResumeFile(file)).rejects.toThrow("2 Mo");
  });
});

describe("validateAvpNumber", () => {
  it("normalise implicitement les espaces lors de la validation", () => {
    expect(validateAvpNumber(" 3134-26-1382/SR ")).toBeNull();
  });

  it("refuse une valeur vide ou trop longue", () => {
    expect(validateAvpNumber("   ")).toMatch(/Renseignez/);
    expect(validateAvpNumber("A".repeat(129))).toMatch(/128/);
  });
});
