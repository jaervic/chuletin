import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowUp,
  BookOpen,
  Square,
  Sparkles,
} from "lucide-react";
import type { ChatTurn, Citation } from "../types";
import { Markdown } from "./Markdown";
import { Banner, Button, cx } from "./ui";

const SUGGESTIONS = [
  "Explícame el tema principal de mis apuntes",
  "Hazme un resumen de lo que he subido",
  "¿Qué dice sobre el concepto más importante?",
  "Compárame las dos ideas centrales",
];

function Dots() {
  return (
    <div className="flex items-center gap-1 py-1.5">
      {[0, 1, 2].map((index) => (
        <span
          key={index}
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent/70"
          style={{ animationDelay: `${index * 120}ms` }}
        />
      ))}
    </div>
  );
}

function SourcesRow({
  citations,
  onCitation,
}: {
  citations: Citation[];
  onCitation: (citation: Citation) => void;
}) {
  return (
    <div className="mt-4 flex flex-wrap gap-1.5">
      {citations.map((citation) => (
        <button
          key={citation.index}
          type="button"
          onClick={() => onCitation(citation)}
          className="inline-flex max-w-full items-center gap-1.5 rounded-lg border border-rule bg-raised/70 px-2 py-1 text-[11px] text-muted transition hover:border-accent/50 hover:text-ink"
        >
          <span className="inline-flex h-4 min-w-4 items-center justify-center rounded bg-highlight px-1 font-semibold text-ink">
            {citation.index}
          </span>
          <span className="max-w-[220px] truncate">{citation.document_title}</span>
          {citation.locator ? <span>· {citation.locator}</span> : null}
        </button>
      ))}
    </div>
  );
}

function Message({
  turn,
  onCitation,
}: {
  turn: ChatTurn;
  onCitation: (citation: Citation) => void;
}) {
  if (turn.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md border border-rule bg-raised px-4 py-2.5 text-[15px] leading-7 shadow-paper">
          {turn.content}
        </div>
      </div>
    );
  }

  return (
    <article>
      <div className="mb-1.5 flex items-center gap-2 text-[11px] uppercase tracking-[0.14em] text-muted">
        <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-accent-soft text-[10px] font-bold text-accent">
          Ch
        </span>
        Chuletín
        {turn.pending ? (
          <span className="normal-case tracking-normal text-accent">escribiendo…</span>
        ) : null}
      </div>

      <div className="border-l-2 border-accent/25 pl-4">
        {turn.content ? (
          <Markdown
            content={turn.content}
            onCitation={(index) => {
              const citation = turn.citations?.find((item) => item.index === index);
              if (citation) onCitation(citation);
            }}
          />
        ) : turn.pending ? (
          <Dots />
        ) : null}

        {turn.failed ? (
          <div className="mt-3">
            <Banner tone="danger">
              No se pudo completar la respuesta. Revisa los ajustes del proveedor.
            </Banner>
          </div>
        ) : null}

        {turn.citations && turn.citations.length > 0 ? (
          <SourcesRow citations={turn.citations} onCitation={onCitation} />
        ) : null}

        {!turn.pending && turn.provider ? (
          <p className="mt-2 text-[10px] uppercase tracking-wide text-muted/70">
            {turn.provider}
            {turn.model ? ` · ${turn.model}` : ""}
            {turn.latency_ms ? ` · ${(turn.latency_ms / 1000).toFixed(1)} s` : ""}
          </p>
        ) : null}
      </div>
    </article>
  );
}

interface ChatViewProps {
  turns: ChatTurn[];
  streaming: boolean;
  onAsk: (question: string) => void;
  onStop: () => void;
  onCitation: (citation: Citation) => void;
  subjectName: string | null;
  hasDocuments: boolean;
  onOpenLibrary: () => void;
  onOpenSettings: () => void;
  error: string | null;
  onDismissError: () => void;
}

