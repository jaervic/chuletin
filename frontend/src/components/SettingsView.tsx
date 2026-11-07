import { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  Cpu,
  ExternalLink,
  KeyRound,
  Loader2,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import type { ProviderTest, SettingsResponse } from "../types";
import { Banner, Button, Chip, Field, Spinner, cx, inputClass } from "./ui";
import { api } from "../lib/api";

interface SettingsViewProps {
  settings: SettingsResponse | null;
  onSaveProvider: (payload: {
    provider: string;
    model: string;
    api_key?: string | null;
    base_url?: string | null;
  }) => Promise<void>;
  onTestProvider: (payload: {
    provider: string;
    model?: string;
    api_key?: string | null;
    base_url?: string | null;
  }) => Promise<ProviderTest>;
  onSetOcr: (enabled: boolean) => Promise<void>;
  onRefresh: () => Promise<void>;
}

export function SettingsView({
  settings,
  onSaveProvider,
  onTestProvider,
  onSetOcr,
  onRefresh,
}: SettingsViewProps) {
  const [selected, setSelected] = useState<string>("gemini");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState<{ tone: "success" | "danger"; text: string } | null>(
    null,
  );
  const [models, setModels] = useState<string[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [ocrEnabled, setOcrEnabled] = useState(false);

  const providers = settings?.providers ?? [];
  const current = useMemo(
    () => providers.find((item) => item.id === selected) ?? null,
    [providers, selected],
  );

  useEffect(() => {
    if (!settings) return;
    setOcrEnabled(settings.ocr_enabled);
    setSelected((value) => value || settings.current);
  }, [settings]);

  useEffect(() => {
    if (!current) return;
    setModel(current.model);
    setBaseUrl(current.base_url ?? "");
    setApiKey("");
    setModels([]);
    setMessage(null);
  }, [current?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function save() {
    if (!current) return;
    setSaving(true);
    setMessage(null);
    try {
      await onSaveProvider({
        provider: current.id,
        model: model.trim() || current.default_model,
        api_key: apiKey.trim() ? apiKey.trim() : undefined,
        base_url: baseUrl.trim() || undefined,
      });
      setApiKey("");
      setMessage({ tone: "success", text: "Ajustes guardados." });
      await onRefresh();
    } catch (caught) {
      setMessage({
        tone: "danger",
        text: caught instanceof Error ? caught.message : "No se pudo guardar",
      });
    } finally {
      setSaving(false);
    }
  }

  async function test() {
    if (!current) return;
    setTesting(true);
    setMessage(null);
    try {
      const result = await onTestProvider({
        provider: current.id,
        model: model.trim() || current.default_model,
        api_key: apiKey.trim() ? apiKey.trim() : undefined,
        base_url: baseUrl.trim() || undefined,
      });
      if (result.ok) {
        setModels(result.models);
        setMessage({
          tone: "success",
          text: result.models.length
            ? `${result.message} Elige un modelo de la lista.`
            : result.message,
        });
      } else {
        setMessage({ tone: "danger", text: result.message });
      }
    } catch (caught) {
      setMessage({
        tone: "danger",
        text: caught instanceof Error ? caught.message : "No se pudo probar",
      });
    } finally {
      setTesting(false);
    }
  }

  async function loadModels() {
    if (!current) return;
    setLoadingModels(true);
    setMessage(null);
    try {
      const result = await api.settings.models(current.id);
      setModels(result.models);
      if (!result.models.length) {
        setMessage({ tone: "danger", text: "El proveedor no devolvió modelos." });
      }
    } catch (caught) {
      setMessage({
        tone: "danger",
        text:
          caught instanceof Error
            ? `${caught.message} Guarda la clave antes de cargar modelos.`
            : "No se pudieron cargar los modelos",
      });
    } finally {
      setLoadingModels(false);
    }
  }

  async function toggleOcr() {
    const next = !ocrEnabled;
    setOcrEnabled(next);
    try {
      await onSetOcr(next);
    } catch {
      setOcrEnabled(!next);
    }
  }

  return (
    <div className="scroll-thin h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-4xl px-5 py-8 md:px-8">
        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-accent">
          Ajustes
        </p>
        <h1 className="mt-2 font-serif text-3xl">Motor de IA</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
          Chuletín no incluye claves. Elige un proveedor, pega la tuya y prueba la
          conexión. Solo se envían al proveedor los fragmentos citados de tus apuntes.
        </p>

        <div className="mt-6 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {providers.map((provider) => (
            <button
              key={provider.id}
              type="button"
              onClick={() => setSelected(provider.id)}
              className={cx(
                "flex flex-col items-start gap-1 rounded-xl border px-4 py-3 text-left transition",
                selected === provider.id
                  ? "border-accent bg-accent-soft/60"
                  : "border-rule bg-raised/70 hover:border-accent/40",
              )}
            >
              <span className="flex w-full items-center justify-between gap-2">
                <span className="text-sm font-medium">{provider.label}</span>
                {settings?.current === provider.id ? (
                  <Chip tone="accent">activo</Chip>
                ) : provider.has_key ? (
                  <CheckCircle2 className="h-3.5 w-3.5 text-success" />
                ) : null}
              </span>
              <span className="text-[11px] text-muted">
                {provider.has_key ? `clave ${provider.key_hint}` : "sin clave"}
              </span>
            </button>
          ))}
        </div>

        {current ? (
          <div className="mt-6 rounded-xl border border-rule bg-raised/80 p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-serif text-xl">{current.label}</h2>
              {current.help_url ? (
                <a
                  href={current.help_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-[12px] text-accent underline underline-offset-2"
                >
                  Obtener una clave
                  <ExternalLink className="h-3 w-3" />
                </a>
              ) : null}
            </div>

            <div className="mt-4 grid gap-4">
              {current.kind === "openai" ? (
                <Field
                  label="URL base"
                  hint="Debe incluir la versión de la API, por ejemplo https://api.deepseek.com/v1"
                >
                  <input
                    value={baseUrl}
                    onChange={(event) => setBaseUrl(event.target.value)}
                    placeholder="https://…/v1"
                    className={inputClass}
                  />
                </Field>
              ) : null}

              <Field label="Clave de API" hint={current.has_key ? `Guardada: ${current.key_hint}` : "Aún no hay clave guardada"}>
                <div className="relative">
                  <KeyRound className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(event) => setApiKey(event.target.value)}
                    placeholder={current.has_key ? "Dejar vacío para conservar la actual" : "Pega tu clave aquí"}
                    className={cx(inputClass, "pl-9")}
                    autoComplete="off"
                  />
                </div>
              </Field>

              <Field label="Modelo" hint="Puedes escribir cualquiera que admita el proveedor.">
                <div className="flex flex-wrap gap-2">
                  <input
                    value={model}
                    onChange={(event) => setModel(event.target.value)}
                    list="modelos-disponibles"
                    placeholder={current.default_model || "nombre-del-modelo"}
                    className={cx(inputClass, "min-w-[220px] flex-1")}
                  />
                  <datalist id="modelos-disponibles">
                    {models.map((name) => (
                      <option key={name} value={name} />
                    ))}
                  </datalist>
                  <Button variant="secondary" onClick={() => void loadModels()} disabled={loadingModels}>
                    {loadingModels ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                    Ver modelos
                  </Button>
                </div>
              </Field>
            </div>

            {message ? (
              <div className="mt-4">
                <Banner tone={message.tone}>{message.text}</Banner>
              </div>
            ) : null}

            <div className="mt-5 flex flex-wrap gap-2">
              <Button variant="primary" onClick={() => void save()} disabled={saving}>
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Guardar y usar
              </Button>
              <Button variant="secondary" onClick={() => void test()} disabled={testing}>
                {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Probar conexión
              </Button>
            </div>
          </div>
        ) : (
          <div className="mt-6 flex items-center gap-2 text-sm text-muted">
            <Spinner /> Cargando proveedores…
          </div>
        )}

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <div className="rounded-xl border border-rule bg-raised/80 p-5">
            <h2 className="flex items-center gap-2 font-serif text-lg">
              <Cpu className="h-4 w-4 text-accent" />
              Índice local
            </h2>
            <p className="mt-2 text-[13px] leading-6 text-muted">
              Los embeddings se calculan en tu equipo. El modelo se descarga una sola vez
              (~500 MB).
            </p>
            <dl className="mt-3 space-y-1 text-[12px]">
              <div className="flex justify-between gap-4">
                <dt className="text-muted">Modelo</dt>
                <dd className="truncate text-right">
                  {settings?.embeddings.model ?? "por determinar"}
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted">Dimensión</dt>
                <dd>{settings?.embeddings.dim ?? "—"}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted">Estado</dt>
                <dd>
                  {settings?.embeddings.ready ? (
                    <span className="inline-flex items-center gap-1 text-success">
                      <CheckCircle2 className="h-3.5 w-3.5" /> listo
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-muted">
                      <XCircle className="h-3.5 w-3.5" /> se descargará al indexar
                    </span>
                  )}
                </dd>
              </div>
            </dl>
          </div>

          <div className="rounded-xl border border-rule bg-raised/80 p-5">
            <h2 className="font-serif text-lg">Lectura de imágenes</h2>
            <p className="mt-2 text-[13px] leading-6 text-muted">
              Activa el OCR para leer fotos y escaneos. Necesita{" "}
              <code className="rounded bg-accent-soft/70 px-1 py-0.5 text-[12px]">
                tesseract-ocr
              </code>{" "}
              instalado en el sistema.
            </p>
            <label className="mt-4 flex cursor-pointer items-center gap-3">
              <span
                className={cx(
                  "relative inline-flex h-6 w-11 items-center rounded-full transition",
                  ocrEnabled ? "bg-accent" : "bg-rule",
                )}
              >
                <input
                  type="checkbox"
                  checked={ocrEnabled}
                  onChange={() => void toggleOcr()}
                  className="sr-only"
                />
                <span
                  className={cx(
                    "inline-block h-4 w-4 transform rounded-full bg-raised shadow transition",
                    ocrEnabled ? "translate-x-6" : "translate-x-1",
                  )}
                />
              </span>
              <span className="text-sm">{ocrEnabled ? "OCR activado" : "OCR desactivado"}</span>
            </label>
          </div>
        </div>

        <div className="mt-4 rounded-xl border border-success/25 bg-success/5 p-5">
          <h2 className="flex items-center gap-2 font-serif text-lg">
            <ShieldCheck className="h-4 w-4 text-success" />
            Privacidad y seguridad
          </h2>
          <ul className="mt-2 space-y-1 text-[13px] leading-6 text-muted">
            <li>· El servidor escucha solo en 127.0.0.1.</li>
            <li>· Tus documentos y el índice se quedan en este equipo.</li>
            <li>· Las claves se guardan con permisos 600 y nunca se muestran.</li>
            <li>· Los documentos se extraen en un proceso aislado y con límites.</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
