import { useEffect, useRef, useState } from "react";
import type { ChatMessage, ToolCall } from "./types";
import { streamChat } from "./api";
import { RedCross } from "./components/RedCross";
import { SourceTrace } from "./components/SourceTrace";
import { AssistantBody } from "./components/AssistantBody";

const STORAGE_KEY = "lpa-chat-history-v1";
const DISCLAIMER_KEY = "lpa-disclaimer-dismissed-v1";

const STARTERS = [
  "Was ist Lipoprotein(a)?",
  "Welche Medikamente gegen Lp(a) sind in Entwicklung?",
  "Wie wird Lp(a) gemessen?",
  "Senken Statine den Lp(a)-Wert?",
];

function loadHistory(): ChatMessage[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as ChatMessage[]) : [];
  } catch {
    return [];
  }
}

function saveHistory(messages: ChatMessage[]) {
  if (messages.length === 0) {
    localStorage.removeItem(STORAGE_KEY);
  } else {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
  }
}

export function App() {
  const [messages, setMessages] = useState<ChatMessage[]>(() => loadHistory());
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [pendingTools, setPendingTools] = useState<ToolCall[]>([]);
  const [pendingAnswer, setPendingAnswer] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [disclaimerDismissed, setDisclaimerDismissed] = useState<boolean>(
    () => localStorage.getItem(DISCLAIMER_KEY) === "1",
  );
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    saveHistory(messages);
  }, [messages]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pendingAnswer, pendingTools]);

  async function sendText(text: string) {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    const userMsg: ChatMessage = { role: "user", content: trimmed };
    const next = [...messages, userMsg];
    setMessages(next);
    setInput("");
    setBusy(true);
    setError(null);
    setPendingTools([]);
    setPendingAnswer("");

    const tools: ToolCall[] = [];
    let answer = "";
    let errMessage: string | null = null;
    try {
      for await (const ev of streamChat(next)) {
        if (ev.type === "tool_call") {
          tools.push({ name: ev.name, arguments: ev.arguments });
          setPendingTools([...tools]);
        } else if (ev.type === "tool_result") {
          for (let i = tools.length - 1; i >= 0; i--) {
            if (tools[i].name === ev.name && !tools[i].resultPreview) {
              tools[i].resultPreview = ev.result_preview;
              break;
            }
          }
          setPendingTools([...tools]);
        } else if (ev.type === "answer") {
          answer = ev.content;
          setPendingAnswer(answer);
        } else if (ev.type === "error") {
          errMessage = ev.message;
        }
      }
    } catch (e) {
      errMessage = (e as Error).message;
    }

    if (errMessage && !answer) {
      setError(errMessage);
      setMessages(next);
    } else {
      setMessages([
        ...next,
        { role: "assistant", content: answer, toolCalls: tools },
      ]);
    }
    setPendingTools([]);
    setPendingAnswer("");
    setBusy(false);
  }

  function send() {
    void sendText(input);
  }

  function clearHistory() {
    if (!confirm("Gesamten Chat-Verlauf löschen?")) return;
    setMessages([]);
    setError(null);
    localStorage.removeItem(STORAGE_KEY);
  }

  function dismissDisclaimer() {
    setDisclaimerDismissed(true);
    localStorage.setItem(DISCLAIMER_KEY, "1");
  }

  const isEmpty = messages.length === 0 && !busy && !error;

  const composer = (
    <div className="composer">
      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send();
          }
        }}
        placeholder="Frag mich etwas über Lipoprotein(a)…"
        disabled={busy}
        rows={2}
      />
      <div className="composer-row">
        <div className="composer-hint">↵ senden · ⇧↵ neue Zeile</div>
        <button
          className="btn-primary"
          onClick={send}
          disabled={busy || !input.trim()}
        >
          Senden
        </button>
      </div>
    </div>
  );

  return (
    <div className={`app${isEmpty ? " app-empty" : ""}`}>
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark" aria-hidden>
            <RedCross size={22} />
          </span>
          <div className="brand-text">
            <h1 className="brand-title">Lp(a) Chatbot</h1>
            <div className="brand-subtitle">
              Wissensbasierte Antworten aus meiner Literaturdatenbank
            </div>
          </div>
        </div>
        <button
          className="btn-ghost"
          onClick={clearHistory}
          disabled={busy || messages.length === 0}
        >
          Verlauf löschen
        </button>
      </header>

      {!disclaimerDismissed && (
        <div className="disclaimer">
          <div className="disclaimer-body">
            <strong>Keine medizinische Beratung.</strong> Diese Anwendung dient ausschließlich zu Informationszwecken und ist primär für meine eigenen Zwecke erstellt worden.
          </div>
          <button
            className="disclaimer-dismiss"
            onClick={dismissDisclaimer}
            aria-label="Hinweis schließen"
          >
            ×
          </button>
        </div>
      )}

      <main className="transcript">
        {isEmpty && (
          <div className="empty">
            <div className="empty-mark">
              <RedCross size={30} />
            </div>
            <div className="starter-chips">
              {STARTERS.map((s) => (
                <button
                  key={s}
                  className="starter-chip"
                  onClick={() => void sendText(s)}
                >
                  {s}
                </button>
              ))}
            </div>
            <div className="empty-composer">{composer}</div>
          </div>
        )}

        {messages.map((m, i) => (
          <TranscriptEntry key={i} msg={m} />
        ))}

        {busy && (
          <TranscriptEntry
            msg={{
              role: "assistant",
              content: pendingAnswer,
              toolCalls: pendingTools,
            }}
            pending
          />
        )}

        {error && (
          <div className="error-card" role="alert">
            <span className="error-icon" aria-hidden>
              <RedCross size={18} />
            </span>
            <div>
              <div className="error-title">Es ist ein Fehler aufgetreten</div>
              <div className="error-message">{error}</div>
            </div>
          </div>
        )}

        <div ref={endRef} />
      </main>

      {!isEmpty && <footer className="composer-wrap">{composer}</footer>}
    </div>
  );
}

function TranscriptEntry({
  msg,
  pending,
}: {
  msg: ChatMessage;
  pending?: boolean;
}) {
  const isUser = msg.role === "user";
  return (
    <article className={`entry entry-${msg.role}${pending ? " entry-pending" : ""}`}>
      <div className="entry-label">
        {isUser ? "Du" : "Assistent"}
        {pending && (
          <span className="pulse-mark" aria-hidden>
            <RedCross size={11} />
          </span>
        )}
      </div>
      {!isUser && msg.toolCalls && msg.toolCalls.length > 0 && (
        <SourceTrace toolCalls={msg.toolCalls} />
      )}
      {isUser ? (
        <div className="entry-body user-body">{msg.content}</div>
      ) : msg.content ? (
        <AssistantBody content={msg.content} />
      ) : (
        <div className="entry-body shimmer">…</div>
      )}
    </article>
  );
}
