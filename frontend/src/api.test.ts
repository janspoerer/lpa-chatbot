import { afterEach, describe, expect, it, vi } from "vitest";
import { streamChat, type AgentEvent } from "./api";
import { sseFrame, sseResponse } from "./test/sse";

async function collect(gen: AsyncGenerator<AgentEvent>): Promise<AgentEvent[]> {
  const out: AgentEvent[] = [];
  for await (const ev of gen) out.push(ev);
  return out;
}

function mockFetch(response: Response) {
  const spy = vi.fn(async () => response);
  vi.stubGlobal("fetch", spy);
  return spy;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("streamChat", () => {
  it("parses a well-formed event stream", async () => {
    const frames = [
      sseFrame({ type: "tool_call", name: "list_files", arguments: {} }),
      sseFrame({
        type: "tool_result",
        name: "list_files",
        result_preview: "a.md, b.md",
      }),
      sseFrame({ type: "answer", content: "Hello" }),
      sseFrame({ type: "done" }),
    ];
    mockFetch(sseResponse(frames));

    const events = await collect(
      streamChat([{ role: "user", content: "hi" }]),
    );

    expect(events).toHaveLength(4);
    expect(events[0]).toMatchObject({ type: "tool_call", name: "list_files" });
    expect(events[2]).toMatchObject({ type: "answer", content: "Hello" });
    expect(events[3]).toMatchObject({ type: "done" });
  });

  it("handles frames split across multiple chunks", async () => {
    // Split a single SSE frame across arbitrary byte boundaries.
    const answer = sseFrame({ type: "answer", content: "stitched" });
    const mid = Math.floor(answer.length / 2);
    const chunks = [answer.slice(0, mid), answer.slice(mid), sseFrame({ type: "done" })];
    mockFetch(sseResponse(chunks));

    const events = await collect(
      streamChat([{ role: "user", content: "x" }]),
    );

    expect(events).toEqual([
      { type: "answer", content: "stitched" },
      { type: "done" },
    ]);
  });

  it("handles multiple frames arriving in one chunk", async () => {
    const combined =
      sseFrame({ type: "tool_call", name: "read_file", arguments: { filename: "a.md" } }) +
      sseFrame({ type: "tool_result", name: "read_file", result_preview: "..." }) +
      sseFrame({ type: "answer", content: "ok" }) +
      sseFrame({ type: "done" });
    mockFetch(sseResponse([combined]));

    const events = await collect(
      streamChat([{ role: "user", content: "x" }]),
    );

    expect(events.map((e) => e.type)).toEqual([
      "tool_call",
      "tool_result",
      "answer",
      "done",
    ]);
  });

  it("ignores malformed JSON payloads without throwing", async () => {
    const chunks = [
      "data: {not json}\n\n",
      sseFrame({ type: "answer", content: "recovered" }),
      sseFrame({ type: "done" }),
    ];
    mockFetch(sseResponse(chunks));

    const events = await collect(
      streamChat([{ role: "user", content: "x" }]),
    );

    expect(events).toHaveLength(2);
    expect(events[0]).toMatchObject({ type: "answer", content: "recovered" });
  });

  it("ignores non-data lines (e.g. comments)", async () => {
    const chunks = [
      ": heartbeat\n\n",
      sseFrame({ type: "answer", content: "hi" }),
      sseFrame({ type: "done" }),
    ];
    mockFetch(sseResponse(chunks));

    const events = await collect(
      streamChat([{ role: "user", content: "x" }]),
    );

    expect(events.map((e) => e.type)).toEqual(["answer", "done"]);
  });

  it("throws on non-OK HTTP response", async () => {
    mockFetch(new Response("nope", { status: 500 }));

    await expect(
      collect(streamChat([{ role: "user", content: "x" }])),
    ).rejects.toThrow(/HTTP 500/);
  });

  it("sends only role and content in the request body", async () => {
    const spy = mockFetch(sseResponse([sseFrame({ type: "done" })]));

    await collect(
      streamChat([
        {
          role: "user",
          content: "hello",
          toolCalls: [{ name: "x", arguments: {} }],
        },
      ]),
    );

    expect(spy).toHaveBeenCalledTimes(1);
    const [, init] = spy.mock.calls[0] as unknown as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body).toEqual({
      messages: [{ role: "user", content: "hello" }],
    });
  });
});
