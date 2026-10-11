import { Eye, FileClock, LoaderCircle, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { DocumentDownloadActions } from "@/components/DocumentDownloadActions";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { PdfPreviewDialog } from "@/components/PdfPreviewDialog";
import { PdfViewer } from "@/components/PdfViewer";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useAppState } from "@/hooks/useAppState";
import { ApiError } from "@/services/apiClient";
import { getDocumentHistory } from "@/services/documentService";
import {
  documentStatusLabels,
  documentTypeLabels,
  type DocumentHistoryItem,
  type DocumentJobStatus,
  type DocumentMetadata,
  type DocumentType,
} from "@/types/document";

const PAGE_SIZE = 20;

function metadata(item: DocumentHistoryItem): DocumentMetadata {
  return {
    id: item.id,
    documentType: item.type,
    status: item.status,
    avpNumber: item.avp_number,
    candidateName: item.candidate_name,
    createdAt: item.created_at,
  };
}

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Date inconnue"
    : new Intl.DateTimeFormat("fr-FR", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date);
}

function statusVariant(status: DocumentJobStatus) {
  if (status === "completed" || status === "processing")
    return "default" as const;
  if (status === "failed") return "accent" as const;
  return "outline" as const;
}

type OwnedSelection = {
  item: DocumentHistoryItem;
  apiKey: string;
  opener?: HTMLButtonElement;
};

function PreviewDialog({
  selection,
  onClose,
  onApiKeyRejected,
}: {
  selection: OwnedSelection;
  onClose: () => void;
  onApiKeyRejected: (apiKey: string) => void;
}) {
  const item = selection.item;
  return (
    <PdfPreviewDialog
      title={documentTypeLabels[item.type]}
      subtitle={
        <>
          {item.candidate_name || "Candidat non renseigné"} · AVP{" "}
          {item.avp_number}
        </>
      }
      opener={selection.opener}
      onClose={onClose}
      footer={<DocumentDownloadActions document={metadata(item)} />}
    >
      <PdfViewer
        documentId={item.id}
        apiKey={selection.apiKey}
        enabled
        title={`Aperçu PDF — ${documentTypeLabels[item.type]}`}
        onApiKeyRejected={onApiKeyRejected}
      />
    </PdfPreviewDialog>
  );
}

