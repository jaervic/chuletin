import type { DocumentStatus, SourceType } from "../types";

export function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / Math.pow(1024, index);
  return `${value >= 10 || index === 0 ? Math.round(value) : value.toFixed(1)} ${units[index]}`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("es", { day: "2-digit", month: "short", year: "numeric" });
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  const diff = Date.now() - date.getTime();
  if (Number.isNaN(diff)) return "";
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "ahora";
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `hace ${hours} h`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `hace ${days} d`;
  return formatDate(iso);
}

export const STATUS_LABEL: Record<DocumentStatus, string> = {
  pending: "En cola",
  reading: "Leyendo",
  indexing: "Indexando",
  ready: "Listo",
  error: "Error",
};

export const SOURCE_LABEL: Record<SourceType, string> = {
  pdf: "PDF",
  docx: "Word",
  pptx: "PowerPoint",
  web: "Web",
  youtube: "YouTube",
  image: "Imagen",
  text: "Texto",
};

export function locatorFor(sourceType: SourceType, pageFrom: number | null): string | null {
  if (pageFrom === null || pageFrom === undefined) return null;
  if (sourceType === "youtube") {
    const total = Math.max(0, Math.floor(pageFrom));
    return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
  }
  if (sourceType === "pptx") return `diapositiva ${pageFrom}`;
  return `p. ${pageFrom}`;
}

export function initials(text: string): string {
  return text
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? "")
    .join("");
}
