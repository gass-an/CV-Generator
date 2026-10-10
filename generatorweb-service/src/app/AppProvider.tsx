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
import { ApiError } from "@/services/apiClient";
import { verifyApiKey } from "@/services/authService";
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
  setAvpNumber: (value: string) => void;
  acceptResume: (parsed: ParsedResumeFile) => void;
  removeResume: () => void;
};

type AppContextValue = {
  auth: AuthState;
  draft: ApplicationDraftState;
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
  const validationInProgress = useRef(false);

  useEffect(() => {
    if (!storedAtStartup.key) {
      return;
    }
    const controller = new AbortController();
    verifyApiKey(storedAtStartup.key, controller.signal)
      .then(() => setAuthStatus("valid"))
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.kind === "aborted") {
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
      validationInProgress.current = true;
      if (!hadValidCredential) {
        setAuthStatus("verifying");
      }
      try {
        await verifyApiKey(normalized);
        setCredentialKey(normalized);
        setRememberState(shouldRemember);
        setAuthStatus("valid");
        setStorageError(persistCredential(normalized, shouldRemember));
        return { ok: true } satisfies AuthenticationResult;
      } catch (error) {
        const result = authenticationError(error);
        if (!hadValidCredential) {
          setAuthStatus(result.reason);
        }
        return result;
      } finally {
        validationInProgress.current = false;
      }
    },
    [authStatus, credentialKey],
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
    setStorageError(removeStoredCredentials());
    setCredentialKey(null);
    setRememberState(false);
    setAuthStatus("absent");
  }, []);

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
        setAvpNumber,
        acceptResume,
        removeResume,
      },
    }),
    [
      acceptResume,
      authenticate,
      authStatus,
      avpNumber,
      clearCredential,
      credentialKey,
      importedResume,
      remember,
      removeResume,
      setRemember,
      storageError,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}
