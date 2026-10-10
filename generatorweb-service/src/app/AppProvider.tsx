import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { validateAvpNumber } from "@/lib/resume";
import { useDocumentPolling } from "@/hooks/useDocumentPolling";
import { ApiError } from "@/services/apiClient";
import { verifyApiKey } from "@/services/authService";
import { createDocumentJob } from "@/services/documentService";
import type {
  DocumentJobStatusResponse,
  DocumentType,
  GenerationState,
  TrackedDocumentJob,
} from "@/types/document";
import type { ImportedResume, ParsedResumeFile } from "@/types/resume";

const SESSION_KEY = "cv-generator.api-key.session";
const LOCAL_KEY = "cv-generator.api-key.local";

export type AuthStatus =
  "absent" | "verifying" | "valid" | "rejected" | "unavailable";

type AuthenticationResult =
  | { ok: true }
  | { ok: false; message: string; reason: "rejected" | "unavailable" };
type AuthenticationFailure = Extract<AuthenticationResult, { ok: false }>;

type AuthState = {
  status: AuthStatus;
  credentialKey: string | null;
  activeApiKey: string | null;
  remember: boolean;
  storageError: string | null;
  authenticate: (
    key: string,
    remember: boolean,
  ) => Promise<AuthenticationResult>;
  setRemember: (remember: boolean) => void;
  clearCredential: () => void;
};

type ApplicationDraftState = {
  importedResume: ImportedResume | null;
  avpNumber: string;
  profileValid: boolean;
  avpValid: boolean;
  selectedDocumentType: DocumentType | null;
  setAvpNumber: (value: string) => void;
  setSelectedDocumentType: (value: DocumentType) => void;
  acceptResume: (parsed: ParsedResumeFile) => void;
  removeResume: () => void;
};

type GenerationActionResult = { ok: true } | { ok: false; message: string };

type GenerationContextState = {
  state: GenerationState;
  start: () => Promise<GenerationActionResult>;
  allowUncertainRetry: () => void;
  resumeTracking: () => void;
  stopTracking: () => void;
};

type AppContextValue = {
  auth: AuthState;
  draft: ApplicationDraftState;
  generation: GenerationContextState;
};

type StoredCredential = {
  key: string | null;
  remember: boolean;
  storageError: string | null;
};

// Le contexte est exporté pour le hook dédié ; le provider reste le seul composant.
// eslint-disable-next-line react-refresh/only-export-components
export const AppContext = createContext<AppContextValue | null>(null);

function readStoredCredential(): StoredCredential {
  try {
    const localKey = window.localStorage.getItem(LOCAL_KEY);
    if (localKey) {
      window.sessionStorage.removeItem(SESSION_KEY);
      return { key: localKey, remember: true, storageError: null };
    }
    const sessionKey = window.sessionStorage.getItem(SESSION_KEY);
    return { key: sessionKey, remember: false, storageError: null };
  } catch {
    return {
      key: null,
      remember: false,
      storageError:
        "Le stockage du navigateur est indisponible. La clé ne pourra être conservée qu'en mémoire.",
    };
  }
}

function persistCredential(key: string, remember: boolean): string | null {
  const target = remember ? window.localStorage : window.sessionStorage;
  const obsolete = remember ? window.sessionStorage : window.localStorage;
  const targetKey = remember ? LOCAL_KEY : SESSION_KEY;
  const obsoleteKey = remember ? SESSION_KEY : LOCAL_KEY;

  try {
    obsolete.removeItem(obsoleteKey);
    target.setItem(targetKey, key);
    return null;
  } catch {
    try {
      target.removeItem(targetKey);
      obsolete.removeItem(obsoleteKey);
    } catch {
      // Le message retourné suffit ; aucun détail sensible n'est exposé.
    }
    return "La clé est valide, mais le navigateur n'a pas pu la conserver.";
  }
}

function removeStoredCredentials(): string | null {
  try {
    window.localStorage.removeItem(LOCAL_KEY);
    window.sessionStorage.removeItem(SESSION_KEY);
    return null;
  } catch {
    return "Le navigateur n'a pas pu supprimer la clé enregistrée.";
  }
}