export function ChatView({
  turns,
  streaming,
  onAsk,
  onStop,
  onCitation,
  subjectName,
  hasDocuments,
  onOpenLibrary,
  onOpenSettings,
  error,
  onDismissError,
}: ChatViewProps) {
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const stickToBottom = useRef(true);

  useEffect(() => {
    const node = scrollRef.current;
    if (node && stickToBottom.current) {
      node.scrollTop = node.scrollHeight;
    }
  }, [turns]);

  useEffect(() => {
    const node = scrollRef.current;
    if (!node) return;
    const handleScroll = () => {
      stickToBottom.current =
        node.scrollHeight - node.scrollTop - node.clientHeight < 140;
    };
    node.addEventListener("scroll", handleScroll);
    return () => node.removeEventListener("scroll", handleScroll);
  }, []);

  function resizeTextarea(element: HTMLTextAreaElement) {
    element.style.height = "auto";
    element.style.height = `${Math.min(200, element.scrollHeight)}px`;
  }

  function send() {
    const value = draft.trim();
    if (!value || streaming) return;
    onAsk(value);
    setDraft("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    stickToBottom.current = true;
  }

  const hasTurns = turns.length > 0;

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollRef} className="scroll-thin flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-5 pb-6 pt-6 md:px-8">
          {!hasTurns ? (
            <div className="py-10 md:py-16">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-accent">
                Cuaderno abierto
              </p>
              <h1 className="mt-3 max-w-xl font-serif text-[34px] leading-[1.15] text-ink md:text-[42px]">
                Pregunta lo que estés estudiando.
              </h1>
              <p className="mt-4 max-w-xl text-[15px] leading-7 text-muted">
                Respondo solo con tus apuntes y te digo de qué documento y página sale
                cada afirmación. Si no está en tus materiales, te lo digo.
              </p>

              {!hasDocuments ? (
                <div className="mt-8 flex flex-col gap-3 rounded-xl border border-rule bg-raised/80 p-5 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-start gap-3">
                    <BookOpen className="mt-0.5 h-5 w-5 text-accent" />
                    <div>
                      <p className="text-sm font-medium text-ink">
                        Tu biblioteca está vacía
                      </p>
                      <p className="text-[13px] leading-6 text-muted">
                        Sube un PDF, unos apuntes o un enlace para empezar.
                      </p>
                    </div>
                  </div>
                  <Button variant="primary" onClick={onOpenLibrary}>
                    Ir a la biblioteca
                  </Button>
                </div>
              ) : (
                <div className="mt-8 flex flex-wrap gap-2">
                  {SUGGESTIONS.map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      onClick={() => {
                        setDraft(suggestion);
                        textareaRef.current?.focus();
                      }}
                      className="inline-flex items-center gap-1.5 rounded-full border border-rule bg-raised/70 px-3 py-1.5 text-[12px] text-muted transition hover:border-accent/50 hover:text-ink"
                    >
                      <Sparkles className="h-3 w-3 text-accent/80" />
                      {suggestion}
                    </button>
                  ))}
                </div>
              )}

              <p className="mt-10 text-[11px] uppercase tracking-[0.16em] text-muted/70">
                {subjectName ? `Ámbito: ${subjectName}` : "Ámbito: todas las materias"}
                {" · "}
                {hasDocuments ? "listo para preguntar" : "sin documentos"}
              </p>
            </div>
          ) : (
            <div className="space-y-8">
              {turns.map((turn, index) => (
                <Message
                  key={turn.id ?? `${turn.role}-${index}`}
                  turn={turn}
                  onCitation={onCitation}
                />
              ))}
            </div>
          )}

          {error ? (
            <div className="mt-6 flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
              <div className="flex-1">
                <Banner tone="danger">{error}</Banner>
                <button
                  type="button"
                  onClick={onOpenSettings}
                  className="mt-1 text-[11px] text-accent underline underline-offset-2"
                >
                  Abrir ajustes del proveedor
                </button>
              </div>
              <button
                type="button"
                onClick={onDismissError}
                className="text-[11px] text-muted underline underline-offset-2"
              >
                cerrar
              </button>
            </div>
          ) : null}
        </div>
      </div>

      <div className="border-t border-rule bg-paper/80 px-4 pb-4 pt-3 backdrop-blur md:px-8">
        <div className="mx-auto w-full max-w-3xl">
          <div
            className={cx(
              "rounded-xl border bg-raised shadow-paper transition",
              streaming ? "border-accent/40" : "border-rule focus-within:border-accent/60",
            )}
          >
            <textarea
              ref={textareaRef}
              value={draft}
              rows={1}
              onChange={(event) => {
                setDraft(event.target.value);
                resizeTextarea(event.target);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  send();
                }
              }}
              placeholder={
                hasDocuments
                  ? "Escribe tu pregunta sobre los apuntes…"
                  : "Primero sube algún documento en la biblioteca…"
              }
              className="max-h-[200px] w-full resize-none bg-transparent px-4 pb-1 pt-3 text-[15px] leading-7 text-ink outline-none placeholder:text-muted/70"
            />
            <div className="flex items-center justify-between gap-2 px-3 pb-2.5 pt-1">
              <span className="truncate text-[11px] text-muted">
                {subjectName ? subjectName : "Todas las materias"}
                <span className="hidden sm:inline"> · Enter envía, Shift+Enter salto de línea</span>
              </span>
              <div className="flex items-center gap-1.5">
                {streaming ? (
                  <Button variant="secondary" size="sm" onClick={onStop}>
                    <Square className="h-3 w-3" />
                    Detener
                  </Button>
                ) : null}
                <button
                  type="button"
                  onClick={send}
                  disabled={!draft.trim() || streaming}
                  className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-accent text-accent-ink transition hover:brightness-105 disabled:opacity-40"
                  aria-label="Enviar pregunta"
                >
                  <ArrowUp className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
          <p className="mt-2 text-center text-[10px] text-muted/70">
            Chuletín cita tus documentos. Verifica siempre las fuentes antes de entregar
            un trabajo.
          </p>
        </div>
      </div>
    </div>
  );
}
