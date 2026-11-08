import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, Check, RotateCcw, Sparkles } from "lucide-react";
import type { Citation, StudyCard } from "../types";
import { Button, Chip, ProgressBar, cx } from "./ui";
import { locatorFor } from "../lib/format";

const RATING_BUTTONS: Array<{
  rating: 1 | 2 | 3 | 4;
  label: string;
  hint: string;
  className: string;
  key: string;
}> = [
  {
    rating: 1,
    label: "Otra vez",
    hint: "en 10 min",
    key: "1",
    className: "border-danger/40 text-danger hover:bg-danger/10",
  },
  {
    rating: 2,
    label: "Difícil",
    hint: "intervalo corto",
    key: "2",
    className: "border-accent/40 text-ink hover:bg-accent-soft/60",
  },
  {
    rating: 3,
    label: "Bien",
    hint: "intervalo normal",
    key: "3",
    className: "border-success/40 text-success hover:bg-success/10",
  },
  {
    rating: 4,
    label: "Fácil",
    hint: "intervalo largo",
    key: "4",
    className: "border-success/60 text-success hover:bg-success/15",
  },
];

interface DeckReviewProps {
  cards: StudyCard[];
  citations: Citation[];
  onReview: (cardId: string, rating: 1 | 2 | 3 | 4) => Promise<StudyCard>;
  onCitation: (citation: Citation) => void;
  onBack: () => void;
}

