import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  BookOpenCheck,
  Brain,
  ClipboardList,
  FileText,
  ListTree,
  Loader2,
  Sparkles,
  Trash2,
} from "lucide-react";
import type { Citation, StudyDetail, StudyKind, StudySet, Subject } from "../types";
import { api } from "../lib/api";
import { Markdown } from "./Markdown";
import { DeckReview } from "./DeckReview";
import { QuizRunner } from "./QuizRunner";
import {
  Banner,
  Button,
  Chip,
  EmptyState,
  Field,
  Spinner,
  cx,
  inputClass,
} from "./ui";
import { formatDate } from "../lib/format";

type Tab = "reading" | "cards" | "quiz";

const TAB_KINDS: Record<Tab, StudyKind[]> = {
  reading: ["summary", "outline"],
  cards: ["deck"],
  quiz: ["quiz"],
};

const KIND_META: Record<StudyKind, { label: string; icon: typeof FileText }> = {
  summary: { label: "Resumen", icon: FileText },
  outline: { label: "Esquema", icon: ListTree },
  deck: { label: "Tarjetas", icon: Brain },
  quiz: { label: "Test", icon: ClipboardList },
};

interface StudyViewProps {
  subject: Subject | null;
  subjects: Subject[];
  onSelectSubject: (id: string | null) => void;
  onCitation: (citation: Citation) => void;
  onOpenSettings: () => void;
  providerReady: boolean;
}

