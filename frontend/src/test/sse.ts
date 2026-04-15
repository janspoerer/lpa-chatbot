import type { AgentEvent } from "../api";

/** Build a fetch Response whose body streams SSE chunks. */
export function sseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const c of chunks) controller.enqueue(encoder.encode(c));
      controller.close();
    },
  });
  return new Response(stream, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

/** Serialize an event as one SSE frame (`data: ...\n\n`). */
export function sseFrame(ev: AgentEvent): string {
  return `data: ${JSON.stringify(ev)}\n\n`;
}