function authenticationError(error: unknown): AuthenticationFailure {
  if (error instanceof ApiError && error.status === 401) {
    return {
      ok: false,
      reason: "rejected",
      message:
        "La clé a été refusée. Vérifiez-la ou demandez une nouvelle clé.",
    };
  }
  if (error instanceof ApiError && error.kind === "timeout") {
    return { ok: false, reason: "unavailable", message: error.message };
  }
  if (error instanceof ApiError && error.kind === "network") {
    return { ok: false, reason: "unavailable", message: error.message };
  }
  return {
    ok: false,
    reason: "unavailable",
    message:
      "Le service ne peut pas vérifier la clé pour le moment. Réessayez plus tard.",
  };
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [storedAtStartup] = useState(readStoredCredential);
  const [credentialKey, setCredentialKey] = useState(storedAtStartup.key);
  const [authStatus, setAuthStatus] = useState<AuthStatus>(
    storedAtStartup.key ? "verifying" : "absent",
  );
  const [remember, setRememberState] = useState(storedAtStartup.remember);
  const [storageError, setStorageError] = useState(
    storedAtStartup.storageError,
  );
  const [importedResume, setImportedResume] = useState<ImportedResume | null>(
    null,
  );
  const [avpNumber, setAvpNumber] = useState("");
  const [selectedDocumentType, setSelectedDocumentType] =
    useState<DocumentType | null>(null);
  const [generationState, setGenerationState] = useState<GenerationState>({
    phase: "idle",
  });
  const [pollingRetryToken, setPollingRetryToken] = useState(0);
  const validationInProgress = useRef(false);
  const creationInProgress = useRef(false);
  const authOperation = useRef(0);
  const generationOperation = useRef(0);
  const identityRevision = useRef(0);
  const generationAbortController = useRef<AbortController | null>(null);

  const invalidateGeneration = useCallback((clearDraft: boolean) => {
    identityRevision.current += 1;
    generationOperation.current += 1;
    creationInProgress.current = false;
    generationAbortController.current?.abort();
    generationAbortController.current = null;
    setPollingRetryToken((value) => value + 1);
    setGenerationState({ phase: "idle" });
    if (clearDraft) {
      setImportedResume(null);
      setAvpNumber("");
      setSelectedDocumentType(null);
    }
  }, []);

  useEffect(() => {
    if (!storedAtStartup.key) {
      return;
    }
    const operation = ++authOperation.current;
    const controller = new AbortController();
    verifyApiKey(storedAtStartup.key, controller.signal)
      .then(() => {
        if (authOperation.current === operation) {
          setAuthStatus("valid");
        }
      })
      .catch((error: unknown) => {
        if (
          authOperation.current !== operation ||
          (error instanceof ApiError && error.kind === "aborted")
        ) {
          return;
        }
        setAuthStatus(authenticationError(error).reason);
      });
    return () => controller.abort();
  }, [storedAtStartup.key]);

  const authenticate = useCallback(
    async (candidate: string, shouldRemember: boolean) => {
      if (validationInProgress.current) {
        return {
          ok: false,
          reason: "unavailable",
          message: "Une vérification est déjà en cours.",
        } satisfies AuthenticationResult;
      }

      const normalized = candidate.trim();
      if (!normalized) {
        return {
          ok: false,
          reason: "rejected",
          message: "Saisissez une clé API avant de la vérifier.",
        } satisfies AuthenticationResult;
      }

      const hadValidCredential =
        authStatus === "valid" && credentialKey !== null;
      const operation = ++authOperation.current;
      validationInProgress.current = true;
      if (!hadValidCredential) {
        setAuthStatus("verifying");
      }
      try {
        await verifyApiKey(normalized);
        if (authOperation.current !== operation) {
          return {
            ok: false,
            reason: "unavailable",
            message: "La vérification a été annulée.",
          } satisfies AuthenticationResult;
        }
        const changesIdentity =
          credentialKey !== null && normalized !== credentialKey;
        if (changesIdentity) {
          invalidateGeneration(true);
        }
        setCredentialKey(normalized);
        setRememberState(shouldRemember);
        setAuthStatus("valid");
        setStorageError(persistCredential(normalized, shouldRemember));
        return { ok: true } satisfies AuthenticationResult;
      } catch (error) {
        const result = authenticationError(error);
        if (authOperation.current === operation && !hadValidCredential) {
          setAuthStatus(result.reason);
        }
        return result;
      } finally {
        validationInProgress.current = false;
      }
    },
    [authStatus, credentialKey, invalidateGeneration],
  );

  const setRemember = useCallback(
    (shouldRemember: boolean) => {
      setRememberState(shouldRemember);
      if (credentialKey && authStatus === "valid") {
        setStorageError(persistCredential(credentialKey, shouldRemember));
      }
    },
    [authStatus, credentialKey],
  );

  const clearCredential = useCallback(() => {
    authOperation.current += 1;
    invalidateGeneration(true);
    setStorageError(removeStoredCredentials());
    setCredentialKey(null);
    setRememberState(false);
    setAuthStatus("absent");
  }, [invalidateGeneration]);

  const acceptResume = useCallback((parsed: ParsedResumeFile) => {
    setImportedResume({
      resume: parsed.resume,
      fileName: parsed.fileName,
      fileSize: parsed.fileSize,
      metadata: parsed.metadata,
    });
    if (parsed.avpNumber) {
      setAvpNumber(parsed.avpNumber);
    }
  }, []);

  const removeResume = useCallback(() => setImportedResume(null), []);

  const startGeneration =
    useCallback(async (): Promise<GenerationActionResult> => {
      if (creationInProgress.current) {
        return { ok: false, message: "Une demande est déjà en cours d'envoi." };
      }
      if (!credentialKey || authStatus !== "valid") {
        return {
          ok: false,
          message: "Vérifiez votre clé API dans les Paramètres.",
        };
      }
      if (!importedResume) {
        return { ok: false, message: "Importez un JSON Resume valide." };
      }
      const normalizedAvp = avpNumber.trim();
      if (validateAvpNumber(normalizedAvp)) {
        return { ok: false, message: "Renseignez un numéro AVP valide." };
      }
      if (!selectedDocumentType) {
        return { ok: false, message: "Sélectionnez un type de document." };
      }
      if (
        generationState.phase === "creation_error" &&
        generationState.uncertain
      ) {
        return {
          ok: false,
          message:
            "Confirmez explicitement la nouvelle demande après avoir pris connaissance du risque de doublon.",
        };
      }

      const operation = ++generationOperation.current;
      const operationIdentity = identityRevision.current;
      const controller = new AbortController();
      generationAbortController.current = controller;
      const request = {
        documentType: selectedDocumentType,
        avpNumber: normalizedAvp,
        candidateName: importedResume.metadata.candidateName,
        requestedAt: new Date().toISOString(),
      };
      creationInProgress.current = true;
      setGenerationState({ phase: "creating", request });

      try {
        const created = await createDocumentJob(
          selectedDocumentType,
          { avp_number: normalizedAvp, resume: importedResume.resume },
          credentialKey,
          controller.signal,
        );
        if (
          generationOperation.current !== operation ||
          identityRevision.current !== operationIdentity
        ) {
          return { ok: false, message: "La demande a été remplacée." };
        }
        const job: TrackedDocumentJob = {
          ...request,
          id: created.id,
          status: created.status,
          createdAt: request.requestedAt,
          startedAt: null,
          completedAt: null,
        };
        setGenerationState({ phase: created.status, job });
        return { ok: true };
      } catch (error) {
        if (
          generationOperation.current !== operation ||
          identityRevision.current !== operationIdentity
        ) {
          return { ok: false, message: "La demande a été remplacée." };
        }
        const apiError = error instanceof ApiError ? error : null;
        const authenticationError = apiError?.status === 401;
        const uncertain =
          apiError?.kind === "network" || apiError?.kind === "timeout";
        if (authenticationError) {
          setAuthStatus("rejected");
        }
        const message = authenticationError
          ? "La clé API a été refusée. Vérifiez-la dans les Paramètres."
          : uncertain
            ? "La réponse n'est pas parvenue. Le job a peut-être été créé : vérifiez l'historique avant de relancer une demande."
            : "La demande de génération a échoué. Vous pouvez réessayer.";
        setGenerationState({
          phase: "creation_error",
          request,
          message,
          uncertain,
          authenticationError,
        });
        return { ok: false, message };
      } finally {
        if (generationOperation.current === operation) {
          creationInProgress.current = false;
          generationAbortController.current = null;
        }
      }
    }, [
      authStatus,
      avpNumber,
      credentialKey,
      importedResume,
      generationState,
      selectedDocumentType,
    ]);

  const pollingGenerationOperation = generationOperation.current;
  const pollingIdentityRevision = identityRevision.current;

  const handlePolledStatus = useCallback(
    (status: DocumentJobStatusResponse) => {
      if (
        generationOperation.current !== pollingGenerationOperation ||
        identityRevision.current !== pollingIdentityRevision
      ) {
        return;
      }
      setGenerationState((current) => {
        if (
          (current.phase !== "pending" && current.phase !== "processing") ||
          current.job.id !== status.id
        ) {
          return current;
        }
        const job: TrackedDocumentJob = {
          ...current.job,
          status: status.status,
          createdAt: status.created_at,
          startedAt: status.started_at,
          completedAt: status.completed_at,
        };
        return { phase: status.status, job };
      });
    },
    [pollingGenerationOperation, pollingIdentityRevision],
  );

  const handlePollingError = useCallback(
    (error: ApiError) => {
      if (
        generationOperation.current !== pollingGenerationOperation ||
        identityRevision.current !== pollingIdentityRevision
      ) {
        return;
      }
      const authenticationError = error.status === 401;
      setGenerationState((current) => {
        if (current.phase !== "pending" && current.phase !== "processing") {
          return current;
        }
        return {
          phase: "interrupted",
          job: current.job,
          authenticationError,
          message: authenticationError
            ? "La clé API a été refusée. Vérifiez-la avant de reprendre le suivi."
            : "Connexion interrompue. Le job continue côté serveur et son suivi peut être repris.",
        };
      });
      if (authenticationError) {
        setAuthStatus("rejected");
      }
    },
    [pollingGenerationOperation, pollingIdentityRevision],
  );

  const polledJob =
    generationState.phase === "pending" ||
    generationState.phase === "processing"
      ? generationState.job
      : null;

  useDocumentPolling({
    jobId: polledJob?.id ?? null,
    apiKey: authStatus === "valid" ? credentialKey : null,
    enabled: polledJob !== null,
    retryToken: pollingRetryToken,
    onStatus: handlePolledStatus,
    onError: handlePollingError,
  });

  const resumeTracking = useCallback(() => {
    setGenerationState((current) => {
      if (current.phase !== "interrupted") {
        return current;
      }
      return {
        phase: current.job.status === "processing" ? "processing" : "pending",
        job: current.job,
      };
    });
    setPollingRetryToken((value) => value + 1);
  }, []);

  const allowUncertainRetry = useCallback(() => {
    setGenerationState((current) =>
      current.phase === "creation_error" && current.uncertain
        ? { phase: "idle" }
        : current,
    );
  }, []);

  const stopTracking = useCallback(() => {
    generationOperation.current += 1;
    generationAbortController.current?.abort();
    generationAbortController.current = null;
    creationInProgress.current = false;
    setPollingRetryToken((value) => value + 1);
    setGenerationState((current) =>
      current.phase === "interrupted" ? { phase: "idle" } : current,
    );
  }, []);

  const value = useMemo<AppContextValue>(
    () => ({
      auth: {
        status: authStatus,
        credentialKey,
        activeApiKey: authStatus === "valid" ? credentialKey : null,
        remember,
        storageError,
        authenticate,
        setRemember,
        clearCredential,
      },
      draft: {
        importedResume,
        avpNumber,
        profileValid: importedResume !== null,
        avpValid: validateAvpNumber(avpNumber) === null,
        selectedDocumentType,
        setAvpNumber,
        setSelectedDocumentType,
        acceptResume,
        removeResume,
      },
      generation: {
        state: generationState,
        start: startGeneration,
        allowUncertainRetry,
        resumeTracking,
        stopTracking,
      },
    }),
    [
      acceptResume,
      allowUncertainRetry,
      authenticate,
      authStatus,
      avpNumber,
      clearCredential,
      credentialKey,
      importedResume,
      generationState,
      remember,
      removeResume,
      resumeTracking,
      selectedDocumentType,
      setRemember,
      startGeneration,
      stopTracking,
      storageError,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}