export function StudyView({
  subject,
  subjects,
  onSelectSubject,
  onCitation,
  onOpenSettings,
  providerReady,
}: StudyViewProps) {
  const [tab, setTab] = useState<Tab>("reading");
  const [sets, setSets] = useState<StudySet[]>([]);
  const [detail, setDetail] = useState<StudyDetail | null>(null);
  const [topic, setTopic] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const loadSets = useCallback(async () => {
    if (!subject) {
      setSets([]);
      return;
    }
    const next = await api.study.list(subject.id);
    setSets(next);
  }, [subject?.id]);

  useEffect(() => {
    setDetail(null);
    setError(null);
    if (!subject) {
      setSets([]);
      return;
    }
    setLoading(true);
    loadSets()
      .catch((caught) =>
        setError(caught instanceof Error ? caught.message : "No se pudo cargar"),
      )
      .finally(() => setLoading(false));
  }, [subject?.id, loadSets]);

  const hasGenerating =
    sets.some((item) => item.status === "generating") ||
    detail?.set.status === "generating";

  const activeIdRef = useRef<string | null>(null);
  useEffect(() => {
    activeIdRef.current = detail?.set.id ?? null;
  }, [detail?.set.id]);

  useEffect(() => {
    if (!hasGenerating || !subject) return;
    const timer = window.setInterval(() => {
      void loadSets().catch(() => undefined);
      const activeId = activeIdRef.current;
      if (activeId) {
        void api.study
          .get(activeId)
          .then((fresh) => setDetail(fresh))
          .catch(() => undefined);
      }
    }, 2500);
    return () => window.clearInterval(timer);
  }, [hasGenerating, subject?.id, loadSets]);

  async function generate(kind: StudyKind) {
    if (!subject || busy) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api.study.create({
        subject_id: subject.id,
        kind,
        topic: topic.trim() || null,
      });
      setTopic("");
      await loadSets();
      const fresh = await api.study.get(created.id);
      setDetail(fresh);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo generar");
    } finally {
      setBusy(false);
    }
  }

  async function openSet(id: string) {
    setError(null);
    try {
      const fresh = await api.study.get(id);
      setDetail(fresh);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo abrir");
    }
  }

  async function removeSet(id: string) {
    if (!window.confirm("¿Borrar este material de estudio?")) return;
    try {
      await api.study.remove(id);
      if (detail?.set.id === id) setDetail(null);
      await loadSets();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo borrar");
    }
  }

  if (!subject) {
    return (
      <div className="mx-auto max-w-3xl px-5 py-16 text-center">
        <BookOpenCheck className="mx-auto h-8 w-8 text-accent" />
        <h1 className="mt-3 font-serif text-2xl">Elige una materia</h1>
        <p className="mt-2 text-sm text-muted">
          El material de estudio se genera a partir de los documentos de una materia.
        </p>
        {subjects.length > 0 ? (
          <div className="mt-5 flex flex-wrap justify-center gap-2">
            {subjects.map((item) => (
              <Button key={item.id} onClick={() => onSelectSubject(item.id)}>
                {item.name}
              </Button>
            ))}
          </div>
        ) : (
          <p className="mt-4 text-sm text-muted">
            Primero sube documentos en la biblioteca.
          </p>
        )}
      </div>
    );
  }

  const visibleSets = sets.filter((item) => TAB_KINDS[tab].includes(item.kind));

  return (
    <div className="scroll-thin h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-4xl px-5 py-8 md:px-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-accent">
              Estudiar
            </p>
            <h1 className="mt-2 font-serif text-3xl">Material de repaso</h1>
            <p className="mt-2 max-w-xl text-sm leading-6 text-muted">
              Se genera solo con tus documentos y cada dato lleva su fuente. El repaso
              espaciado decide cuándo volver a mostrarte cada tarjeta.
            </p>
          </div>
          <div className="w-full sm:w-64">
            <Field label="Materia">
              <select
                value={subject.id}
                onChange={(event) => onSelectSubject(event.target.value)}
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
          <div className="mt-4">
            <Banner tone="danger">{error}</Banner>
          </div>
        ) : null}

        {detail ? (
          <div className="mt-6">
            <button
              type="button"
              onClick={() => setDetail(null)}
              className="mb-3 inline-flex items-center gap-1 text-[12px] text-muted hover:text-ink"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Volver a la lista
            </button>

            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="font-serif text-2xl">{detail.set.title}</h2>
                <Chip tone="accent">{KIND_META[detail.set.kind].label}</Chip>
                {detail.set.status === "generating" ? (
                  <Chip tone="warning">generando</Chip>
                ) : null}
                {detail.set.provider ? (
                  <Chip>
                    {detail.set.provider}
                    {detail.set.model ? ` · ${detail.set.model}` : ""}
                  </Chip>
                ) : null}
              </div>
              <button
                type="button"
                onClick={() => void removeSet(detail.set.id)}
                className="rounded-md p-1.5 text-muted hover:bg-danger/10 hover:text-danger"
                aria-label="Borrar material"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>

            {detail.set.status === "generating" ? (
              <div className="rounded-xl border border-rule bg-raised/70 p-10 text-center">
                <Loader2 className="mx-auto h-6 w-6 animate-spin text-accent" />
                <p className="mt-3 text-sm font-medium">Generando con tus apuntes…</p>
                <p className="mt-1 text-[12px] text-muted">
                  Puede tardar entre 20 y 60 segundos según el proveedor.
                </p>
              </div>
            ) : detail.set.status === "error" ? (
              <div className="rounded-xl border border-rule bg-raised/70 p-6">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
                  <div>
                    <p className="text-sm font-medium">No se pudo generar</p>
                    <p className="mt-1 text-[13px] leading-6 text-muted">
                      {detail.set.error ?? "Error desconocido"}
                    </p>
                  </div>
                </div>
                <div className="mt-4 flex gap-2">
                  <Button
                    variant="primary"
                    onClick={() => void generate(detail.set.kind)}
                    disabled={busy}
                  >
                    Reintentar
                  </Button>
                  <Button variant="secondary" onClick={() => setDetail(null)}>
                    Volver
                  </Button>
                </div>
              </div>
            ) : detail.set.kind === "deck" ? (
              <DeckReview
                cards={detail.cards ?? []}
                citations={detail.citations}
                onReview={(cardId, rating) => api.study.reviewCard(cardId, rating)}
                onCitation={onCitation}
                onBack={() => {
                  setDetail(null);
                  void loadSets();
                }}
              />
            ) : detail.set.kind === "quiz" ? (
              <QuizRunner
                items={detail.items ?? []}
                citations={detail.citations}
                onAnswer={(itemId, chosen) =>
                  api.study.answer(detail.set.id, itemId, chosen)
                }
                onReset={async () => {
                  await api.study.resetQuiz(detail.set.id);
                }}
                onCitation={onCitation}
                onBack={() => {
                  setDetail(null);
                  void loadSets();
                }}
              />
            ) : (
              <div>
                <article className="rounded-xl border border-rule bg-raised/80 p-6 shadow-paper md:p-8">
                  <Markdown
                    content={detail.set.content ?? ""}
                    onCitation={(index) => {
                      const citation = detail.citations.find((c) => c.index === index);
                      if (citation) onCitation(citation);
                    }}
                  />
                </article>

                {detail.citations.length > 0 ? (
                  <div className="mt-4 flex flex-wrap gap-1.5">
                    {detail.citations.map((citation) => (
                      <button
                        key={citation.index}
                        type="button"
                        onClick={() => onCitation(citation)}
                        className="inline-flex max-w-full items-center gap-1.5 rounded-lg border border-rule bg-raised/70 px-2 py-1 text-[11px] text-muted hover:border-accent/50 hover:text-ink"
                      >
                        <span className="inline-flex h-4 min-w-4 items-center justify-center rounded bg-highlight px-1 font-semibold text-ink">
                          {citation.index}
                        </span>
                        <span className="max-w-[220px] truncate">
                          {citation.document_title}
                        </span>
                        {citation.locator ? <span>· {citation.locator}</span> : null}
                      </button>
                    ))}
                  </div>
                ) : null}

                <div className="mt-5 flex flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    onClick={() => void generate(detail.set.kind)}
                    disabled={busy}
                  >
                    {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                    Generar otra versión
                  </Button>
                </div>
              </div>
            )}
          </div>
        ) : (
          <>
            <div className="mt-6 flex gap-1 rounded-lg border border-rule bg-raised/60 p-1">
              {(
                [
                  ["reading", "Resúmenes", FileText],
                  ["cards", "Tarjetas", Brain],
                  ["quiz", "Tests", ClipboardList],
                ] as Array<[Tab, string, typeof FileText]>
              ).map(([value, label, Icon]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setTab(value)}
                  className={cx(
                    "flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-2 text-[13px] font-medium transition",
                    tab === value
                      ? "bg-accent-soft text-ink"
                      : "text-muted hover:text-ink",
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {label}
                </button>
              ))}
            </div>

            <div className="mt-4 rounded-xl border border-rule bg-raised/70 p-5">
              {!providerReady ? (
                <div className="mb-4">
                  <Banner tone="accent">
                    Necesitas configurar una clave de IA para generar material.{" "}
                    <button
                      type="button"
                      onClick={onOpenSettings}
                      className="underline underline-offset-2"
                    >
                      Ir a Ajustes
                    </button>
                  </Banner>
                </div>
              ) : null}

              <div className="flex flex-wrap items-end gap-3">
                <div className="min-w-[220px] flex-1">
                  <Field
                    label="Tema o foco (opcional)"
                    hint="Si lo dejas vacío se usa una muestra representativa de toda la materia."
                  >
                    <input
                      value={topic}
                      onChange={(event) => setTopic(event.target.value)}
                      placeholder="Ej.: mitosis, fotosíntesis, tema 3…"
                      className={inputClass}
                      maxLength={300}
                    />
                  </Field>
                </div>
                <div className="flex flex-wrap gap-2">
                  {tab === "reading" ? (
                    <>
                      <Button
                        variant="primary"
                        onClick={() => void generate("summary")}
                        disabled={busy || !providerReady}
                      >
                        {busy ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Sparkles className="h-4 w-4" />
                        )}
                        Resumen
                      </Button>
                      <Button
                        variant="secondary"
                        onClick={() => void generate("outline")}
                        disabled={busy || !providerReady}
                      >
                        <ListTree className="h-4 w-4" />
                        Esquema
                      </Button>
                    </>
                  ) : tab === "cards" ? (
                    <Button
                      variant="primary"
                      onClick={() => void generate("deck")}
                      disabled={busy || !providerReady}
                    >
                      {busy ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Brain className="h-4 w-4" />
                      )}
                      Generar tarjetas
                    </Button>
                  ) : (
                    <Button
                      variant="primary"
                      onClick={() => void generate("quiz")}
                      disabled={busy || !providerReady}
                    >
                      {busy ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <ClipboardList className="h-4 w-4" />
                      )}
                      Generar test
                    </Button>
                  )}
                </div>
              </div>
            </div>

            <div className="mt-6">
              <h2 className="mb-3 font-serif text-lg">
                {tab === "reading"
                  ? "Resúmenes y esquemas"
                  : tab === "cards"
                    ? "Mazos de tarjetas"
                    : "Tests"}
              </h2>

              {loading ? (
                <div className="flex items-center gap-2 text-sm text-muted">
                  <Spinner /> Cargando…
                </div>
              ) : visibleSets.length === 0 ? (
                <div className="rounded-xl border border-rule bg-raised/60">
                  <EmptyState
                    icon={<BookOpenCheck className="h-8 w-8" />}
                    title="Aún no hay material"
                    description="Genera el primero con el botón de arriba. Se guarda en tu equipo y se puede borrar cuando quieras."
                  />
                </div>
              ) : (
                <ul className="divide-y divide-rule overflow-hidden rounded-xl border border-rule bg-raised/70">
                  {visibleSets.map((item) => {
                    const Icon = KIND_META[item.kind].icon;
                    return (
                      <li key={item.id} className="flex items-center gap-3 px-4 py-3">
                        <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-rule bg-paper text-accent">
                          <Icon className="h-4 w-4" />
                        </span>
                        <button
                          type="button"
                          onClick={() => void openSet(item.id)}
                          className="min-w-0 flex-1 text-left"
                        >
                          <span className="flex flex-wrap items-center gap-2">
                            <span className="truncate text-sm font-medium">
                              {item.title}
                            </span>
                            {item.status === "generating" ? (
                              <Chip tone="warning">
                                <Loader2 className="h-3 w-3 animate-spin" />
                                generando
                              </Chip>
                            ) : item.status === "error" ? (
                              <Chip tone="danger">error</Chip>
                            ) : item.kind === "deck" ? (
                              <Chip tone="accent">
                                {item.due_count ?? 0} pendientes / {item.card_count ?? 0}
                              </Chip>
                            ) : item.kind === "quiz" ? (
                              <Chip>
                                {item.answered_count ?? 0} / {item.item_count ?? 0}
                                {item.score !== null
                                  ? ` · ${Math.round(item.score * 100)}%`
                                  : ""}
                              </Chip>
                            ) : null}
                          </span>
                          <span className="mt-0.5 block text-[11px] text-muted">
                            {formatDate(item.created_at)}
                            {item.provider ? ` · ${item.provider}` : ""}
                          </span>
                        </button>
                        <button
                          type="button"
                          onClick={() => void removeSet(item.id)}
                          className="rounded-md p-1.5 text-muted hover:bg-danger/10 hover:text-danger"
                          aria-label="Borrar"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
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
