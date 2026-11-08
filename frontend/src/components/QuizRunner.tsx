import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, Check, RotateCcw, X } from "lucide-react";
import type { Citation, QuizItem } from "../types";
import { Button, Chip, ProgressBar, cx } from "./ui";

const LETTERS = ["A", "B", "C", "D"];

interface QuizRunnerProps {
  items: QuizItem[];
  citations: Citation[];
  onAnswer: (itemId: string, chosen: number) => Promise<QuizItem>;
  onReset: () => Promise<void>;
  onCitation: (citation: Citation) => void;
  onBack: () => void;
}

export function QuizRunner({
  items,
  citations,
  onAnswer,
  onReset,
  onCitation,
  onBack,
}: QuizRunnerProps) {
  const [local, setLocal] = useState<QuizItem[]>(items);
  const [current, setCurrent] = useState(0);
  const [busy, setBusy] = useState(false);
  const [showSummary, setShowSummary] = useState(false);

  useEffect(() => {
    setLocal(items);
    const next = items.findIndex((item) => item.chosen_index === null);
    setCurrent(next >= 0 ? next : 0);
    setShowSummary(items.length > 0 && next === -1);
  }, [items]);

  const answered = local.filter((item) => item.chosen_index !== null).length;
  const correct = local.filter((item) => item.is_correct === 1).length;
  const allAnswered = local.length > 0 && answered === local.length;
  const item = local[current];

  async function answer(option: number) {
    if (!item || busy || item.chosen_index !== null) return;
    setBusy(true);
    try {
      const updated = await onAnswer(item.id, option);
      setLocal((previous) =>
        previous.map((entry) => (entry.id === updated.id ? updated : entry)),
      );
    } finally {
      setBusy(false);
    }
  }

  function next() {
    const nextIndex = local.findIndex(
      (entry, position) => position > current && entry.chosen_index === null,
    );
    if (nextIndex >= 0) {
      setCurrent(nextIndex);
      return;
    }
    const first = local.findIndex((entry) => entry.chosen_index === null);
    if (first >= 0) setCurrent(first);
    else setShowSummary(true);
  }

  async function reset() {
    await onReset();
    setLocal((previous) =>
      previous.map((entry) => ({ ...entry, chosen_index: null, is_correct: null })),
    );
    setCurrent(0);
    setShowSummary(false);
  }

  if (local.length === 0) {
    return (
      <div className="rounded-xl border border-rule bg-raised/70 p-6 text-sm text-muted">
        Este test no tiene preguntas.
        <div className="mt-3">
          <Button variant="secondary" onClick={onBack}>
            Volver
          </Button>
        </div>
      </div>
    );
  }

  if (showSummary) {
    const score = answered ? Math.round((correct / answered) * 100) : 0;
    const wrong = local.filter((entry) => entry.is_correct === 0);
    return (
      <div>
        <div className="rounded-xl border border-rule bg-raised/80 p-6 text-center">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-accent">
            Resultado
          </p>
          <p className="mt-2 font-serif text-5xl">{score}%</p>
          <p className="mt-1 text-sm text-muted">
            {correct} de {answered} correctas
          </p>
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            <Button variant="primary" onClick={() => void reset()}>
              <RotateCcw className="h-4 w-4" />
              Repetir test
            </Button>
            <Button variant="secondary" onClick={onBack}>
              Volver a la lista
            </Button>
          </div>
        </div>

        {wrong.length > 0 ? (
          <div className="mt-5">
            <h3 className="mb-2 font-serif text-lg">Para repasar</h3>
            <ul className="space-y-2">
              {wrong.map((entry) => {
                const citation = entry.source_index
                  ? citations.find((c) => c.index === entry.source_index)
                  : null;
                return (
                  <li
                    key={entry.id}
                    className="rounded-lg border border-rule bg-raised/70 p-4"
                  >
                    <p className="text-sm font-medium">{entry.question}</p>
                    <p className="mt-1 text-[12px] text-danger">
                      Tu respuesta: {LETTERS[entry.chosen_index ?? 0]}){" "}
                      {entry.options[entry.chosen_index ?? 0]}
                    </p>
                    <p className="text-[12px] text-success">
                      Correcta: {LETTERS[entry.correct_index]}){" "}
                      {entry.options[entry.correct_index]}
                    </p>
                    {entry.explanation ? (
                      <p className="mt-1.5 text-[12px] leading-5 text-muted">
                        {entry.explanation}
                      </p>
                    ) : null}
                    {citation ? (
                      <button
                        type="button"
                        onClick={() => onCitation(citation)}
                        className="mt-2 inline-flex items-center gap-1.5 rounded border border-rule bg-paper px-2 py-0.5 text-[11px] text-muted hover:border-accent/50"
                      >
                        <span className="inline-flex h-4 min-w-4 items-center justify-center rounded bg-highlight px-1 font-semibold text-ink">
                          {citation.index}
                        </span>
                        {citation.document_title}
                        {citation.locator ? ` · ${citation.locator}` : ""}
                      </button>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </div>
        ) : (
          <p className="mt-5 text-center text-sm text-success">
            Todas correctas. Buen trabajo.
          </p>
        )}

        <div className="mt-5">
          <Button variant="ghost" onClick={onBack}>
            <ArrowLeft className="h-4 w-4" />
            Volver
          </Button>
        </div>
      </div>
    );
  }

  if (!item) return null;

  return (
    <div>
      <div className="mb-3 flex items-center justify-between gap-3">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft className="h-4 w-4" />
          Salir
        </Button>
        <span className="text-[11px] uppercase tracking-wide text-muted">
          Pregunta {current + 1} de {local.length} · {correct} correctas
        </span>
      </div>

      <ProgressBar value={answered / local.length} />

      <div className="mt-4 rounded-xl border border-rule bg-raised p-5 shadow-paper md:p-6">
        <p className="whitespace-pre-wrap font-serif text-[18px] leading-snug md:text-[20px]">
          {item.question}
        </p>

        <div className="mt-4 grid gap-2">
          {item.options.map((option, index) => {
            const chosen = item.chosen_index === index;
            const isCorrect = item.correct_index === index;
            const answeredItem = item.chosen_index !== null;
            return (
              <button
                key={index}
                type="button"
                onClick={() => void answer(index)}
                disabled={answeredItem || busy}
                className={cx(
                  "flex items-start gap-3 rounded-lg border px-3 py-2.5 text-left text-sm transition",
                  !answeredItem && "border-rule hover:border-accent/50 hover:bg-accent-soft/40",
                  answeredItem && isCorrect && "border-success/60 bg-success/10",
                  answeredItem && chosen && !isCorrect && "border-danger/50 bg-danger/10",
                  answeredItem && !isCorrect && !chosen && "border-rule opacity-60",
                )}
              >
                <span
                  className={cx(
                    "mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded border text-[11px] font-semibold",
                    answeredItem && isCorrect
                      ? "border-success bg-success text-white"
                      : answeredItem && chosen
                        ? "border-danger bg-danger text-white"
                        : "border-rule text-muted",
                  )}
                >
                  {answeredItem && isCorrect ? (
                    <Check className="h-3 w-3" />
                  ) : answeredItem && chosen ? (
                    <X className="h-3 w-3" />
                  ) : (
                    LETTERS[index]
                  )}
                </span>
                <span className="leading-6">{option}</span>
              </button>
            );
          })}
        </div>

        {item.chosen_index !== null ? (
          <div
            className={cx(
              "mt-4 rounded-lg border px-3 py-2.5 text-[13px] leading-6",
              item.is_correct
                ? "border-success/40 bg-success/10 text-success"
                : "border-danger/40 bg-danger/10 text-danger",
            )}
          >
            <p className="font-medium">
              {item.is_correct ? "Correcto" : "No es correcto"}
              {!item.is_correct
                ? ` · la respuesta era ${LETTERS[item.correct_index]}`
                : ""}
            </p>
            {item.explanation ? <p className="mt-1 text-ink/85">{item.explanation}</p> : null}
            {item.source_index ? (
              <button
                type="button"
                onClick={() => {
                  const citation = citations.find((c) => c.index === item.source_index);
                  if (citation) onCitation(citation);
                }}
                className="mt-2 inline-flex items-center gap-1.5 rounded border border-rule bg-raised px-2 py-0.5 text-[11px] text-muted hover:border-accent/50"
              >
                <span className="inline-flex h-4 min-w-4 items-center justify-center rounded bg-highlight px-1 font-semibold text-ink">
                  {item.source_index}
                </span>
                Ver fuente
              </button>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="mt-4 flex items-center justify-between">
        <Chip>
          {answered} / {local.length} respondidas
        </Chip>
        {allAnswered ? (
          <Button variant="primary" onClick={() => setShowSummary(true)}>
            Ver resultado
            <ArrowRight className="h-4 w-4" />
          </Button>
        ) : (
          <Button
            variant="secondary"
            onClick={next}
            disabled={item.chosen_index === null}
          >
            Siguiente
            <ArrowRight className="h-4 w-4" />
          </Button>
        )}
      </div>
    </div>
  );
}
