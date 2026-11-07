import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

const ALLOWED_PROTOCOLS = new Set(["http:", "https:", "mailto:"]);

function urlTransform(url: string): string {
  if (url.startsWith("#")) return url;
  try {
    const parsed = new URL(url, window.location.origin);
    if (ALLOWED_PROTOCOLS.has(parsed.protocol)) return url;
  } catch {
    return "";
  }
  return "";
}

/** Convierte [1], [2]... en enlaces internos sin tocar bloques de codigo. */
export function linkCitations(text: string): string {
  const parts = text.split(/(```[\s\S]*?```|`[^`\n]*`)/g);
  return parts
    .map((part, index) =>
      index % 2 === 1 ? part : part.replace(/\[(\d{1,2})\]/g, "[$1](#cita-$1)"),
    )
    .join("");
}

export function Markdown({
  content,
  onCitation,
}: {
  content: string;
  onCitation?: (index: number) => void;
}) {
  const prepared = useMemo(() => linkCitations(content), [content]);

  return (
    <div className="prose-chuletin">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        urlTransform={urlTransform}
        components={{
          a({ href, children }) {
            const match = href?.match(/^#cita-(\d+)$/);
            if (match) {
              const index = Number(match[1]);
              return (
                <button
                  type="button"
                  className="cita"
                  onClick={() => onCitation?.(index)}
                  aria-label={`Ver fuente ${index}`}
                >
                  {children}
                </button>
              );
            }
            return (
              <a href={href} target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            );
          },
        }}
      >
        {prepared}
      </ReactMarkdown>
    </div>
  );
}
