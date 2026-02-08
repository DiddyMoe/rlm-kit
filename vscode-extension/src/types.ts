/**
 * Shared type definitions for the RLM VS Code extension.
 *
 * All provider/backend configuration, bridge protocol messages, and
 * domain types live here.  Keep this file free of VS Code API imports
 * so it can be unit-tested without the extension host.
 */

// ── Provider configuration ──────────────────────────────────────────

/**
 * How the extension obtains LLM completions.
 *
 * - `"builtin"` → VS Code Language Model API (Copilot subscription)
 * - `"api_key"` → Direct API calls via rlm/clients/ (user provides key)
 */
export type LlmProvider = "builtin" | "api_key";

/**
 * Backend identifier matching Python's `ClientBackend` literal.
 * Only relevant when `LlmProvider === "api_key"`.
 */
export type ClientBackend =
  | "openai"
  | "portkey"
  | "openrouter"
  | "vercel"
  | "vllm"
  | "litellm"
  | "anthropic"
  | "azure_openai"
  | "gemini"
  | "vscode_lm";

/**
 * Full provider configuration sent to the Python backend on startup.
 */
export interface ProviderConfig {
  readonly provider: LlmProvider;
  readonly backend: ClientBackend;
  readonly model: string;
  readonly backendKwargs: Record<string, unknown>;
  readonly subBackend?: ClientBackend | undefined;
  readonly subModel?: string | undefined;
  readonly subBackendKwargs?: Record<string, unknown> | undefined;
  readonly maxIterations: number;
  readonly maxOutputChars: number;
}

// ── Bridge protocol messages (TS ↔ Python) ──────────────────────────

/** Messages the extension sends to the Python backend. */
export type OutboundMessage =
  | ConfigureMessage
  | CompletionMessage
  | ExecuteMessage
  | LlmResponseMessage
  | PingMessage
  | ShutdownMessage;

export interface ConfigureMessage {
  readonly type: "configure";
  readonly provider: LlmProvider;
  readonly backend: ClientBackend;
  readonly model: string;
  readonly backendKwargs: Record<string, unknown>;
  readonly subBackend?: ClientBackend | undefined;
  readonly subBackendKwargs?: Record<string, unknown> | undefined;
  readonly maxIterations: number;
  readonly maxOutputChars: number;
}

export interface CompletionMessage {
  readonly type: "completion";
  readonly nonce: string;
  readonly prompt: string;
  readonly context?: string | undefined;
  readonly rootPrompt?: string | undefined;
  readonly persistent?: boolean | undefined;
}

export interface ExecuteMessage {
  readonly type: "execute";
  readonly nonce: string;
  readonly code: string;
}

export interface LlmResponseMessage {
  readonly type: "llm_response";
  readonly nonce: string;
  readonly text?: string | undefined;
  readonly error?: string | undefined;
}

export interface PingMessage {
  readonly type: "ping";
  readonly nonce: string;
}

export interface ShutdownMessage {
  readonly type: "shutdown";
}

/** Messages the Python backend sends to the extension. */
export type InboundMessage =
  | ReadyMessage
  | ConfiguredMessage
  | ResultMessage
  | ExecResultMessage
  | LlmRequestMessage
  | ProgressMessage
  | ErrorMessage
  | PongMessage;

export interface ReadyMessage {
  readonly type: "ready";
}

export interface ConfiguredMessage {
  readonly type: "configured";
  readonly provider: string;
  readonly backend: string;
}

export interface ResultMessage {
  readonly type: "result";
  readonly nonce: string;
  readonly text: string;
}

export interface ExecResultMessage {
  readonly type: "exec_result";
  readonly nonce: string;
  readonly stdout: string;
  readonly stderr: string;
  readonly error: boolean;
}

export interface LlmRequestMessage {
  readonly type: "llm_request";
  readonly nonce: string;
  readonly prompt: string;
  readonly model: string | null;
}

export interface ProgressMessage {
  readonly type: "progress";
  readonly nonce: string;
  readonly iteration: number;
  readonly maxIterations: number;
  readonly text: string;
}

export interface ErrorMessage {
  readonly type: "error";
  readonly nonce: string | null;
  readonly error: string;
}

export interface PongMessage {
  readonly type: "pong";
  readonly nonce: string;
}

// ── Domain types ────────────────────────────────────────────────────

/** REPL execution result (matches Python's REPLResult). */
export interface REPLResult {
  readonly stdout: string;
  readonly stderr: string;
  readonly error: boolean;
}

/** Pending nonce callback. */
export interface PendingRequest<T = string> {
  resolve: (value: T) => void;
  reject: (reason: Error) => void;
}
