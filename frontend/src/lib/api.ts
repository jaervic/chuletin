import type {
  ChatEvent,
  ChatPayload,
  ConversationMessage,
  ConversationSummary,
  DocumentItem,
  ProviderPreset,
  ProviderTest,
  SettingsResponse,
  Subject,
} from "../types";

const BASE = "/api";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let detail = `Error ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (Array.isArray(body?.detail)) {
        detail = body.detail
          .map((item: { msg?: string }) => item.msg ?? "")
          .filter(Boolean)
          .join(". ");
      }
    } catch {
      /* respuesta sin JSON */
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  health: () => request<Record<string, unknown>>("/health"),

  subjects: {
    list: () => request<Subject[]>("/subjects"),
    create: (name: string, color = "#6366f1") =>
      request<Subject>("/subjects", {
        method: "POST",
        body: JSON.stringify({ name, color }),
      }),
    update: (id: string, name: string, color: string) =>
      request<Subject>(`/subjects/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ name, color }),
      }),
    remove: (id: string) =>
      request<void>(`/subjects/${id}`, { method: "DELETE" }),
  },

  documents: {
    list: (subjectId?: string) =>
      request<DocumentItem[]>(
        subjectId ? `/documents?subject_id=${encodeURIComponent(subjectId)}` : "/documents",
      ),
    get: (id: string) => request<DocumentItem>(`/documents/${id}`),
    upload: (subjectId: string, file: File, onProgress?: (value: number) => void) =>
      new Promise<DocumentItem>((resolve, reject) => {
        const form = new FormData();
        form.append("subject_id", subjectId);
        form.append("file", file);
        const xhr = new XMLHttpRequest();
        xhr.open("POST", `${BASE}/documents`);
        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable && onProgress) {
            onProgress(event.loaded / event.total);
          }
        };
        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(JSON.parse(xhr.responseText) as DocumentItem);
          } else {
            let detail = `Error ${xhr.status}`;
            try {
              const parsed = JSON.parse(xhr.responseText);
              if (typeof parsed?.detail === "string") detail = parsed.detail;
            } catch {
              /* sin detalle */
            }
            reject(new ApiError(detail, xhr.status));
          }
        };
        xhr.onerror = () => reject(new ApiError("Fallo de red", 0));
        xhr.send(form);
      }),
    fromUrl: (subjectId: string, url: string, kind: "web" | "youtube") =>
      request<DocumentItem>("/documents/url", {
        method: "POST",
        body: JSON.stringify({ subject_id: subjectId, url, kind }),
      }),
    fromText: (subjectId: string, title: string, text: string) =>
      request<DocumentItem>("/documents/text", {
        method: "POST",
        body: JSON.stringify({ subject_id: subjectId, title, text }),
      }),
    remove: (id: string) =>
      request<void>(`/documents/${id}`, { method: "DELETE" }),
    reindex: (id: string) =>
      request<DocumentItem>(`/documents/${id}/reindex`, { method: "POST" }),
    fileUrl: (id: string) => `${BASE}/documents/${id}/file`,
  },

  settings: {
    get: () => request<SettingsResponse>("/settings"),
    saveProvider: (payload: {
      provider: string;
      model: string;
      api_key?: string | null;
      base_url?: string | null;
    }) =>
      request<ProviderPreset>("/settings/provider", {
        method: "PUT",
        body: JSON.stringify(payload),
      }),
    testProvider: (payload: {
      provider: string;
      model?: string;
      api_key?: string | null;
      base_url?: string | null;
    }) =>
      request<ProviderTest>("/settings/provider/test", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    models: (provider: string) =>
      request<{ provider: string; models: string[] }>(
        `/settings/models?provider=${encodeURIComponent(provider)}`,
      ),
    setOcr: (enabled: boolean) =>
      request<{ ocr_enabled: boolean }>("/settings/ocr", {
        method: "PUT",
        body: JSON.stringify({ enabled }),
      }),
  },

  conversations: {
    list: () => request<ConversationSummary[]>("/conversations"),
    get: (id: string) =>
      request<{ conversation: ConversationSummary; messages: ConversationMessage[] }>(
        `/conversations/${id}`,
      ),
    remove: (id: string) =>
      request<void>(`/conversations/${id}`, { method: "DELETE" }),
  },
};

export async function streamChat(
  payload: ChatPayload,
  onEvent: (event: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok || !response.body) {
    let detail = `Error ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* sin detalle */
    }
    throw new ApiError(detail, response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");

      let name = "message";
      const dataLines: string[] = [];
      for (const line of rawEvent.split("\n")) {
        if (line.startsWith("event:")) name = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      if (!dataLines.length) continue;

      try {
        const parsed = JSON.parse(dataLines.join("\n"));
        onEvent({ type: name, data: parsed } as ChatEvent);
      } catch {
        /* evento incompleto */
      }
    }
  }
}
