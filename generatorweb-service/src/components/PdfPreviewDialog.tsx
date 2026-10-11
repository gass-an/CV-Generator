import { X } from "lucide-react";
import { type ReactNode, useEffect, useId, useRef } from "react";

export function PdfPreviewDialog({
  title,
  subtitle,
  children,
  footer,
  opener,
  onClose,
}: {
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  opener?: HTMLElement;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDivElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const titleId = useId();

  useEffect(() => {
    closeButton.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !dialog.current) return;
      const focusable = Array.from(
        dialog.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], object, [tabindex]:not([tabindex="-1"])',
        ),
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable.at(-1)!;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (
        !event.shiftKey &&
        (document.activeElement === last ||
          !dialog.current.contains(document.activeElement))
      ) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      if (opener?.isConnected) opener.focus();
    };
  }, [onClose, opener]);

  return (
    <div
      ref={dialog}
      className="bg-overlay fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-2 sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      <div className="bg-card border-border my-auto flex max-h-[calc(100svh-1rem)] w-full max-w-5xl min-w-0 flex-col overflow-hidden rounded-xl border shadow-xl sm:max-h-[calc(100svh-3rem)]">
        <div className="border-border flex shrink-0 items-start justify-between gap-3 border-b p-3 sm:gap-4 sm:p-5">
          <div className="min-w-0">
            <h2 id={titleId} className="font-semibold break-words">
              {title}
            </h2>
            {subtitle ? (
              <p className="text-muted-foreground mt-1 text-sm break-words">
                {subtitle}
              </p>
            ) : null}
          </div>
          <button
            ref={closeButton}
            type="button"
            onClick={onClose}
            className="hover:bg-muted flex size-11 shrink-0 items-center justify-center rounded-lg"
            aria-label="Fermer la prévisualisation"
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        </div>
        <div className="bg-muted/50 min-h-0 overflow-y-auto p-2 sm:p-5">
          {children}
        </div>
        {footer ? (
          <div className="border-border shrink-0 border-t p-3 sm:p-5">
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  );
}
