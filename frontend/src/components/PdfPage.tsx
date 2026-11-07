import { useEffect, useRef, useState } from "react";
import * as pdfjs from "pdfjs-dist";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { ChevronLeft, ChevronRight, FileWarning, Loader2 } from "lucide-react";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

const MIN_WIDTH = 300;

export function PdfPage({ url, page }: { url: string; page: number }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [document, setDocument] = useState<PDFDocumentProxy | null>(null);
  const [current, setCurrent] = useState(page);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setCurrent(page);
  }, [page]);

  useEffect(() => {
    let cancelled = false;
    const task = pdfjs.getDocument({ url, withCredentials: false });
    task.promise
      .then((loaded) => {
        if (!cancelled) {
          setDocument(loaded);
          setError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setError("No se pudo abrir el PDF");
      });
    return () => {
      cancelled = true;
      void task.destroy();
    };
  }, [url]);

  useEffect(() => {
    if (!document) return;
    let cancelled = false;
    let renderTask: RenderTask | null = null;

    const draw = async () => {
      const target = Math.max(1, Math.min(current, document.numPages));
      const pdfPage = await document.getPage(target);
      if (cancelled) return;

      const canvas = canvasRef.current;
      const container = containerRef.current;
      if (!canvas || !container) return;

      const base = pdfPage.getViewport({ scale: 1 });
      const available = Math.max(MIN_WIDTH, container.clientWidth - 2);
      const scale = Math.max(0.4, Math.min(2.4, available / base.width));
      const viewport = pdfPage.getViewport({ scale });
      const ratio = window.devicePixelRatio || 1;

      canvas.width = Math.floor(viewport.width * ratio);
      canvas.height = Math.floor(viewport.height * ratio);
      canvas.style.width = `${Math.floor(viewport.width)}px`;
      canvas.style.height = `${Math.floor(viewport.height)}px`;

      const context = canvas.getContext("2d");
      if (!context) return;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);

      renderTask = pdfPage.render({ canvasContext: context, viewport });
      try {
        await renderTask.promise;
      } catch {
        /* render cancelado */
      }
    };

    void draw();
    return () => {
      cancelled = true;
      renderTask?.cancel();
    };
  }, [document, current]);

  if (error) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-lg border border-rule bg-raised p-8 text-center text-sm text-muted">
        <FileWarning className="h-6 w-6 text-accent" />
        {error}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between text-[12px] text-muted">
        <button
          type="button"
          className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-rule hover:bg-accent-soft/50 disabled:opacity-40"
          onClick={() => setCurrent((value) => Math.max(1, value - 1))}
          disabled={current <= 1}
          aria-label="Pagina anterior"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <span>
          Pagina {current}
          {document ? ` de ${document.numPages}` : ""}
        </span>
        <button
          type="button"
          className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-rule hover:bg-accent-soft/50 disabled:opacity-40"
          onClick={() =>
            setCurrent((value) =>
              document ? Math.min(document.numPages, value + 1) : value + 1,
            )
          }
          disabled={Boolean(document && current >= document.numPages)}
          aria-label="Pagina siguiente"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>

      <div
        ref={containerRef}
        className="max-h-[60vh] overflow-auto rounded-lg border border-rule bg-raised p-1"
      >
        {!document && !error ? (
          <div className="flex h-40 items-center justify-center text-muted">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        ) : null}
        <canvas ref={canvasRef} className="mx-auto block" />
      </div>
    </div>
  );
}
