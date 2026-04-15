import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "./App";
import type { AgentEvent } from "./api";

// Mock the api module so we don't touch real fetch.
vi.mock("./api", () => ({
  streamChat: vi.fn(),
}));
import { streamChat } from "./api";

const mockedStream = streamChat as unknown as ReturnType<typeof vi.fn>;

async function* yieldEvents(events: AgentEvent[]): AsyncGenerator<AgentEvent> {
  for (const ev of events) yield ev;
}

beforeEach(() => {
  mockedStream.mockReset();
  localStorage.clear();
  // jsdom doesn't implement confirm by default — auto-accept.
  vi.stubGlobal("confirm", () => true);
  // scrollIntoView is also not implemented.
  Element.prototype.scrollIntoView = vi.fn();
});

describe("App", () => {
  it("renders the empty-state hint when there is no history", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: /Lp\(a\) Chatbot/i })).toBeInTheDocument();
    expect(screen.getByText(/Frag mich etwas/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Senden/i })).toBeDisabled();
  });

  it("loads prior messages from localStorage", () => {
    localStorage.setItem(
      "lpa-chat-history-v1",
      JSON.stringify([
        { role: "user", content: "Frage?" },
        { role: "assistant", content: "Antwort." },
      ]),
    );
    render(<App />);
    expect(screen.getByText("Frage?")).toBeInTheDocument();
    expect(screen.getByText("Antwort.")).toBeInTheDocument();
  });

  it("sends a message, streams events, persists the result", async () => {
    mockedStream.mockImplementation((_messages) =>
      yieldEvents([
        { type: "tool_call", name: "list_files", arguments: {} },
        { type: "tool_result", name: "list_files", result_preview: "a.md" },
        { type: "answer", content: "Die Antwort." },
        { type: "done" },
      ]),
    );

    const user = userEvent.setup();
    render(<App />);

    await user.type(
      screen.getByPlaceholderText(/Frag mich etwas/i),
      "Was ist Lp(a)?",
    );
    await user.click(screen.getByRole("button", { name: /Senden/i }));

    await waitFor(() => {
      expect(screen.getByText("Die Antwort.")).toBeInTheDocument();
    });
    expect(screen.getByText("Was ist Lp(a)?")).toBeInTheDocument();

    // streamChat called once, with the user message appended.
    expect(mockedStream).toHaveBeenCalledTimes(1);
    const args = mockedStream.mock.calls[0][0];
    expect(args).toEqual([{ role: "user", content: "Was ist Lp(a)?" }]);

    // Persisted to localStorage.
    const saved = JSON.parse(localStorage.getItem("lpa-chat-history-v1")!);
    expect(saved).toHaveLength(2);
    expect(saved[1].role).toBe("assistant");
    expect(saved[1].content).toBe("Die Antwort.");
    expect(saved[1].toolCalls).toHaveLength(1);
    expect(saved[1].toolCalls[0]).toMatchObject({
      name: "list_files",
      resultPreview: "a.md",
    });
  });

  it("surfaces stream errors in a dedicated error card", async () => {
    mockedStream.mockImplementation(() =>
      yieldEvents([
        { type: "error", message: "LLM exploded" },
        { type: "done" },
      ]),
    );

    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByPlaceholderText(/Frag mich etwas/i), "hi");
    await user.click(screen.getByRole("button", { name: /Senden/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(screen.getByText(/LLM exploded/)).toBeInTheDocument();
    expect(screen.getByText(/Es ist ein Fehler aufgetreten/i)).toBeInTheDocument();
  });

  it("clears history when the clear button is pressed", async () => {
    localStorage.setItem(
      "lpa-chat-history-v1",
      JSON.stringify([{ role: "user", content: "alte Frage" }]),
    );
    const user = userEvent.setup();
    render(<App />);

    expect(screen.getByText("alte Frage")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Verlauf löschen/i }));

    expect(screen.queryByText("alte Frage")).not.toBeInTheDocument();
    // History effect re-saves [] right after removeItem — either state is "empty".
    const raw = localStorage.getItem("lpa-chat-history-v1");
    expect(raw === null || raw === "[]").toBe(true);
  });

  it("disables the send button for empty/whitespace input", async () => {
    const user = userEvent.setup();
    render(<App />);
    const send = screen.getByRole("button", { name: /Senden/i });
    expect(send).toBeDisabled();
    await user.type(screen.getByPlaceholderText(/Frag mich etwas/i), "   ");
    expect(send).toBeDisabled();
  });
});
