import { useState } from "react";
import {
  AlertTriangle,
  FileText,
  FileType2,
  Globe,
  Image as ImageIcon,
  Link2,
  Loader2,
  Plus,
  Presentation,
  RefreshCw,
  Trash2,
  UploadCloud,
  Youtube,
} from "lucide-react";
import type { DocumentItem, SourceType, Subject } from "../types";
import { Banner, Button, Chip, EmptyState, Field, ProgressBar, cx, inputClass } from "./ui";
import { SOURCE_LABEL, STATUS_LABEL, formatBytes, timeAgo } from "../lib/format";

export interface UploadEntry {
  id: string;
  name: string;
  progress: number;
  error?: string;
}

const ICONS: Record<SourceType, React.ComponentType<{ className?: string }>> = {
  pdf: FileText,
  docx: FileText,
  pptx: Presentation,
  web: Globe,
  youtube: Youtube,
  image: ImageIcon,
  text: FileType2,
};

const ACCEPT =
  ".pdf,.docx,.pptx,.png,.jpg,.jpeg,.webp,.tif,.tiff,.txt,.md";

const STATUS_TONE = {
  ready: "success",
  error: "danger",
  reading: "accent",
  indexing: "accent",
  pending: "neutral",
} as const;

interface LibraryViewProps {
  subjects: Subject[];
  subject: Subject | null;
  documents: DocumentItem[];
  onSelectSubject: (id: string | null) => void;
  onCreateSubject: (name: string) => Promise<void>;
  onUpload: (files: File[]) => Promise<void>;
  onAddUrl: (url: string, kind: "web" | "youtube") => Promise<void>;
  onAddText: (title: string, text: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onReindex: (id: string) => Promise<void>;
  uploads: UploadEntry[];
}

export function LibraryView({
  subjects,
  subject,
  documents,
  onSelectSubject,
  onCreateSubject,
  onUpload,
  onAddUrl,
  onAddText,
  onDelete,
  onReindex,
  uploads,
}: LibraryViewProps) {
  const [dragging, setDragging] = useState(false);
  const [mode, setMode] = useState<"url" | "text" | null>(null);
  const [url, setUrl] = useState("");
  const [urlKind, setUrlKind] = useState<"web" | "youtube">("web");
  const [textTitle, setTextTitle] = useState("");
  const [textBody, setTextBody] = useState("");
  const [newSubject, setNewSubject] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFiles(files: FileList | File[]) {
    const list = Array.from(files);
    if (!list.length || !subject) return;
    setError(null);
    try {
      await onUpload(list);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo subir el archivo");
    }
  }

  async function submitUrl(event: React.FormEvent) {
    event.preventDefault();
    if (!url.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      await onAddUrl(url.trim(), urlKind);
      setUrl("");
      setMode(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo añadir el enlace");
    } finally {
      setBusy(false);
    }
  }

  async function submitText(event: React.FormEvent) {
    event.preventDefault();
    if (!textTitle.trim() || !textBody.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      await onAddText(textTitle.trim(), textBody.trim());
      setTextTitle("");
      setTextBody("");
      setMode(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo añadir el texto");
    } finally {
      setBusy(false);
    }
  }

  async function submitSubject(event: React.FormEvent) {
    event.preventDefault();
    if (!newSubject.trim()) return;
    try {
      await onCreateSubject(newSubject.trim());
      setNewSubject("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo crear la materia");
    }
  }

  const noSubject = !subject;

  return (
    <div className="scroll-thin h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-4xl px-5 py-8 md:px-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-accent">
              Biblioteca
            </p>
            <h1 className="mt-2 font-serif text-3xl">Tus materiales</h1>
            <p className="mt-2 max-w-xl text-sm leading-6 text-muted">
              Todo se indexa en tu equipo. Solo los fragmentos que se citan viajan al
              proveedor de IA que elijas.
            </p>
          </div>
          <div className="w-full sm:w-64">
            <Field label="Materia">
              <select
                value={subject?.id ?? ""}
                onChange={(event) => onSelectSubject(event.target.value || null)}
                className={inputClass}
              >
                {subjects.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        </div>

        {error ? (
          <div className="mt-5">
            <Banner tone="danger">{error}</Banner>
          </div>
        ) : null}

        {noSubject ? (
          <div className="mt-8 rounded-xl border border-rule bg-raised/80 p-6">
            <h2 className="font-serif text-xl">Crea una materia para empezar</h2>
            <p className="mt-1 text-sm text-muted">
              Cada documento se guarda dentro de una materia (por ejemplo, «Biología» o
              «Historia»).
            </p>
            <form onSubmit={submitSubject} className="mt-4 flex gap-2">
              <input
                value={newSubject}
                onChange={(event) => setNewSubject(event.target.value)}
                placeholder="Nombre de la materia"
                className={inputClass}
              />
              <Button type="submit" variant="primary">
                <Plus className="h-4 w-4" />
                Crear
              </Button>
            </form>
          </div>
        ) : (
          <>
            <div
              onDragOver={(event) => {
                event.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => {
                event.preventDefault();
                setDragging(false);
                void handleFiles(event.dataTransfer.files);
              }}
              className={cx(
                "mt-8 rounded-xl border-2 border-dashed p-8 text-center transition",
                dragging
                  ? "border-accent bg-accent-soft/60"
                  : "border-rule bg-raised/60 hover:border-accent/40",
              )}
            >
              <UploadCloud className="mx-auto h-7 w-7 text-accent" />
              <p className="mt-3 text-sm font-medium text-ink">
                Arrastra tus archivos aquí o elige uno
              </p>
              <p className="mt-1 text-[12px] text-muted">
                PDF, Word, PowerPoint, imágenes y texto · hasta 50 MB por archivo
              </p>
              <label className="mt-4 inline-flex cursor-pointer items-center justify-center rounded-lg border border-accent bg-accent px-4 py-2 text-sm font-medium text-accent-ink transition hover:brightness-105">
                Seleccionar archivos
                <input
                  type="file"
                  accept={ACCEPT}
                  multiple
                  className="hidden"
                  onChange={(event) => {
                    if (event.target.files) void handleFiles(event.target.files);
                    event.target.value = "";
                  }}
                />
              </label>

              <div className="mt-4 flex flex-wrap justify-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setMode(mode === "url" ? null : "url")}
                >
                  <Link2 className="h-3.5 w-3.5" />
                  Añadir enlace
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setMode(mode === "text" ? null : "text")}
                >
                  <FileType2 className="h-3.5 w-3.5" />
                  Pegar texto
                </Button>
              </div>
            </div>

            {mode === "url" ? (
              <form
                onSubmit={submitUrl}
                className="mt-4 rounded-xl border border-rule bg-raised p-4"
              >
                <div className="flex flex-wrap items-end gap-3">
                  <div className="w-40">
                    <Field label="Tipo">
                      <select
                        value={urlKind}
                        onChange={(event) =>
                          setUrlKind(event.target.value as "web" | "youtube")
                        }
                        className={inputClass}
                      >
                        <option value="web">Página web</option>
                        <option value="youtube">Vídeo de YouTube</option>
                      </select>
                    </Field>
                  </div>
                  <div className="min-w-[220px] flex-1">
                    <Field label="Enlace">
                      <input
                        value={url}
                        onChange={(event) => setUrl(event.target.value)}
                        placeholder="https://…"
                        className={inputClass}
                        autoFocus
                      />
                    </Field>
                  </div>
                  <Button type="submit" variant="primary" disabled={busy}>
                    {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                    Añadir
                  </Button>
                </div>
              </form>
            ) : null}

            {mode === "text" ? (
              <form
                onSubmit={submitText}
                className="mt-4 space-y-3 rounded-xl border border-rule bg-raised p-4"
              >
                <Field label="Título">
                  <input
                    value={textTitle}
                    onChange={(event) => setTextTitle(event.target.value)}
                    placeholder="Tema 4: apuntes de clase"
                    className={inputClass}
                    autoFocus
                  />
                </Field>
                <Field label="Contenido">
                  <textarea
                    value={textBody}
                    onChange={(event) => setTextBody(event.target.value)}
                    rows={6}
                    placeholder="Pega aquí tus apuntes…"
                    className={cx(inputClass, "resize-y")}
                  />
                </Field>
                <div className="flex justify-end">
                  <Button type="submit" variant="primary" disabled={busy}>
                    {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                    Guardar texto
                  </Button>
                </div>
              </form>
            ) : null}

            {uploads.length > 0 ? (
              <div className="mt-5 space-y-2">
                {uploads.map((entry) => (
                  <div
                    key={entry.id}
                    className="rounded-lg border border-rule bg-raised px-3 py-2"
                  >
                    <div className="flex items-center justify-between text-[12px]">
                      <span className="truncate">{entry.name}</span>
                      <span className="text-muted">
                        {entry.error ? "error" : `${Math.round(entry.progress * 100)}%`}
                      </span>
                    </div>
                    <div className="mt-1.5">
                      {entry.error ? (
                        <p className="text-[11px] text-danger">{entry.error}</p>
                      ) : (
                        <ProgressBar value={entry.progress} />
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : null}

            <div className="mt-8">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="font-serif text-lg">
                  {documents.length} documento{documents.length === 1 ? "" : "s"}
                </h2>
                <span className="text-[11px] uppercase tracking-wide text-muted">
                  {subject.name}
                </span>
              </div>

              {documents.length === 0 ? (
                <div className="rounded-xl border border-rule bg-raised/60">
                  <EmptyState
                    icon={<FileText className="h-8 w-8" />}
                    title="Aún no hay documentos en esta materia"
                    description="Sube tus apuntes, un PDF o un enlace y podrás preguntarle a Chuletín sobre ellos."
                  />
                </div>
              ) : (
                <ul className="divide-y divide-rule overflow-hidden rounded-xl border border-rule bg-raised/70">
                  {documents.map((document) => {
                    const Icon = ICONS[document.source_type];
                    const processing =
                      document.status === "reading" || document.status === "indexing";
                    return (
                      <li key={document.id} className="px-4 py-3">
                        <div className="flex items-start gap-3">
                          <span className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-rule bg-paper text-accent">
                            <Icon className="h-4 w-4" />
                          </span>
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="truncate text-sm font-medium text-ink">
                                {document.title}
                              </span>
                              <Chip tone={STATUS_TONE[document.status]}>
                                {STATUS_LABEL[document.status]}
                              </Chip>
                            </div>
                            <p className="mt-0.5 text-[11px] text-muted">
                              {SOURCE_LABEL[document.source_type]}
                              {document.page_count ? ` · ${document.page_count} pág.` : ""}
                              {document.chunk_count
                                ? ` · ${document.chunk_count} fragmentos`
                                : ""}
                              {document.size_bytes
                                ? ` · ${formatBytes(document.size_bytes)}`
                                : ""}
                              {` · ${timeAgo(document.created_at)}`}
                            </p>

                            {processing ? (
                              <div className="mt-2 max-w-sm">
                                <ProgressBar value={document.progress} />
                              </div>
                            ) : null}

                            {document.error ? (
                              <p className="mt-1.5 flex items-start gap-1 text-[11px] leading-5 text-danger">
                                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                                {document.error}
                              </p>
                            ) : null}
                          </div>

                          <div className="flex shrink-0 items-center gap-1">
                            <button
                              type="button"
                              onClick={() => void onReindex(document.id)}
                              disabled={processing}
                              className="rounded-md p-1.5 text-muted transition hover:bg-accent-soft/60 hover:text-ink disabled:opacity-40"
                              aria-label="Reindexar"
                              title="Reindexar"
                            >
                              <RefreshCw className="h-3.5 w-3.5" />
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                if (
                                  window.confirm(
                                    `¿Borrar «${document.title}»? Se eliminarán también sus fragmentos y citas.`,
                                  )
                                ) {
                                  void onDelete(document.id);
                                }
                              }}
                              className="rounded-md p-1.5 text-muted transition hover:bg-danger/10 hover:text-danger"
                              aria-label="Borrar"
                              title="Borrar"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
