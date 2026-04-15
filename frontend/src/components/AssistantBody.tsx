import ReactMarkdown from "react-markdown";
import { SourceChip } from "./SourceChip";

interface AssistantBodyProps {
  content: string;
}

// Detects a trailing "**Quellen:**" (or "**Sources:**") line and splits it off
// so the file list can be rendered as chips instead of inline code.
function splitSources(content: string): {
  body: string;
  sources: string[];
} {
  const re = /\n?\*\*(?:Quellen|Sources?):\*\*\s*(.+?)\s*$/s;
  const m = content.match(re);
  if (!m) return { body: content, sources: [] };
  const sourceLine = m[1];
  const sources = [...sourceLine.matchAll(/`([^`]+)`/g)].map((x) => x[1]);
  if (sources.length === 0) return { body: content, sources: [] };
  return { body: content.slice(0, m.index).trimEnd(), sources };
}

export function AssistantBody({ content }: AssistantBodyProps) {
  const { body, sources } = splitSources(content);
  return (
    <div className="assistant-body">
      <ReactMarkdown>{body}</ReactMarkdown>
      {sources.length > 0 && (
        <div className="assistant-sources">
          <div className="assistant-sources-label">Quellen</div>
          <div className="assistant-sources-chips">
            {sources.map((s, i) => (
              <SourceChip key={i} filename={s} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
