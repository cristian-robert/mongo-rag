/**
 * Shared widget types.
 */

export type Position = "bottom-right" | "bottom-left";

export interface WidgetConfig {
  apiKey: string;
  apiUrl: string;
  botId?: string;
  primaryColor: string;
  botName: string;
  welcomeMessage: string;
  position: Position;
  showBranding: boolean;
}

export interface ChatSource {
  document_title: string;
  heading_path: string[];
  snippet: string;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  sources?: ChatSource[];
  pending?: boolean;
  /** Set when the bubble represents a terminal failure — drives retry UI. */
  error?: boolean;
}

export interface SSEEvent {
  type: string;
  content?: string;
  message?: string;
  sources?: ChatSource[];
  conversation_id?: string;
  [key: string]: unknown;
}
