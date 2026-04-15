import { useState } from "react";
import type { ToolCall } from "../types";
import { SourceChip } from "./SourceChip";

interface SourceTraceProps {
  toolCalls: ToolCall[];
}

function fileFromCall(tc: ToolCall): string | null {
  const fn = (tc.arguments as { filename?: string }).filename;
  if (typeof fn === "string") return fn;
  if (tc.name === "keyword_search") {
    const q = (tc.arguments as { query?: string }).query;
    return q ? `search: "${q}"` : null;
  }
  if (tc.name === "list_files") return "list_files";
  return null;
}

export function SourceTrace({ toolCalls }: SourceTraceProps) {
  const [openIdx, setOpenIdx] = useState<number | null>(null);
  if (toolCalls.length === 0) return null;

  return (
    <div className="source-trace">
      <div className="source-trace-label">Konsultiert</div>
      <div className="source-trace-chips">
        {toolCalls.map((tc, i) => {
          const label = fileFromCall(tc) ?? tc.name;
          return (
            <SourceChip
              key={i}
              filename={label}
              active={openIdx === i}
              onClick={() =>
                setOpenIdx((prev) => (prev === i ? null : i))
              }
            />
          );
        })}
      </div>
      {openIdx !== null && toolCalls[openIdx]?.resultPreview && (
        <div className="source-trace-preview">
          <div className="source-trace-preview-label">
            {toolCalls[openIdx].name}
          </div>
          <pre>{toolCalls[openIdx].resultPreview}</pre>
        </div>
      )}
    </div>
  );
}
