export type SourceType =
  | "pdf"
  | "docx"
  | "pptx"
  | "web"
  | "youtube"
  | "image"
  | "text";

export type DocumentStatus =
  | "pending"
  | "reading"
  | "indexing"
  | "ready"
  | "error";

export interface Subject {
  id: string;
  name: string;
  color: string;
  created_at: string;
  document_count: number;
}

export interface DocumentItem {
  id: string;
  subject_id: string;
  title: string;
  original_name: string | null;
  source_type: SourceType;
  source_uri: string | null;
  size_bytes: number;
  page_count: number | null;
  status: DocumentStatus;
  progress: number;
  error: string | null;
  chunk_count: number;
  created_at: string;
  indexed_at: string | null;
}

export interface Citation {
  index: number;
  document_id: string;
  document_title: string;
  source_type: SourceType;
  page_from: number | null;
  page_to: number | null;
  heading: string | null;
  snippet: string;
  score: number;
  locator: string | null;
}

export interface ChatTurn {
  id?: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  provider?: string | null;
  model?: string | null;
  latency_ms?: number | null;
  pending?: boolean;
  failed?: boolean;
}

export interface ConversationSummary {
  id: string;
  title: string;
  subject_id: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface CitationRecord {
  id: number;
  message_id: string;
  chunk_id: number | null;
  document_id: string | null;
  page_from: number | null;
  page_to: number | null;
  heading: string | null;
  score: number | null;
  snippet: string;
}

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  provider: string | null;
  model: string | null;
  latency_ms: number | null;
  created_at: string;
  citations: CitationRecord[];
}

export interface ProviderPreset {
  id: string;
  label: string;
  kind: string;
  base_url: string | null;
  default_model: string;
  requires_key: boolean;
  help_url: string | null;
  provider: string;
  model: string;
  has_key: boolean;
  key_hint: string | null;
}

export interface SettingsResponse {
  current: string;
  providers: ProviderPreset[];
  ocr_enabled: boolean;
  embeddings: {
    model: string | null;
    dim: number | null;
    ready: boolean;
  };
  limits: {
    max_upload_mb: number;
    max_pages: number;
    max_context_chunks: number;
  };
}

export interface ProviderTest {
  ok: boolean;
  message: string;
  models: string[];
}

export type StudyKind = "summary" | "outline" | "deck" | "quiz";
export type StudyStatus = "generating" | "ready" | "error";

export interface StudySet {
  id: string;
  subject_id: string;
  kind: StudyKind;
  title: string;
  topic: string | null;
  status: StudyStatus;
  content: string | null;
  provider: string | null;
  model: string | null;
  error: string | null;
  score: number | null;
  created_at: string;
  updated_at: string;
  card_count: number | null;
  due_count: number | null;
  item_count: number | null;
  answered_count: number | null;
}

export interface StudyCard {
  id: string;
  set_id: string;
  front: string;
  back: string;
  source_index: number | null;
  ease: number;
  interval_days: number;
  repetitions: number;
  lapses: number;
  due_at: string;
  created_at: string;
  last_reviewed_at: string | null;
}

export interface QuizItem {
  id: string;
  set_id: string;
  position: number;
  question: string;
  options: string[];
  correct_index: number;
  explanation: string | null;
  source_index: number | null;
  chosen_index: number | null;
  is_correct: number | null;
}

export interface StudyDetail {
  set: StudySet;
  citations: Citation[];
  cards?: StudyCard[];
  items?: QuizItem[];
}

export interface ChatPayload {
  question: string;
  subject_id?: string | null;
  document_ids?: string[] | null;
  conversation_id?: string | null;
}

export interface ChatMeta {
  conversation_id: string;
  citations: Citation[];
  provider: string | null;
  model: string | null;
  configured: boolean;
  hit_count?: number;
}

export type ChatEvent =
  | { type: "meta"; data: ChatMeta }
  | { type: "delta"; data: { text: string } }
  | { type: "done"; data: { text: string; message_id?: string; latency_ms?: number } }
  | { type: "error"; data: { message: string } };
