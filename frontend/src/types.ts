export type Role = "user" | "assistant";

export interface ToolCall {
  name: string;
  arguments: Record<string, unknown>;
  resultPreview?: string;
}

export interface ChatMessage {
  role: Role;
  content: string;
  toolCalls?: ToolCall[];
}
