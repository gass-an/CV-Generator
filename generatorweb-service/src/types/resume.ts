export type JsonObject = Record<string, unknown>;

export type ResumeMetadata = {
  candidateName: string | null;
  professionalTitle: string | null;
  location: string | null;
  workCount: number;
  educationCount: number;
  skillCount: number;
};

export type ImportedResume = {
  resume: JsonObject;
  fileName: string;
  fileSize: number;
  metadata: ResumeMetadata;
};

export type ParsedResumeFile = ImportedResume & {
  avpNumber: string | null;
};
