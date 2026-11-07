import { lazy, Suspense } from "react";
import { ExternalLink, Loader2, Quote, X } from "lucide-react";
import type { Citation, DocumentItem } from "../types";
import { Chip } from "./ui";
import { SOURCE_LABEL, locatorFor } from "../lib/format";
import { api } from "../lib/api";

// El visor de PDF pesa bastante: se carga solo cuando hace falta.
const PdfPage = lazy(() =>
  import("./PdfPage").then((module) => ({ default: module.PdfPage })),
);

const LOCAL_FILE_TYPES = new Set(["pdf", "docx", "pptx", "image", "text"]);

export function SourcePanel({
  citation,
  document,
  onClose,
}: {
  citation: Citation | null;
  document: DocumentItem | undefined;
  onClose: () => void;
}) {
  if (!citation) return null;

  const locator = citation.locator ?? locatorFor(citation.source_type, citation.page_from);
  const canOpenFile = LOCAL_FILE_TYPES.has(citation.source_type);

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <button
        type="button"
        className="absolute inset-0 bg-ink/25 backdrop-blur-[1px]"
        onClick={onClose}
        aria-label="Cerrar fuente"
      />
      <aside className="relative flex h-full w-full max-w-md flex-col border-l border-rule bg-paper shadow-paper">
        <header className="flex items-center justify-between border-b border-rule px-5 py-4">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-6 min-w-6 items-center justify-center rounded bg-highlight px-1.5 text-[12px] font-semibold">
              {citation.index}
            </span>
            <h2 className="font-serif text-lg">Fuente</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 text-muted hover:bg-accent-soft/60 hover:text-ink"
            aria-label="Cerrar"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="scroll-thin flex-1 overflow-y-auto px-5 py-4">
          <h3 className="text-[15px] font-semibold leading-6">{citation.document_title}</h3>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <Chip tone="accent">{SOURCE_LABEL[citation.source_type]}</Chip>
            {locator ? <Chip>{locator}</Chip> : null}
            {citation.heading ? <Chip>{citation.heading}</Chip> : null}
          </div>

          <div className="mt-5 rounded-lg border border-rule bg-raised p-4">
            <Quote className="mb-2 h-4 w-4 text-accent/70" />
            <p className="whitespace-pre-wrap text-[13.5px] leading-6 text-ink/90">
              {citation.snippet}
            </p>
          </div>

          {document && citation.source_type === "pdf" && citation.page_from ? (
            <div className="mt-5">
              <Suspense
                fallback={
                  <div className="flex h-40 items-center justify-center rounded-lg border border-rule bg-raised text-muted">
                    <Loader2 className="h-5 w-5 animate-spin" />
                  </div>
                }
              >
                <PdfPage
                  url={api.documents.fileUrl(document.id)}
                  page={citation.page_from}
                />
              </Suspense>
            </div>
          ) : null}

          {document && citation.source_type === "image" ? (
            <div className="mt-5 overflow-hidden rounded-lg border border-rule bg-raised">
              <img
                src={api.documents.fileUrl(document.id)}
                alt={citation.document_title}
                className="max-h-[60vh] w-full object-contain"
              />
            </div>
          ) : null}

          {citation.source_type === "web" || citation.source_type === "youtube" ? (
            <p className="mt-4 text-[12px] leading-5 text-muted">
              Fuente original:{" "}
              {document?.source_uri ? (
                <a
                  href={document.source_uri}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent underline underline-offset-2"
                >
                  {document.source_uri}
                </a>
              ) : (
                "enlace no disponible"
              )}
            </p>
          ) : null}
        </div>

        <footer className="flex items-center justify-between gap-3 border-t border-rule px-5 py-3">
          <span className="text-[11px] text-muted">
            Fragmento citado de tus apuntes
          </span>
          {canOpenFile && document ? (
            <a
              href={api.documents.fileUrl(document.id)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg border border-rule bg-raised px-3 py-1.5 text-[12px] font-medium hover:border-accent/50"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              Abrir documento
            </a>
          ) : null}
        </footer>
      </aside>
    </div>
  );
}
