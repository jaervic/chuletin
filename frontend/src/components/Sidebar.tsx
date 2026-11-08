import { useState } from "react";
import {
  BookOpen,
  GraduationCap,
  Library,
  MessageSquarePlus,
  Moon,
  Plus,
  Settings,
  Sun,
  Trash2,
  X,
} from "lucide-react";
import type { ConversationSummary, Subject } from "../types";
import { cx } from "./ui";
import { timeAgo } from "../lib/format";

export type View = "chat" | "library" | "study" | "settings";

export function Logo({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M7 4.5h13.2L25 9.3V27.5H7z" />
      <path d="M20.2 4.5v4.8H25" />
      <path d="M11 14.5h10M11 18.2h10M11 21.9h6.5" />
    </svg>
  );
}

interface SidebarProps {
  subjects: Subject[];
  activeSubject: string | null;
  onSelectSubject: (id: string | null) => void;
  conversations: ConversationSummary[];
  activeConversation: string | null;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  onCreateSubject: (name: string) => Promise<void>;
  onDeleteSubject: (id: string) => void;
  view: View;
  onNavigate: (view: View) => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  onClose?: () => void;
}

export function Sidebar({
  subjects,
  activeSubject,
  onSelectSubject,
  conversations,
  activeConversation,
  onSelectConversation,
  onNewConversation,
  onCreateSubject,
  onDeleteSubject,
  view,
  onNavigate,
  theme,
  onToggleTheme,
  onClose,
}: SidebarProps) {
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  async function submitSubject(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    try {
      await onCreateSubject(trimmed);
      setName("");
      setCreating(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="flex h-full w-[280px] shrink-0 flex-col border-r border-rule bg-raised/70">
      <div className="flex items-center justify-between px-5 pb-4 pt-5">
        <button
          type="button"
          className="flex items-center gap-2 text-left"
          onClick={() => onNavigate("chat")}
        >
          <Logo className="h-7 w-7 text-accent" />
          <span>
            <span className="block font-serif text-[19px] font-semibold leading-none text-ink">
              Chuletín
            </span>
            <span className="block text-[10px] uppercase tracking-[0.18em] text-muted">
              con fuentes
            </span>
          </span>
        </button>
        {onClose ? (
          <button
            type="button"
            className="rounded-md p-1 text-muted hover:bg-accent-soft/50 md:hidden"
            onClick={onClose}
            aria-label="Cerrar menu"
          >
            <X className="h-5 w-5" />
          </button>
        ) : null}
      </div>

      <div className="px-3">
        <button
          type="button"
          onClick={onNewConversation}
          className="flex w-full items-center gap-2 rounded-lg border border-accent/25 bg-accent-soft/60 px-3 py-2 text-sm font-medium text-ink transition hover:border-accent/50 hover:bg-accent-soft"
        >
          <MessageSquarePlus className="h-4 w-4 text-accent" />
          Nueva conversación
        </button>
      </div>

      <nav className="scroll-thin mt-5 flex-1 overflow-y-auto px-3 pb-4">
        <div className="mb-2 flex items-center justify-between px-2">
          <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">
            Materias
          </span>
          <button
            type="button"
            onClick={() => setCreating((value) => !value)}
            className="rounded p-1 text-muted hover:bg-accent-soft/60 hover:text-ink"
            aria-label="Crear materia"
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
        </div>

        {creating ? (
          <form onSubmit={submitSubject} className="mb-2 px-1">
            <input
              autoFocus
              value={name}
              onChange={(event) => setName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  setCreating(false);
                  setName("");
                }
              }}
              placeholder="Nombre de la materia"
              className="w-full rounded-md border border-rule bg-paper px-2 py-1.5 text-[13px] outline-none focus:border-accent"
            />
          </form>
        ) : null}

        <ul className="space-y-0.5">
          <li>
            <button
              type="button"
              onClick={() => {
                onSelectSubject(null);
                onNavigate("chat");
              }}
              className={cx(
                "group flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px]",
                activeSubject === null && view === "chat"
                  ? "bg-accent-soft/70 text-ink"
                  : "text-muted hover:bg-accent-soft/40 hover:text-ink",
              )}
            >
              <span className="h-2 w-2 rounded-full bg-accent/70" />
              <span className="flex-1 truncate">Todas</span>
            </button>
          </li>
          {subjects.map((subject) => (
            <li key={subject.id} className="group relative">
              <button
                type="button"
                onClick={() => {
                  onSelectSubject(subject.id);
                  onNavigate("chat");
                }}
                className={cx(
                  "flex w-full items-center gap-2 rounded-md px-2 py-1.5 pr-7 text-left text-[13px]",
                  activeSubject === subject.id && view === "chat"
                    ? "bg-accent-soft/70 text-ink"
                    : "text-muted hover:bg-accent-soft/40 hover:text-ink",
                )}
              >
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ backgroundColor: subject.color }}
                />
                <span className="flex-1 truncate">{subject.name}</span>
                <span className="text-[10px] tabular-nums text-muted/70">
                  {subject.document_count}
                </span>
              </button>
              <button
                type="button"
                onClick={() => onDeleteSubject(subject.id)}
                className="absolute right-1 top-1/2 hidden -translate-y-1/2 rounded p-1 text-muted hover:text-danger group-hover:block"
                aria-label={`Borrar ${subject.name}`}
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </li>
          ))}
        </ul>

        <div className="mb-2 mt-6 flex items-center justify-between px-2">
          <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">
            Conversaciones
          </span>
        </div>

        {conversations.length === 0 ? (
          <p className="px-2 py-1 text-[12px] leading-5 text-muted/80">
            Aún no hay conversaciones.
          </p>
        ) : (
          <ul className="space-y-0.5">
            {conversations.slice(0, 12).map((conversation) => (
              <li key={conversation.id}>
                <button
                  type="button"
                  onClick={() => onSelectConversation(conversation.id)}
                  className={cx(
                    "w-full rounded-md px-2 py-1.5 text-left",
                    activeConversation === conversation.id
                      ? "bg-accent-soft/70 text-ink"
                      : "text-muted hover:bg-accent-soft/40 hover:text-ink",
                  )}
                >
                  <span className="block truncate text-[13px]">{conversation.title}</span>
                  <span className="block text-[10px] text-muted/70">
                    {timeAgo(conversation.updated_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </nav>

      <div className="border-t border-rule px-3 py-3">
        <button
          type="button"
          onClick={() => onNavigate("library")}
          className={cx(
            "flex w-full items-center gap-2 rounded-md px-2 py-2 text-[13px]",
            view === "library"
              ? "bg-accent-soft/70 text-ink"
              : "text-muted hover:bg-accent-soft/40 hover:text-ink",
          )}
        >
          <Library className="h-4 w-4" />
          Biblioteca
        </button>
        <button
          type="button"
          onClick={() => onNavigate("study")}
          className={cx(
            "flex w-full items-center gap-2 rounded-md px-2 py-2 text-[13px]",
            view === "study"
              ? "bg-accent-soft/70 text-ink"
              : "text-muted hover:bg-accent-soft/40 hover:text-ink",
          )}
        >
          <GraduationCap className="h-4 w-4" />
          Estudiar
        </button>
        <button
          type="button"
          onClick={() => onNavigate("settings")}
          className={cx(
            "flex w-full items-center gap-2 rounded-md px-2 py-2 text-[13px]",
            view === "settings"
              ? "bg-accent-soft/70 text-ink"
              : "text-muted hover:bg-accent-soft/40 hover:text-ink",
          )}
        >
          <Settings className="h-4 w-4" />
          Ajustes
        </button>
        <div className="mt-1 flex items-center justify-between rounded-md px-2 py-1">
          <span className="flex items-center gap-2 text-[12px] text-muted">
            <BookOpen className="h-3.5 w-3.5" />
            v0.2.0
          </span>
          <button
            type="button"
            onClick={onToggleTheme}
            className="rounded p-1.5 text-muted hover:bg-accent-soft/60 hover:text-ink"
            aria-label={theme === "dark" ? "Cambiar a tema claro" : "Cambiar a tema oscuro"}
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </aside>
  );
}
