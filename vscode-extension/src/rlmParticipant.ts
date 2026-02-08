/**
 * RLM Chat Participant — thin bridge between VS Code's Chat API and
 * the Python RLM backend, routed through the Orchestrator.
 *
 * This module:
 *  1. Registers the `@rlm` chat participant (VS Code only — skipped on Cursor)
 *  2. Resolves file/workspace references from the chat context
 *  3. Delegates to the Orchestrator, which enforces budgets and emits spans
 *  4. In builtin mode, relays sub-LLM requests from Python → vscode.lm → Python
 *  5. Streams progress and the final answer back to the chat UI
 *
 * The RLM iteration loop, prompt construction, code parsing, and FINAL detection
 * all happen in Python (rlm_backend.py + rlm/core/rlm.py). This file does NOT
 * duplicate any of that logic.
 */

import * as vscode from "vscode";
import { BackendBridge } from "./backendBridge";
import { Orchestrator } from "./orchestrator";
import { ApiKeyManager } from "./apiKeyManager";
import { ConfigService } from "./configService";
import { logger } from "./logger";
import { hasChatApi, hasLanguageModelApi } from "./platform";
import type { ProviderConfig } from "./types";

// ── Constants ───────────────────────────────────────────────────────

const PARTICIPANT_ID = "rlm-chat.rlm";
const SUB_LLM_TIMEOUT_MS = 300_000;

// ── RLM Chat Participant ────────────────────────────────────────────

export class RLMChatParticipant {
  private bridge: BackendBridge | null = null;
  private orchestrator: Orchestrator | null = null;
  private disposables: vscode.Disposable[] = [];
  private readonly apiKeys: ApiKeyManager;
  private readonly configService: ConfigService;

  constructor(
    private readonly context: vscode.ExtensionContext,
    apiKeys: ApiKeyManager,
    configService: ConfigService,
  ) {
    this.apiKeys = apiKeys;
    this.configService = configService;
  }

  /**
   * Register the chat participant and start the backend.
   * On Cursor (no Chat API), this is a no-op — Cursor uses MCP instead.
   */
  async register(): Promise<void> {
    if (!hasChatApi()) {
      logger.info("RLMParticipant", "Chat API not available (Cursor?) — skipping registration");
      return;
    }

    const participant = vscode.chat.createChatParticipant(
      PARTICIPANT_ID,
      (request, chatContext, stream, token) =>
        this.handleRequest(request, chatContext, stream, token),
    );

    participant.iconPath = vscode.Uri.joinPath(this.context.extensionUri, "icon.png");

    this.disposables.push(participant);
    logger.info("RLMParticipant", "Chat participant registered");

    await this.ensureBackend();
  }

  /** Tear down the backend and participant. */
  dispose(): void {
    this.bridge?.dispose();
    this.bridge = null;
    this.orchestrator = null;
    for (const d of this.disposables) {
      d.dispose();
    }
    this.disposables = [];
  }

  /** Restart the backend (e.g. after config change). */
  async restart(): Promise<void> {
    logger.info("RLMParticipant", "Restarting backend");
    this.bridge?.dispose();
    this.bridge = null;
    this.orchestrator = null;
    await this.ensureBackend();
  }

  // ── Core request handler ──────────────────────────────────────────

  private async handleRequest(
    request: vscode.ChatRequest,
    _chatContext: vscode.ChatContext,
    stream: vscode.ChatResponseStream,
    token: vscode.CancellationToken,
  ): Promise<vscode.ChatResult> {
    const startTime = Date.now();
    logger.info("RLMParticipant", "Request received", {
      prompt: request.prompt.slice(0, 200),
      command: request.command ?? "(none)",
      references: request.references?.length ?? 0,
    });

    try {
      const { bridge, orchestrator } = await this.ensureBackend();
      const cfg = this.configService.get();

      // Resolve references (files, selections, etc.)
      const resolvedContext = await this.resolveReferences(request);

      // Set up LLM handler for builtin mode
      if (cfg.provider === "builtin" && hasLanguageModelApi()) {
        bridge.setLlmHandler(async (prompt: string, _model: string | null) => {
          return this.handleSubLlmRequest(prompt, token);
        });
      }

      // Cancel in-flight work if the user cancels the chat request
      const cancelListener = token.onCancellationRequested(() => {
        bridge.cancelAll();
      });

      stream.progress("Starting RLM reasoning...");

      let result;
      try {
        result = await orchestrator.run(
          {
            prompt: request.prompt,
            context: resolvedContext ?? undefined,
            rootPrompt: request.prompt,
            persistent: false,
          },
          cfg,
          (iteration, maxIterations, text) => {
            stream.progress(`Iteration ${iteration}/${maxIterations}${text ? `: ${text}` : ""}`);
          },
        );
      } finally {
        cancelListener.dispose();
      }

      stream.markdown(result.text);

      logger.info("RLMParticipant", "Request completed", {
        durationMs: Date.now() - startTime,
        resultLength: result.text.length,
        spanId: result.spanId,
        iterationsUsed: result.iterationsUsed,
      });

      return {};
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      logger.error("RLMParticipant", "Request failed", { error: message });

      if (token.isCancellationRequested) {
        stream.markdown("*Request cancelled.*");
        return {};
      }

      stream.markdown(`**Error:** ${message}`);
      return {};
    }
  }

  // ── Sub-LLM handler (builtin mode) ───────────────────────────────

