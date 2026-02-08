/**
 * RLM VS Code Extension — entry point.
 *
 * Activation:
 *  - VS Code: registers the @rlm chat participant (builtin + api_key modes)
 *  - Cursor:  logs a message; Cursor users interact via MCP gateway
 *
 * Commands:
 *  - rlm-chat.openChat        — focus the chat panel
 *  - rlm-chat.newSession      — clear REPL state and start fresh
 *  - rlm-chat.openLog         — open the JSONL debug log
 *  - rlm-chat.setApiKey       — securely store an API key
 *  - rlm-chat.clearApiKey     — remove stored API keys
 *  - rlm-chat.showProvider    — show current LLM provider info
 */

import * as path from "path";
import * as vscode from "vscode";
import { logger } from "./logger";
import { ConfigService } from "./configService";
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
  // ── Config service init ─────────────────────────────────────────
  const configService = ConfigService.instance;
  configService.init(context);
  const cfg = configService.get();

  // ── Logger init ─────────────────────────────────────────────────
  // Prefer workspace-local logs/ directory for discoverability; fall back
  // to global storage when no workspace folder is open.
  const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  const logDir = workspaceRoot ? path.join(workspaceRoot, "logs") : context.globalStorageUri.fsPath;
  logger.init(logDir, cfg.logLevel, cfg.logMaxSizeMB);
  logger.setTracingEnabled(cfg.tracingEnabled);

  const editor = detectEditor();
  logger.info("Extension", "Activating RLM extension", {
    editor,
    version: ((context.extension.packageJSON as Record<string, unknown> | undefined)?.["version"] as string | undefined) ?? "unknown",
  });

  // ── React to config changes ─────────────────────────────────────
  configService.onDidChange((newCfg) => {
    logger.setLevel(newCfg.logLevel);
    logger.setTracingEnabled(newCfg.tracingEnabled);
    logger.info("Extension", "Configuration changed");

    // Restart backend on provider/backend/model/python changes
    if (participant) {
      participant.restart().catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : String(err);
        logger.error("Extension", "Failed to restart backend after config change", { error: msg });
      });
    }
  });

  // ── API key manager ─────────────────────────────────────────────
  const apiKeys = new ApiKeyManager(context.secrets);

  // ── Chat participant (VS Code only) ────────────────────────────
  if (!isCursor()) {
    participant = new RLMChatParticipant(context, apiKeys, configService);
    context.subscriptions.push({ dispose: () => participant?.dispose() });
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
      const current = configService.get();
      vscode.window.showInformationMessage(
        `RLM Provider: ${current.provider} | Backend: ${current.backend} | Model: ${current.model}`,
      );
    }),
  );

  logger.info("Extension", "Activation complete");
}

export function deactivate(): void {
  participant?.dispose();
  participant = null;
  logger.dispose();
}