export function DeckReview({
  cards,
  citations,
  onReview,
  onCitation,
  onBack,
}: DeckReviewProps) {
  const [started, setStarted] = useState(false);
  const [queue, setQueue] = useState<StudyCard[]>([]);
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [finished, setFinished] = useState(false);
  const [busy, setBusy] = useState(false);
  const [counts, setCounts] = useState<Record<number, number>>({ 1: 0, 2: 0, 3: 0, 4: 0 });

  const now = new Date().toISOString();
  const due = cards.filter((card) => card.due_at <= now);
  const current = queue[index];

  function start(mode: "due" | "all") {
    const list = mode === "due" && due.length > 0 ? due : cards;
    setQueue(list);
    setIndex(0);
    setRevealed(false);
    setFinished(false);
    setBusy(false);
    setCounts({ 1: 0, 2: 0, 3: 0, 4: 0 });
    setStarted(true);
  }

  async function rate(rating: 1 | 2 | 3 | 4) {
    if (!current || busy) return;
    setBusy(true);
    try {
      const updated = await onReview(current.id, rating);
      const newLength = queue.length + (rating === 1 ? 1 : 0);
      setQueue((previous) =>
        rating === 1
          ? [...previous, updated]
          : previous.map((card, position) => (position === index ? updated : card)),
      );
      setCounts((previous) => ({ ...previous, [rating]: (previous[rating] ?? 0) + 1 }));
      setRevealed(false);
      const next = index + 1;
      if (next >= newLength) {
        setFinished(true);
      }
      setIndex(next);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!started || finished) return;
    function onKey(event: KeyboardEvent) {
      if (event.code === "Space") {
        event.preventDefault();
        setRevealed(true);
        return;
      }
      if (revealed && ["1", "2", "3", "4"].includes(event.key)) {
        void rate(Number(event.key) as 1 | 2 | 3 | 4);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (cards.length === 0) {
    return (
      <div className="rounded-xl border border-rule bg-raised/70 p-6 text-sm text-muted">
        Este mazo no tiene tarjetas.
        <div className="mt-3">
          <Button variant="secondary" onClick={onBack}>
            Volver
          </Button>
        </div>
      </div>
    );
  }

  if (!started) {
    const total = cards.length;
    return (
      <div className="rounded-xl border border-rule bg-raised/70 p-6">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-accent" />
          <h2 className="font-serif text-xl">Sesión de repaso</h2>
        </div>
        <p className="mt-2 text-sm leading-6 text-muted">
          {due.length > 0
            ? `Tienes ${due.length} tarjeta${due.length === 1 ? "" : "s"} pendiente${
                due.length === 1 ? "" : "s"
              } de ${total}. El repaso espaciado te las volverá a mostrar cuando estés a punto de olvidarlas.`
            : `No hay tarjetas pendientes. Puedes repasar las ${total} igualmente.`}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            variant="primary"
            onClick={() => start(due.length > 0 ? "due" : "all")}
          >
            {due.length > 0 ? `Repasar ${due.length} pendientes` : "Repasar todas"}
          </Button>
          {due.length > 0 && due.length < total ? (
            <Button variant="secondary" onClick={() => start("all")}>
              Repasar las {total}
            </Button>
          ) : null}
          <Button variant="ghost" onClick={onBack}>
            <ArrowLeft className="h-4 w-4" />
            Volver
          </Button>
        </div>
      </div>
    );
  }

  if (finished || !current) {
    const totalReviewed = Object.values(counts).reduce((sum, value) => sum + value, 0);
    return (
      <div className="rounded-xl border border-rule bg-raised/70 p-6 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-success/10 text-success">
          <Check className="h-7 w-7" />
        </div>
        <h2 className="mt-3 font-serif text-2xl">Sesión completada</h2>
        <p className="mt-1 text-sm text-muted">
          {totalReviewed} respuesta{totalReviewed === 1 ? "" : "s"} registrada
          {totalReviewed === 1 ? "" : "s"}.
        </p>
        <div className="mx-auto mt-5 flex max-w-md flex-wrap justify-center gap-2 text-[12px]">
          <Chip tone="danger">Otra vez: {counts[1] ?? 0}</Chip>
          <Chip>Difícil: {counts[2] ?? 0}</Chip>
          <Chip tone="success">Bien: {counts[3] ?? 0}</Chip>
          <Chip tone="success">Fácil: {counts[4] ?? 0}</Chip>
        </div>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <Button variant="primary" onClick={() => start("due")}>
            <RotateCcw className="h-4 w-4" />
            Otro repaso
          </Button>
          <Button variant="secondary" onClick={onBack}>
            Volver a la lista
          </Button>
        </div>
      </div>
    );
  }

  const citation = current.source_index
    ? citations.find((item) => item.index === current.source_index)
    : null;

  return (
    <div>
      <div className="mb-3 flex items-center justify-between gap-3">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft className="h-4 w-4" />
          Salir
        </Button>
        <span className="text-[11px] uppercase tracking-wide text-muted">
          Tarjeta {Math.min(index + 1, queue.length)} de {queue.length}
          {index >= queue.length ? "" : ""}
        </span>
      </div>

      <ProgressBar value={queue.length ? index / queue.length : 0} />

      <div className="mt-4 rounded-xl border border-rule bg-raised p-6 shadow-paper md:p-8">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-accent">
          Pregunta
        </p>
        <h2 className="mt-2 whitespace-pre-wrap font-serif text-[22px] leading-snug text-ink md:text-[26px]">
          {current.front}
        </h2>

        {revealed ? (
          <div className="mt-6 border-t border-rule pt-5">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">
              Respuesta
            </p>
            <p className="mt-2 whitespace-pre-wrap text-[15px] leading-7 text-ink/90">
              {current.back}
            </p>
            {citation ? (
              <button
                type="button"
                onClick={() => onCitation(citation)}
                className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-rule bg-paper px-2 py-1 text-[11px] text-muted hover:border-accent/50 hover:text-ink"
              >
                <span className="inline-flex h-4 min-w-4 items-center justify-center rounded bg-highlight px-1 font-semibold text-ink">
                  {citation.index}
                </span>
                {citation.document_title}
                {citation.locator
                  ? ` · ${citation.locator}`
                  : citation.page_from
                    ? ` · ${locatorFor(citation.source_type, citation.page_from)}`
                    : ""}
              </button>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="mt-4">
        {!revealed ? (
          <Button variant="primary" onClick={() => setRevealed(true)} className="w-full">
            Mostrar respuesta
            <span className="ml-1 text-[11px] opacity-70">(espacio)</span>
          </Button>
        ) : (
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            {RATING_BUTTONS.map((button) => (
              <button
                key={button.rating}
                type="button"
                disabled={busy}
                onClick={() => void rate(button.rating)}
                className={cx(
                  "rounded-lg border bg-raised px-3 py-2 text-left transition disabled:opacity-50",
                  button.className,
                )}
              >
                <span className="flex items-center justify-between text-[13px] font-medium">
                  {button.label}
                  <span className="text-[10px] opacity-60">{button.key}</span>
                </span>
                <span className="mt-0.5 block text-[10px] text-muted">{button.hint}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <p className="mt-3 flex items-center gap-1 text-[11px] text-muted">
        <ArrowRight className="h-3 w-3" />
        Las tarjetas vuelven solas según tu memoria, no hace falta repasarlas todas
        cada día.
      </p>
    </div>
  );
}