  private async handleSubLlmRequest(
    prompt: string,
    token: vscode.CancellationToken,
  ): Promise<string> {
    logger.debug("RLMParticipant", "Sub-LLM request", {
      promptLength: prompt.length,
    });

    if (token.isCancellationRequested) {
      return "[ERROR: Operation cancelled by user]";
    }

    const models = await vscode.lm.selectChatModels({ family: "gpt-4o" });
    const model = models[0];
    if (!model) {
      const allModels = await vscode.lm.selectChatModels();
      if (allModels.length === 0) {
        throw new Error("No language models available. Check your Copilot subscription.");
      }
      return this.callModel(allModels[0], prompt, token);
    }

    return this.callModel(model, prompt, token);
  }

  private async callModel(
    model: vscode.LanguageModelChat,
    prompt: string,
    token: vscode.CancellationToken,
  ): Promise<string> {
    const messages = [vscode.LanguageModelChatMessage.User(prompt)];

    let timer: ReturnType<typeof setTimeout> | undefined;
    const modelCall = (async () => {
      const response = await model.sendRequest(messages, {}, token);
      const parts: string[] = [];
      for await (const fragment of response.text) {
        parts.push(fragment);
      }
      return parts.join("");
    })();

    const timeout = new Promise<never>((_, reject) => {
      timer = setTimeout(
        () => reject(new Error(`Sub-LLM query timed out after ${SUB_LLM_TIMEOUT_MS / 1000}s`)),
        SUB_LLM_TIMEOUT_MS,
      );
    });

    try {
      return await Promise.race([modelCall, timeout]);
    } catch (err: unknown) {
      if (err instanceof vscode.LanguageModelError) {
        const code = err.code;
        const msg = err.message;
        if (code === "NoPermissions" || msg.includes("quota") || msg.includes("rate")) {
          throw new Error(`Model quota/rate limit exceeded. (${msg})`);
        }
        if (code === "Blocked") {
          throw new Error(`Request blocked by content filter. (${msg})`);
        }
        if (code === "NotFound") {
          throw new Error(`Model not available. Check Copilot subscription. (${msg})`);
        }
        throw new Error(`Language Model error [${code}]: ${msg}`);
      }
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }

  // ── Reference resolution ──────────────────────────────────────────

  private async resolveReferences(request: vscode.ChatRequest): Promise<string | null> {
    if (!request.references || request.references.length === 0) {
      return null;
    }

    const parts: string[] = [];

    for (const ref of request.references) {
      try {
        const value = ref.value;

        if (value instanceof vscode.Uri) {
          const doc = await vscode.workspace.openTextDocument(value);
          parts.push(`--- File: ${value.fsPath} ---\n${doc.getText()}`);
        } else if (value instanceof vscode.Location) {
          const doc = await vscode.workspace.openTextDocument(value.uri);
          const text = doc.getText(value.range);
          parts.push(`--- Selection from ${value.uri.fsPath} ---\n${text}`);
        } else if (typeof value === "object" && value !== null && "uri" in value) {
          const uri = (value as { uri: vscode.Uri }).uri;
          if (uri instanceof vscode.Uri) {
            const doc = await vscode.workspace.openTextDocument(uri);
            parts.push(`--- File: ${uri.fsPath} ---\n${doc.getText()}`);
          }
        } else if (typeof value === "string") {
          parts.push(value);
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        logger.warn("RLMParticipant", "Failed to resolve reference", { error: msg });
      }
    }

    return parts.length > 0 ? parts.join("\n\n") : null;
  }

  // ── Backend management ────────────────────────────────────────────

  private async ensureBackend(): Promise<{
    bridge: BackendBridge;
    orchestrator: Orchestrator;
  }> {
    if (this.bridge?.isAlive() && this.orchestrator) {
      return { bridge: this.bridge, orchestrator: this.orchestrator };
    }

    const config = await this.getProviderConfig();
    const cfg = this.configService.get();

    this.bridge = new BackendBridge(cfg.pythonPath);
    await this.bridge.start(config);

    this.orchestrator = new Orchestrator(this.bridge);

    return { bridge: this.bridge, orchestrator: this.orchestrator };
  }

  private async getProviderConfig(): Promise<ProviderConfig> {
    const cfg = this.configService.get();

    const backendKwargs: Record<string, unknown> = {
      model_name: cfg.model,
    };
    if (cfg.baseUrl) {
      backendKwargs["base_url"] = cfg.baseUrl;
    }

    if (cfg.provider === "api_key") {
      const apiKey = await this.apiKeys.get(cfg.backend);
      if (apiKey) {
        backendKwargs["api_key"] = apiKey;
      }
    }

    let subBackendKwargs: Record<string, unknown> | undefined;
    if (cfg.subBackend && cfg.subModel) {
      subBackendKwargs = { model_name: cfg.subModel };
      const subApiKey = await this.apiKeys.get(cfg.subBackend);
      if (subApiKey) {
        subBackendKwargs["api_key"] = subApiKey;
      }
    }

    return {
      provider: cfg.provider,
      backend: cfg.provider === "builtin" ? "vscode_lm" : cfg.backend,
      model: cfg.model,
      backendKwargs,
      subBackend: cfg.subBackend,
      subModel: cfg.subModel,
      subBackendKwargs,
      maxIterations: cfg.maxIterations,
      maxOutputChars: cfg.maxOutputChars,
    };
  }
}