export function HistoryPage() {
  const { auth, generation } = useAppState();
  const { reportApiKeyRejected } = auth;
  const navigate = useNavigate();
  const [items, setItems] = useState<DocumentHistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [typeFilter, setTypeFilter] = useState<DocumentType | "">("");
  const [statusFilter, setStatusFilter] = useState<DocumentJobStatus | "">("");
  const [refreshToken, setRefreshToken] = useState(0);
  const [loadState, setLoadState] = useState<
    "idle" | "loading" | "ready" | "error" | "rejected"
  >("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [loadedApiKey, setLoadedApiKey] = useState<string | null>(null);
  const [previewed, setPreviewed] = useState<OwnedSelection | null>(null);
  const [replacement, setReplacement] = useState<OwnedSelection | null>(null);
  const requestSequence = useRef(0);

  useEffect(() => {
    const sequence = ++requestSequence.current;
    if (auth.status !== "valid" || !auth.activeApiKey) {
      return;
    }
    const controller = new AbortController();
    queueMicrotask(() => {
      if (requestSequence.current !== sequence) return;
      setPreviewed(null);
      setReplacement(null);
      setItems([]);
      setLoadState("loading");
      setErrorMessage("");
    });
    getDocumentHistory(
      {
        limit: PAGE_SIZE,
        offset,
        documentType: typeFilter || undefined,
        status: statusFilter || undefined,
      },
      auth.activeApiKey,
      controller.signal,
    )
      .then((page) => {
        if (requestSequence.current !== sequence) return;
        setItems(page.items);
        setTotal(page.total);
        setLoadedApiKey(auth.activeApiKey);
        setLoadState("ready");
      })
      .catch((error: unknown) => {
        if (
          requestSequence.current !== sequence ||
          (error instanceof ApiError && error.kind === "aborted")
        )
          return;
        if (error instanceof ApiError && error.status === 401) {
          reportApiKeyRejected(auth.activeApiKey!);
        }
        setItems([]);
        setTotal(0);
        setLoadedApiKey(auth.activeApiKey);
        setLoadState(
          error instanceof ApiError && error.status === 401
            ? "rejected"
            : "error",
        );
        setErrorMessage(
          error instanceof ApiError
            ? error.message
            : "Impossible de charger l'historique.",
        );
      });
    return () => controller.abort();
  }, [
    auth.activeApiKey,
    auth.status,
    offset,
    refreshToken,
    reportApiKeyRejected,
    statusFilter,
    typeFilter,
  ]);

  function changeType(value: DocumentType | "") {
    setOffset(0);
    setTypeFilter(value);
  }

  function changeStatus(value: DocumentJobStatus | "") {
    setOffset(0);
    setStatusFilter(value);
  }

  function follow(selection: OwnedSelection, replace = false) {
    const { item, apiKey } = selection;
    if (apiKey !== auth.activeApiKey || auth.status !== "valid") return;
    const result = generation.trackExistingJob(item, replace);
    if (result === "confirmation_required") {
      setReplacement(selection);
      return;
    }
    setReplacement(null);
    void navigate("/");
  }

  const pageNumber = Math.floor(offset / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const noFilters = !typeFilter && !statusFilter;
  const historyMatchesIdentity = loadedApiKey === auth.activeApiKey;
  const visibleItems = historyMatchesIdentity ? items : [];
  const visibleLoadState = historyMatchesIdentity ? loadState : "loading";
  const selectionIsAuthorized = (selection: OwnedSelection | null) =>
    selection !== null &&
    auth.status === "valid" &&
    selection.apiKey === auth.activeApiKey &&
    historyMatchesIdentity &&
    visibleItems.some((item) => item.id === selection.item.id);
  const visiblePreview = selectionIsAuthorized(previewed) ? previewed : null;
  const visibleReplacement = selectionIsAuthorized(replacement)
    ? replacement
    : null;
  const closePreview = useCallback(() => setPreviewed(null), []);

  return (
    <div className="w-full space-y-8">
      <PageHeader
        eyebrow="Vos candidatures"
        title="Historique des documents"
        description="Retrouvez les générations du client associé à votre clé API, reprenez leur suivi et récupérez leurs fichiers."
      />

      {auth.status === "absent" ||
      auth.status === "rejected" ||
      auth.status === "unavailable" ? (
        <Card className="p-6 text-center">
          <p className="font-semibold">Une clé API valide est nécessaire.</p>
          <p className="text-muted-foreground mt-2 text-sm">
            Configurez ou vérifiez votre clé pour accéder à l'historique de
            votre client.
          </p>
          <Link
            to="/parametres"
            className="bg-primary text-primary-foreground mt-5 inline-flex min-h-11 items-center rounded-lg px-5 text-sm font-semibold"
          >
            Ouvrir les paramètres
          </Link>
        </Card>
      ) : auth.status === "verifying" ? (
        <Card className="flex min-h-48 flex-col items-center justify-center">
          <LoaderCircle
            className="text-primary size-7 animate-spin"
            aria-hidden="true"
          />
          <p className="mt-3 font-semibold">Vérification de la clé API…</p>
        </Card>
      ) : (
        <>
          <Card className="p-4 sm:p-5">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_auto] lg:items-end">
              <label className="text-sm font-semibold">
                Type de document
                <select
                  aria-label="Filtrer par type"
                  value={typeFilter}
                  onChange={(event) =>
                    changeType(event.target.value as DocumentType | "")
                  }
                  className="border-border bg-card mt-2 min-h-11 w-full rounded-lg border px-3 font-normal"
                >
                  <option value="">Tous</option>
                  <option value="cv">CV</option>
                  <option value="cover_letter">Lettre de motivation</option>
                  <option value="interview_prep">
                    Préparation à l'entretien
                  </option>
                </select>
              </label>
              <label className="text-sm font-semibold">
                Statut
                <select
                  aria-label="Filtrer par statut"
                  value={statusFilter}
                  onChange={(event) =>
                    changeStatus(event.target.value as DocumentJobStatus | "")
                  }
                  className="border-border bg-card mt-2 min-h-11 w-full rounded-lg border px-3 font-normal"
                >
                  <option value="">Tous</option>
                  <option value="pending">En attente</option>
                  <option value="processing">En cours</option>
                  <option value="completed">Terminé</option>
                  <option value="failed">Échec</option>
                </select>
              </label>
              <button
                type="button"
                disabled={visibleLoadState === "loading"}
                onClick={() => setRefreshToken((value) => value + 1)}
                className="border-border text-primary hover:bg-primary/5 flex min-h-11 items-center justify-center gap-2 rounded-lg border px-4 text-sm font-semibold disabled:opacity-50"
              >
                <RefreshCw
                  className={`size-4 ${visibleLoadState === "loading" ? "animate-spin" : ""}`}
                  aria-hidden="true"
                />
                Actualiser
              </button>
            </div>
          </Card>

          {visibleReplacement ? (
            <div
              className="border-accent/20 bg-accent/5 rounded-xl border p-4"
              role="alert"
            >
              <p className="font-semibold">Un autre document est déjà suivi.</p>
              <p className="text-muted-foreground mt-1 text-sm">
                Le remplacer arrête seulement son suivi local, sans annuler son
                traitement serveur.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => follow(visibleReplacement, true)}
                  className="bg-accent text-accent-foreground min-h-10 rounded-lg px-4 text-sm font-semibold"
                >
                  Remplacer le suivi local
                </button>
                <button
                  type="button"
                  onClick={() => setReplacement(null)}
                  className="border-border min-h-10 rounded-lg border px-4 text-sm font-semibold"
                >
                  Conserver le suivi actuel
                </button>
              </div>
            </div>
          ) : null}

          {visibleLoadState === "loading" ? (
            <Card className="flex min-h-64 flex-col items-center justify-center">
              <LoaderCircle
                className="text-primary size-8 animate-spin"
                aria-hidden="true"
              />
              <p className="mt-4 font-semibold">Chargement de l'historique…</p>
            </Card>
          ) : visibleLoadState === "error" ||
            visibleLoadState === "rejected" ? (
            <Card className="p-8 text-center" role="alert">
              <p className="font-semibold">
                {visibleLoadState === "rejected"
                  ? "La clé API a été refusée."
                  : "L'historique est momentanément indisponible."}
              </p>
              <p className="text-muted-foreground mt-2 text-sm">
                {errorMessage}
              </p>
              <div className="mt-5 flex justify-center gap-3">
                {visibleLoadState === "rejected" ? (
                  <Link
                    to="/parametres"
                    className="bg-primary text-primary-foreground min-h-11 rounded-lg px-5 py-3 text-sm font-semibold"
                  >
                    Vérifier la clé
                  </Link>
                ) : (
                  <button
                    type="button"
                    onClick={() => setRefreshToken((value) => value + 1)}
                    className="bg-primary text-primary-foreground min-h-11 rounded-lg px-5 text-sm font-semibold"
                  >
                    Réessayer
                  </button>
                )}
              </div>
            </Card>
          ) : visibleLoadState === "ready" && visibleItems.length === 0 ? (
            <Card className="overflow-hidden py-0">
              <EmptyState
                icon={FileClock}
                title={
                  noFilters
                    ? "Aucun document à afficher pour le moment"
                    : "Aucun document ne correspond aux filtres"
                }
                description={
                  noFilters
                    ? "Vos futurs documents apparaîtront ici après leur génération."
                    : "Modifiez les filtres ou actualisez l'historique."
                }
              />
            </Card>
          ) : visibleLoadState === "ready" ? (
            <Card className="overflow-hidden py-0">
              <div className="divide-border divide-y">
                {visibleItems.map((item) => (
                  <article
                    key={item.id}
                    className="grid gap-4 p-5 lg:grid-cols-[1.2fr_1fr_1fr_auto] lg:items-center"
                  >
                    <div>
                      <p className="font-semibold">
                        {documentTypeLabels[item.type]}
                      </p>
                      <p className="text-muted-foreground mt-1 text-sm">
                        {item.candidate_name || "Candidat non renseigné"}
                      </p>
                    </div>
                    <div className="text-sm">
                      <p className="font-medium break-all">
                        AVP {item.avp_number}
                      </p>
                      <p className="text-muted-foreground mt-1 text-xs">
                        {formatDate(item.created_at)}
                      </p>
                    </div>
                    <Badge
                      variant={statusVariant(item.status)}
                      className="w-fit"
                    >
                      {documentStatusLabels[item.status]}
                    </Badge>
                    <div className="flex flex-wrap gap-2 lg:justify-end">
                      {item.status === "pending" ||
                      item.status === "processing" ? (
                        <button
                          type="button"
                          onClick={(event) =>
                            follow({
                              item,
                              apiKey: auth.activeApiKey!,
                              opener: event.currentTarget,
                            })
                          }
                          className="border-border text-primary hover:bg-primary/5 min-h-10 rounded-lg border px-3 text-sm font-semibold"
                        >
                          Reprendre le suivi
                        </button>
                      ) : null}
                      {item.status === "completed" ? (
                        <>
                          <button
                            type="button"
                            onClick={(event) =>
                              setPreviewed({
                                item,
                                apiKey: auth.activeApiKey!,
                                opener: event.currentTarget,
                              })
                            }
                            className="border-border text-primary hover:bg-primary/5 flex min-h-10 items-center gap-2 rounded-lg border px-3 text-sm font-semibold"
                          >
                            <Eye className="size-4" aria-hidden="true" />
                            Prévisualiser
                          </button>
                          <DocumentDownloadActions
                            document={metadata(item)}
                            compact
                          />
                        </>
                      ) : null}
                    </div>
                  </article>
                ))}
              </div>
              <div className="border-border flex flex-col gap-3 border-t px-5 py-4 text-sm sm:flex-row sm:items-center sm:justify-between">
                <p className="text-muted-foreground">
                  Page {pageNumber} sur {pageCount} · {total} document
                  {total > 1 ? "s" : ""}
                </p>
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={offset === 0}
                    onClick={() =>
                      setOffset((value) => Math.max(0, value - PAGE_SIZE))
                    }
                    className="border-border min-h-10 rounded-lg border px-4 font-semibold disabled:opacity-40"
                  >
                    Précédente
                  </button>
                  <button
                    type="button"
                    disabled={offset + PAGE_SIZE >= total}
                    onClick={() => setOffset((value) => value + PAGE_SIZE)}
                    className="border-border min-h-10 rounded-lg border px-4 font-semibold disabled:opacity-40"
                  >
                    Suivante
                  </button>
                </div>
              </div>
            </Card>
          ) : null}
        </>
      )}

      {visiblePreview ? (
        <PreviewDialog
          selection={visiblePreview}
          onClose={closePreview}
          onApiKeyRejected={reportApiKeyRejected}
        />
      ) : null}
    </div>
  );
}
