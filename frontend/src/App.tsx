import { useCallback, useEffect, useRef, useState } from "react";
import { Menu } from "lucide-react";
import type {
  ChatTurn,
  Citation,
  CitationRecord,
  ConversationSummary,
  DocumentItem,
  ProviderTest,
  SettingsResponse,
  Subject,
} from "./types";
import { api, streamChat } from "./lib/api";
import { useTheme } from "./hooks/useTheme";
import { Sidebar, type View } from "./components/Sidebar";
import { ChatView } from "./components/ChatView";
import { LibraryView, type UploadEntry } from "./components/LibraryView";
import { SettingsView } from "./components/SettingsView";
import { StudyView } from "./components/StudyView";
import { SourcePanel } from "./components/SourcePanel";
import { Banner, Chip, Spinner } from "./components/ui";
import { locatorFor } from "./lib/format";

export default function App() {
  const { theme, toggle } = useTheme();

  const [view, setView] = useState<View>("chat");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [activeSubject, setActiveSubject] = useState<string | null>(null);

  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [meta, setMeta] = useState<{ provider: string | null; model: string | null } | null>(
    null,
  );

  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [uploads, setUploads] = useState<UploadEntry[]>([]);
  const [source, setSource] = useState<Citation | null>(null);
  const [bootError, setBootError] = useState<string | null>(null);
  const [booting, setBooting] = useState(true);

  const streamingRef = useRef(false);
  const abortRef = useRef<AbortController | null>(null);

  const loadSubjects = useCallback(async () => {
    setSubjects(await api.subjects.list());
  }, []);

  const loadDocuments = useCallback(async () => {
    const next = await api.documents.list();
    setDocuments((previous) =>
      JSON.stringify(previous) === JSON.stringify(next) ? previous : next,
    );
  }, []);

  const loadConversations = useCallback(async () => {
    setConversations(await api.conversations.list());
  }, []);

  const loadSettings = useCallback(async () => {
    setSettings(await api.settings.get());
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await Promise.all([
          loadSubjects(),
          loadDocuments(),
          loadConversations(),
          loadSettings(),
        ]);
      } catch (caught) {
        if (!cancelled) {
          setBootError(
            caught instanceof Error
              ? caught.message
              : "No se pudo conectar con el servidor de Chuletín",
          );
        }
      } finally {
        if (!cancelled) setBooting(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadSubjects, loadDocuments, loadConversations, loadSettings]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      void loadDocuments().catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(interval);
  }, [loadDocuments]);

  const subject = subjects.find((item) => item.id === activeSubject) ?? null;
  const visibleDocuments = activeSubject
    ? documents.filter((document) => document.subject_id === activeSubject)
    : documents;

  function navigate(next: View) {
    if ((next === "library" || next === "study") && !activeSubject && subjects.length > 0) {
      setActiveSubject(subjects[0].id);
    }
    setView(next);
    setSidebarOpen(false);
  }

  function newConversation() {
    setConversationId(null);
    setTurns([]);
    setMeta(null);
    setChatError(null);
    setView("chat");
    setSidebarOpen(false);
  }

  async function createSubject(name: string): Promise<void> {
    const created = await api.subjects.create(name);
    await loadSubjects();
    setActiveSubject(created.id);
  }

  async function deleteSubject(id: string) {
    const target = subjects.find((item) => item.id === id);
    if (!window.confirm(`¿Borrar «${target?.name}» y todos sus documentos?`)) return;
    await api.subjects.remove(id);
    if (activeSubject === id) setActiveSubject(null);
    await Promise.all([loadSubjects(), loadDocuments(), loadConversations()]);
  }

  function citationFromRecord(record: CitationRecord, index: number): Citation {
    const document = documents.find((item) => item.id === record.document_id);
    const sourceType = document?.source_type ?? "text";
    return {
      index,
      document_id: record.document_id ?? "",
      document_title: document?.title ?? "Documento",
      source_type: sourceType,
      page_from: record.page_from,
      page_to: record.page_to,
      heading: record.heading,
      snippet: record.snippet,
      score: record.score ?? 0,
      locator: locatorFor(sourceType, record.page_from),
    };
  }

  async function openConversation(id: string) {
    try {
      const data = await api.conversations.get(id);
      setConversationId(id);
      setChatError(null);
      setMeta(null);
      setTurns(
        data.messages.map((message) => ({
          id: message.id,
          role: message.role,
          content: message.content,
          citations: message.citations.map((record, index) =>
            citationFromRecord(record, index + 1),
          ),
          provider: message.provider,
          model: message.model,
          latency_ms: message.latency_ms,
        })),
      );
      setView("chat");
      setSidebarOpen(false);
    } catch (caught) {
      setChatError(caught instanceof Error ? caught.message : "No se pudo abrir");
    }
  }

  async function ask(question: string) {
    if (streamingRef.current) return;
    streamingRef.current = true;
    setStreaming(true);
    setChatError(null);
    setTurns((previous) => [
      ...previous,
      { role: "user", content: question },
      { role: "assistant", content: "", pending: true },
    ]);

    const controller = new AbortController();
    abortRef.current = controller;

    let citations: Citation[] = [];
    let text = "";
    let provider = "";
    let model = "";

    const patchLast = (
      content: string,
      pending: boolean,
      failed = false,
      extra?: Partial<ChatTurn>,
    ) => {
      setTurns((previous) => {
        const next = [...previous];
        for (let index = next.length - 1; index >= 0; index -= 1) {
          if (next[index].role === "assistant") {
            next[index] = {
              ...next[index],
              content,
              citations,
              pending,
              failed,
              ...extra,
            };
            break;
          }
        }
        return next;
      });
    };

    try {
      await streamChat(
        {
          question,
          subject_id: activeSubject,
          conversation_id: conversationId,
        },
        (event) => {
          if (event.type === "meta") {
            citations = event.data.citations;
            provider = event.data.provider ?? "";
            model = event.data.model ?? "";
            setConversationId(event.data.conversation_id);
            setMeta({ provider: event.data.provider, model: event.data.model });
            if (event.data.provider) {
              setSettings((previous) =>
                previous ? { ...previous, current: event.data.provider as string } : previous,
              );
            }
          } else if (event.type === "delta") {
            text += event.data.text;
            patchLast(text, true);
          } else if (event.type === "done") {
            text = event.data.text;
            patchLast(text, false, false, {
              provider,
              model,
              latency_ms: event.data.latency_ms ?? null,
            });
          } else if (event.type === "error") {
            setChatError(event.data.message);
            patchLast(text, false, true);
          }
        },
        controller.signal,
      );
    } catch (caught) {
      const aborted = caught instanceof Error && caught.name === "AbortError";
      if (aborted) {
        patchLast(text || "Respuesta detenida.", false);
      } else {
        setChatError(caught instanceof Error ? caught.message : "Error de conexión");
        patchLast(text, false, true);
      }
    } finally {
      streamingRef.current = false;
      setStreaming(false);
      abortRef.current = null;
      void loadConversations().catch(() => undefined);
      void loadSettings().catch(() => undefined);
    }
  }

  function stop() {
    abortRef.current?.abort();
  }

  async function uploadFiles(files: File[]) {
    if (!activeSubject) throw new Error("Selecciona una materia antes de subir archivos");
    for (const file of files) {
      const entryId = crypto.randomUUID();
      setUploads((previous) => [
        ...previous,
        { id: entryId, name: file.name, progress: 0 },
      ]);
      try {
        await api.documents.upload(activeSubject, file, (progress) => {
          setUploads((previous) =>
            previous.map((entry) =>
              entry.id === entryId ? { ...entry, progress } : entry,
            ),
          );
        });
        setUploads((previous) =>
          previous.map((entry) =>
            entry.id === entryId ? { ...entry, progress: 1 } : entry,
          ),
        );
        window.setTimeout(() => {
          setUploads((previous) => previous.filter((entry) => entry.id !== entryId));
        }, 1600);
      } catch (caught) {
        setUploads((previous) =>
          previous.map((entry) =>
            entry.id === entryId
              ? {
                  ...entry,
                  error: caught instanceof Error ? caught.message : "Error al subir",
                }
              : entry,
          ),
        );
      }
    }
    await Promise.all([loadDocuments(), loadSubjects()]);
  }

  async function addUrl(url: string, kind: "web" | "youtube") {
    if (!activeSubject) throw new Error("Selecciona una materia");
    await api.documents.fromUrl(activeSubject, url, kind);
    await Promise.all([loadDocuments(), loadSubjects()]);
  }

  async function addText(title: string, text: string) {
    if (!activeSubject) throw new Error("Selecciona una materia");
    await api.documents.fromText(activeSubject, title, text);
    await Promise.all([loadDocuments(), loadSubjects()]);
  }

  async function removeDocument(id: string) {
    await api.documents.remove(id);
    await Promise.all([loadDocuments(), loadSubjects()]);
  }

  async function reindexDocument(id: string) {
    await api.documents.reindex(id);
    await loadDocuments();
  }

  async function saveProvider(payload: {
    provider: string;
    model: string;
    api_key?: string | null;
    base_url?: string | null;
  }) {
    await api.settings.saveProvider(payload);
    await loadSettings();
  }

  async function testProvider(payload: {
    provider: string;
    model?: string;
    api_key?: string | null;
    base_url?: string | null;
  }): Promise<ProviderTest> {
    return api.settings.testProvider(payload);
  }

  async function setOcr(enabled: boolean) {
    await api.settings.setOcr(enabled);
    setSettings((previous) =>
      previous ? { ...previous, ocr_enabled: enabled } : previous,
    );
  }

  const activeProvider = settings?.providers.find(
    (provider) => provider.id === settings.current,
  );

  const titles: Record<View, string> = {
    chat: "Conversación",
    library: "Biblioteca",
    study: "Estudiar",
    settings: "Ajustes",
  };

  const providerReady = Boolean(
    activeProvider && (!activeProvider.requires_key || activeProvider.has_key),
  );

  return (
    <div className="paper-grain flex h-screen overflow-hidden bg-paper text-ink">
      <div className="relative z-10 hidden md:flex">
        <Sidebar
          subjects={subjects}
          activeSubject={activeSubject}
          onSelectSubject={(id) => setActiveSubject(id)}
          conversations={conversations}
          activeConversation={conversationId}
          onSelectConversation={(id) => void openConversation(id)}
          onNewConversation={newConversation}
          onCreateSubject={createSubject}
          onDeleteSubject={(id) => void deleteSubject(id)}
          view={view}
          onNavigate={navigate}
          theme={theme}
          onToggleTheme={toggle}
        />
      </div>

      {sidebarOpen ? (
        <div className="fixed inset-0 z-30 flex md:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-ink/30"
            onClick={() => setSidebarOpen(false)}
            aria-label="Cerrar menu"
          />
          <div className="relative z-10 h-full">
            <Sidebar
              subjects={subjects}
              activeSubject={activeSubject}
              onSelectSubject={(id) => setActiveSubject(id)}
              conversations={conversations}
              activeConversation={conversationId}
              onSelectConversation={(id) => void openConversation(id)}
              onNewConversation={newConversation}
              onCreateSubject={createSubject}
              onDeleteSubject={(id) => void deleteSubject(id)}
              view={view}
              onNavigate={navigate}
              theme={theme}
              onToggleTheme={toggle}
              onClose={() => setSidebarOpen(false)}
            />
          </div>
        </div>
      ) : null}

      <div className="relative z-10 flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-rule px-4 py-2.5 md:px-7">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="rounded-md p-1.5 text-muted hover:bg-accent-soft/60 md:hidden"
            aria-label="Abrir menu"
          >
            <Menu className="h-5 w-5" />
          </button>

          <div className="min-w-0 flex-1">
            <h1 className="truncate font-serif text-[17px] leading-tight">
              {titles[view]}
            </h1>
            {view === "chat" ? (
              <p className="truncate text-[11px] text-muted">
                {subject ? subject.name : "Todas las materias"}
                {meta?.provider ? ` · vía ${meta.provider}` : ""}
              </p>
            ) : null}
          </div>

          <button
            type="button"
            onClick={() => navigate("settings")}
            className="hidden sm:block"
            title="Proveedor de IA"
          >
            {activeProvider ? (
              <Chip
                tone={
                  activeProvider.requires_key && !activeProvider.has_key
                    ? "warning"
                    : "neutral"
                }
              >
                {activeProvider.label}
                <span className="text-muted">
                  {activeProvider.requires_key && !activeProvider.has_key
                    ? " · sin clave"
                    : ` · ${activeProvider.model || "modelo"}`}
                </span>
              </Chip>
            ) : (
              <Chip tone="warning">configura tu IA</Chip>
            )}
          </button>
        </header>

        {bootError ? (
          <div className="px-4 pt-3 md:px-7">
            <Banner tone="danger">
              {bootError}. Comprueba que el backend esté arrancado en{" "}
              <code>127.0.0.1:8000</code>.
            </Banner>
          </div>
        ) : null}

        <main className="min-h-0 flex-1">
          {booting ? (
            <div className="flex h-full items-center justify-center gap-2 text-sm text-muted">
              <Spinner /> Cargando Chuletín…
            </div>
          ) : view === "chat" ? (
            <ChatView
              turns={turns}
              streaming={streaming}
              onAsk={(question) => void ask(question)}
              onStop={stop}
              onCitation={(citation) => setSource(citation)}
              subjectName={subject?.name ?? null}
              hasDocuments={visibleDocuments.length > 0}
              onOpenLibrary={() => navigate("library")}
              onOpenSettings={() => navigate("settings")}
              error={chatError}
              onDismissError={() => setChatError(null)}
            />
          ) : view === "library" ? (
            <LibraryView
              subjects={subjects}
              subject={subject}
              documents={visibleDocuments}
              onSelectSubject={(id) => setActiveSubject(id)}
              onCreateSubject={createSubject}
              onUpload={uploadFiles}
              onAddUrl={addUrl}
              onAddText={addText}
              onDelete={removeDocument}
              onReindex={reindexDocument}
              uploads={uploads}
            />
          ) : view === "study" ? (
            <StudyView
              subject={subject}
              subjects={subjects}
              onSelectSubject={(id) => setActiveSubject(id)}
              onCitation={(citation) => setSource(citation)}
              onOpenSettings={() => navigate("settings")}
              providerReady={providerReady}
            />
          ) : (
            <SettingsView
              settings={settings}
              onSaveProvider={saveProvider}
              onTestProvider={testProvider}
              onSetOcr={setOcr}
              onRefresh={loadSettings}
            />
          )}
        </main>
      </div>

      <SourcePanel
        citation={source}
        document={documents.find((item) => item.id === source?.document_id)}
        onClose={() => setSource(null)}
      />
    </div>
  );
}
