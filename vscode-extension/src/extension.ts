/**
 * RLM VS Code Extension — entry point.
 *
 * Activation:
 *  • VS Code: registers the @rlm chat participant (builtin + api_key modes)
 *  • Cursor:  logs a message; Cursor users interact via MCP gateway
 *
 * Commands:
 *  • rlm-chat.openChat        — focus the chat panel
 *  • rlm-chat.newSession      — clear REPL state and start fresh
 *  • rlm-chat.openLog         — open the JSONL debug log
 *  • rlm-chat.setApiKey       — securely store an API key
 *  • rlm-chat.clearApiKey     — remove stored API keys
 *  • rlm-chat.showProvider    — show current LLM provider info
 */

import * as vscode from "vscode";
import { logger } from "./logger";
import { RLMChatParticipant } from "./rlmParticipant";
import { ApiKeyManager } from "./apiKeyManager";
import { detectEditor, isCursor } from "./platform";
import type { ClientBackend } from "./types";

let participant: RLMChatParticipant | null = null;

const KNOWN_BACKENDS: readonly ClientBackend[] = [
  "openai",
  "portkey",
  "openrouter",
  "vercel",
  "vllm",
  "litellm",
  "anthropic",
  "azure_openai",
  "gemini",
];

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  // ── Logger init ─────────────────────────────────────────────────
  const settings = vscode.workspace.getConfiguration("rlm");
  const logLevel = settings.get<string>("logLevel", "debug");
  const logMaxMb = settings.get<number>("logMaxSizeMB", 5);
  logger.init(context.globalStorageUri.fsPath, logLevel, logMaxMb);

  const editor = detectEditor();
  logger.info("Extension", "Activating RLM extension", {
    editor,
    version: context.extension.packageJSON?.version ?? "unknown",
  });

  // ── API key manager ─────────────────────────────────────────────
  const apiKeys = new ApiKeyManager(context.secrets);

  // ── Chat participant (VS Code only) ────────────────────────────
  if (!isCursor()) {
    participant = new RLMChatParticipant(context);
    try {
      await participant.register();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      logger.error("Extension", "Failed to register participant", { error: msg });
    }
  } else {
    logger.info("Extension", "Running in Cursor — MCP gateway is the integration path");
    vscode.window.showInformationMessage(
      "RLM: Cursor detected. Use the MCP gateway (@rlm tools) for RLM integration.",
    );
  }

  // ── Commands ────────────────────────────────────────────────────

  context.subscriptions.push(
    vscode.commands.registerCommand("rlm-chat.openChat", () => {
      vscode.commands.executeCommand("workbench.action.chat.open");
    }),

    vscode.commands.registerCommand("rlm-chat.newSession", async () => {
      if (participant) {
        await participant.restart();
        vscode.window.showInformationMessage("RLM session restarted.");
      }
    }),

    vscode.commands.registerCommand("rlm-chat.openLog", () => {
      const logPath = logger.getLogPath();
      if (logPath) {
        vscode.window.showTextDocument(vscode.Uri.file(logPath));
      }
    }),

    vscode.commands.registerCommand("rlm-chat.setApiKey", async () => {
      const backend = await vscode.window.showQuickPick(
        KNOWN_BACKENDS.map((b) => b),
        { placeHolder: "Select the backend to store an API key for" },
      );
      if (backend) {
        await apiKeys.promptAndStore(backend);
        // Restart backend to pick up new key
        if (participant) {
          await participant.restart();
        }
      }
    }),

    vscode.commands.registerCommand("rlm-chat.clearApiKey", async () => {
      await apiKeys.clearAll(KNOWN_BACKENDS);
      if (participant) {
        await participant.restart();
      }
    }),

    vscode.commands.registerCommand("rlm-chat.showProvider", () => {
      const provider = settings.get<string>("llmProvider", "builtin");
      const backend = settings.get<string>("backend", "openai");
      const model = settings.get<string>("model", "gpt-4o");
      vscode.window.showInformationMessage(
        `RLM Provider: ${provider} | Backend: ${backend} | Model: ${model}`,
      );
    }),
  );

  // ── Settings change listener ────────────────────────────────────

  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration(async (e) => {
      if (e.affectsConfiguration("rlm.logLevel")) {
        const newLevel = vscode.workspace.getConfiguration("rlm").get<string>("logLevel", "debug");
        logger.setLevel(newLevel);
      }

      // Restart backend on provider/backend/model changes
      if (
        e.affectsConfiguration("rlm.llmProvider") ||
        e.affectsConfiguration("rlm.backend") ||
        e.affectsConfiguration("rlm.model") ||
        e.affectsConfiguration("rlm.baseUrl") ||
        e.affectsConfiguration("rlm.maxIterations") ||
        e.affectsConfiguration("rlm.pythonPath")
      ) {
        logger.info("Extension", "Configuration changed, restarting backend");
        if (participant) {
          await participant.restart();
        }
      }
    }),
  );

  logger.info("Extension", "Activation complete");
}

export function deactivate(): void {
  participant?.dispose();
  participant = null;
  logger.dispose();
}
