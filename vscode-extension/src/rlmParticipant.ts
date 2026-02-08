/**
 * RLM Chat Participant — thin bridge between VS Code's Chat API and
 * the Python RLM backend.
 *
 * This module:
 *  1. Registers the `@rlm` chat participant (VS Code only — skipped on Cursor)
 *  2. Resolves file/workspace references from the chat context
 *  3. Delegates the full completion to BackendBridge (Python runs the RLM loop)
 *  4. In builtin mode, relays sub-LLM requests from Python → vscode.lm → Python
 *  5. Streams progress and the final answer back to the chat UI
 *
 * The RLM iteration loop, prompt construction, code parsing, and FINAL detection
 * all happen in Python (rlm_backend.py + rlm/core/rlm.py). This file does NOT
 * duplicate any of that logic.
 */

import * as vscode from "vscode";
import { BackendBridge } from "./backendBridge";
import { ApiKeyManager } from "./apiKeyManager";
import { logger } from "./logger";
import { hasChatApi, hasLanguageModelApi } from "./platform";
import type { LlmProvider, ProviderConfig, ClientBackend } from "./types";

// ── Constants ───────────────────────────────────────────────────────

const PARTICIPANT_ID = "rlm-chat.rlm";
const SUB_LLM_TIMEOUT_MS = 300_000;

// ── RLM Chat Participant ────────────────────────────────────────────

export class RLMChatParticipant {
  private bridge: BackendBridge | null = null;
  private disposables: vscode.Disposable[] = [];
  private readonly apiKeys: ApiKeyManager;

  constructor(
    private readonly context: vscode.ExtensionContext,
    apiKeys: ApiKeyManager,
  ) {
    this.apiKeys = apiKeys;
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
      (request, context, stream, token) => this.handleRequest(request, context, stream, token),
    );

    participant.iconPath = vscode.Uri.joinPath(this.context.extensionUri, "icon.png");

    this.disposables.push(participant);
    logger.info("RLMParticipant", "Chat participant registered");

    // Start backend eagerly
    await this.ensureBackend();
  }

  /** Tear down the backend and participant. */
  dispose(): void {
    this.bridge?.dispose();
    this.bridge = null;
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
      // Ensure backend is running
      const bridge = await this.ensureBackend();

      // Resolve references (files, selections, etc.)
      const resolvedContext = await this.resolveReferences(request);

      // Set up LLM handler for builtin mode
      const config = await this.getConfig();
      if (config.provider === "builtin" && hasLanguageModelApi()) {
        bridge.setLlmHandler(async (prompt: string, _model: string | null) => {
          return this.handleSubLlmRequest(prompt, token);
        });
      }

      // Set up progress handler
      bridge.setProgressHandler((_nonce, iteration, maxIterations, text) => {
        stream.progress(`Iteration ${iteration}/${maxIterations}${text ? `: ${text}` : ""}`);
      });

      // Cancel in-flight work if the user cancels the chat request
      const cancelListener = token.onCancellationRequested(() => {
        bridge.cancelAll();
      });

      // Run completion
      stream.progress("Starting RLM reasoning...");

      let result: string;
      try {
        result = await bridge.completion(
          request.prompt,
          resolvedContext || undefined,
          request.prompt,
          /* persistent */ false,
        );
      } finally {
        cancelListener.dispose();
      }

      // Stream the result
      stream.markdown(result);

      logger.info("RLMParticipant", "Request completed", {
        durationMs: Date.now() - startTime,
        resultLength: result.length,
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

  /**
   * Handle a sub-LLM request from Python by calling the VS Code Language Model API.
   * This is only active in "builtin" mode when vscode.lm is available.
   */
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

    // Select a model
    const models = await vscode.lm.selectChatModels({ family: "gpt-4o" });
    const model = models[0];
    if (!model) {
      // Fallback: try any available model
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

  /**
   * Resolve all chat references (files, selections, etc.) into a single
   * context string that gets loaded into the Python REPL as the `context` variable.
   */
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
          // ChatReferenceBinaryData or similar
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

  /**
   * Ensure the backend bridge is running with the current configuration.
   * Creates it on first call, restarts if config has changed.
   */
  private async ensureBackend(): Promise<BackendBridge> {
    if (this.bridge?.isAlive()) {
      return this.bridge;
    }

    const config = await this.getConfig();
    const pythonPath = vscode.workspace.getConfiguration("rlm").get<string>("pythonPath", "python3");

    this.bridge = new BackendBridge(pythonPath);
    await this.bridge.start(config);

    return this.bridge;
  }

  /**
   * Build the ProviderConfig from VS Code settings + stored API keys.
   */
  private async getConfig(): Promise<ProviderConfig> {
    const settings = vscode.workspace.getConfiguration("rlm");
    const provider = settings.get<LlmProvider>("llmProvider", "builtin");
    const backend = settings.get<ClientBackend>("backend", "openai");
    const model = settings.get<string>("model", "gpt-4o");
    const baseUrl = settings.get<string>("baseUrl", "");
    const maxIterations = settings.get<number>("maxIterations", 30);
    const maxOutputChars = settings.get<number>("maxOutputChars", 20000);
    const rawSubBackend = settings.get<string>("subBackend", "");
    const rawSubModel = settings.get<string>("subModel", "");

    // Normalise empty-string settings to undefined
    const subBackend: ClientBackend | undefined = rawSubBackend ? rawSubBackend as ClientBackend : undefined;
    const subModel: string | undefined = rawSubModel || undefined;

    // Build backend kwargs
    const backendKwargs: Record<string, unknown> = {
      model_name: model,
    };
    if (baseUrl) {
      backendKwargs["base_url"] = baseUrl;
    }

    // Inject API key from SecretStorage when in api_key mode
    if (provider === "api_key") {
      const apiKey = await this.apiKeys.get(backend);
      if (apiKey) {
        backendKwargs["api_key"] = apiKey;
      }
    }

    // Sub-backend kwargs
    let subBackendKwargs: Record<string, unknown> | undefined;
    if (subBackend && subModel) {
      subBackendKwargs = { model_name: subModel };
      // Inject sub-backend API key too
      const subApiKey = await this.apiKeys.get(subBackend);
      if (subApiKey) {
        subBackendKwargs["api_key"] = subApiKey;
      }
    }

    return {
      provider,
      backend: provider === "builtin" ? "vscode_lm" : backend,
      model,
      backendKwargs,
      subBackend,
      subModel,
      subBackendKwargs,
      maxIterations,
      maxOutputChars,
    };
  }
}
