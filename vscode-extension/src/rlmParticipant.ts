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
import type { OrchestrationResult } from "./orchestrator";
import { ApiKeyManager } from "./apiKeyManager";
import { ConfigService } from "./configService";
import { logger } from "./logger";
import { hasChatApi, hasLanguageModelApi } from "./platform";
import type { ProviderConfig } from "./types";

// ── Constants ───────────────────────────────────────────────────────

const PARTICIPANT_ID = "rlm-chat.rlm";
const SUB_LLM_TIMEOUT_MS = 300_000;

interface ParticipantResultMeta {
  readonly command: string;
}

interface SubLlmResponse {
  readonly text: string;
  readonly promptTokens: number;
  readonly completionTokens: number;
}

/**
 * Signature of the `runWithTools` function exported by `@vscode/chat-extension-utils`.
 * Dynamically imported — not a compile-time dependency.
 */
type RunWithToolsFn = (
  request: vscode.ChatRequest,
  chatContext: vscode.ChatContext,
  response: vscode.ChatResponseStream,
  options: {
    model: vscode.LanguageModelChat;
    tools?: readonly vscode.LanguageModelToolInformation[];
    toolInvocationToken?: vscode.ChatParticipantToolToken;
  },
  token: vscode.CancellationToken,
) => Promise<vscode.ChatResult>;

// ── RLM Chat Participant ────────────────────────────────────────────

export class RLMChatParticipant {
  private bridge: BackendBridge | null = null;
  private orchestrator: Orchestrator | null = null;
  private disposables: vscode.Disposable[] = [];
  private readonly apiKeys: ApiKeyManager;
  private readonly configService: ConfigService;
  private chatExtensionUtilsStatus: "unchecked" | "available" | "missing" = "unchecked";
  private runWithToolsFn: RunWithToolsFn | null = null;

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

    participant.followupProvider = {
      provideFollowups: (result) => {
        const metadata = result.metadata as ParticipantResultMeta | undefined;
        return this.buildFollowups(metadata?.command ?? "default");
      },
    };

    participant.iconPath = vscode.Uri.joinPath(this.context.extensionUri, "icon.png");

    this.disposables.push(participant);
    logger.info("RLMParticipant", "Chat participant registered");

    await this.evaluateChatExtensionUtils();

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

  /**
   * Run a completion from a language model tool invocation.
   * Uses the same orchestrator/backend path as chat requests.
   */
  async runToolCompletion(prompt: string, context?: string): Promise<string> {
    const { orchestrator } = await this.ensureBackend();
    const cfg = this.configService.get();
    const result = await orchestrator.run(
      {
        prompt,
        context,
        rootPrompt: prompt,
        persistent: false,
      },
      cfg,
    );
    return result.text;
  }

  /**
   * Execute Python code from a language model tool invocation.
   */
  async runToolExecute(code: string): Promise<{ stdout: string; stderr: string; error: boolean }> {
    const { bridge } = await this.ensureBackend();
    return bridge.execute(code);
  }

  // ── Core request handler ──────────────────────────────────────────

  private async handleRequest(
    request: vscode.ChatRequest,
    chatContext: vscode.ChatContext,
    stream: vscode.ChatResponseStream,
    token: vscode.CancellationToken,
  ): Promise<vscode.ChatResult> {
    const startTime = Date.now();
    logger.info("RLMParticipant", "Request received", {
      prompt: request.prompt.slice(0, 200),
      command: request.command ?? "(none)",
      references: request.references.length,
    });

    try {
      // Agent-mode: when no specific command is given and @vscode/chat-extension-utils
      // is available, let VS Code's LM orchestrate tool calls via runWithTools().
      // Commands (/analyze, /summarize, /search) always use the direct RLM flow.
      if (!request.command && this.runWithToolsFn) {
        return await this.handleRequestWithTools(request, chatContext, stream, token);
      }

      const result = await this.runDirectCompletion(request, chatContext, stream, token);

      logger.info("RLMParticipant", "Request completed", {
        durationMs: Date.now() - startTime,
        resultLength: result.text.length,
        spanId: result.spanId,
        iterationsUsed: result.iterationsUsed,
      });

      return {
        metadata: {
          command: request.command ?? "default",
        },
      };
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      logger.error("RLMParticipant", "Request failed", { error: message });

      if (token.isCancellationRequested) {
        stream.markdown("*Request cancelled.*");
        return {
          metadata: {
            command: request.command ?? "default",
          },
        };
      }

      stream.markdown(`**Error:** ${message}`);
      return {
        metadata: {
          command: request.command ?? "default",
        },
      };
    }
  }

  /** Run direct RLM completion via orchestrator and stream results. */
  private async runDirectCompletion(
    request: vscode.ChatRequest,
    chatContext: vscode.ChatContext,
    stream: vscode.ChatResponseStream,
    token: vscode.CancellationToken,
  ): Promise<OrchestrationResult> {
    const { bridge, orchestrator } = await this.ensureBackend();
    const cfg = this.configService.get();

    // Resolve references (files, selections, etc.)
    const resolvedContext = await this.resolveReferences(request);
    const historyContext = this.buildHistoryContext(chatContext);
    const mergedContext = this.mergeContexts(historyContext, resolvedContext);

    // Set up LLM handler for builtin mode
    if (cfg.provider === "builtin" && hasLanguageModelApi()) {
      bridge.setLlmHandler(async (prompt: string, model: string | null) => {
        return this.handleSubLlmRequest(prompt, model, token);
      });
    }

    // Cancel in-flight work if the user cancels the chat request
    const cancelListener = token.onCancellationRequested(() => {
      bridge.cancelAll();
    });

    stream.progress("Starting RLM reasoning...");

    const showDetails = cfg.showIterationDetails;

    let result;
    try {
      result = await orchestrator.run(
        {
          prompt: request.prompt,
          context: mergedContext ?? undefined,
          rootPrompt: request.prompt,
          persistent: false,
        },
        cfg,
        showDetails
          ? (iteration, maxIterations, text) => {
              stream.progress(
                `Iteration ${iteration}/${maxIterations}${text ? `: ${text}` : ""}`,
              );
            }
          : undefined,
        showDetails
          ? (text) => {
              stream.markdown(text);
            }
          : undefined,
      );
    } finally {
      cancelListener.dispose();
    }

    // When iteration details are hidden, stream only the final answer.
    if (!showDetails) {
      stream.markdown(result.text);
    }

    return result;
  }

  /**
   * Agent-mode handler: delegates tool orchestration to @vscode/chat-extension-utils.
   * VS Code's LM decides when to invoke rlm_analyze / rlm_execute.
   */
  private async handleRequestWithTools(
    request: vscode.ChatRequest,
    chatContext: vscode.ChatContext,
    stream: vscode.ChatResponseStream,
    token: vscode.CancellationToken,
  ): Promise<vscode.ChatResult> {
    const fn = this.runWithToolsFn;
    if (!fn) {
      throw new Error("runWithTools not available");
    }

    const rlmTools = vscode.lm.tools.filter((t) => t.name.startsWith("rlm_"));

    logger.info("RLMParticipant", "Using agent-mode tool orchestration", {
      model: request.model.name,
      toolCount: rlmTools.length,
    });

    return fn(request, chatContext, stream, {
      model: request.model,
      tools: rlmTools,
      toolInvocationToken: request.toolInvocationToken,
    }, token);
  }

  private buildFollowups(command: string): vscode.ChatFollowup[] {
    if (command === "summarize") {
      return [
        { prompt: "Summarize this at one level deeper", label: "Summarize deeper" },
        { prompt: "Extract the key risks from this summary", label: "Extract risks" },
      ];
    }

    if (command === "search") {
      return [
        { prompt: "Search for related references and evidence", label: "Find references" },
        { prompt: "Narrow the search to the most relevant files", label: "Narrow search" },
      ];
    }

    return [
      { prompt: "Analyze this in more detail", label: "Analyze deeper" },
      { prompt: "Show the most relevant intermediate reasoning steps", label: "Show reasoning" },
      { prompt: "Suggest concrete next actions based on this result", label: "Next actions" },
    ];
  }

  // ── Sub-LLM handler (builtin mode) ───────────────────────────────

  private async handleSubLlmRequest(
    prompt: string,
    requestedModel: string | null,
    token: vscode.CancellationToken,
  ): Promise<SubLlmResponse> {
    logger.debug("RLMParticipant", "Sub-LLM request", {
      promptLength: prompt.length,
    });

    if (token.isCancellationRequested) {
      return {
        text: "[ERROR: Operation cancelled by user]",
        promptTokens: this.estimateTokens(prompt),
        completionTokens: 0,
      };
    }

    const requestedModelValue = requestedModel?.trim() ?? "";
    const normalizedRequestedModel = requestedModelValue.toLowerCase();

    if (normalizedRequestedModel) {
      const byId = await vscode.lm.selectChatModels({ id: requestedModelValue });
      if (byId.length > 0) {
        return this.callModel(byId[0], prompt, token);
      }

      const byFamily = await vscode.lm.selectChatModels({ family: requestedModelValue });
      if (byFamily.length > 0) {
        return this.callModel(byFamily[0], prompt, token);
      }

      const allModels = await vscode.lm.selectChatModels();
      if (allModels.length === 0) {
        throw new Error("No language models available. Check your Copilot subscription.");
      }

      const matchedModel = allModels.find((candidate) => {
        const identifiers = [candidate.id, candidate.name, candidate.family]
          .map((value) => value.toLowerCase())
          .filter((value) => value.length > 0);
        return identifiers.some(
          (identifier) =>
            identifier === normalizedRequestedModel || identifier.includes(normalizedRequestedModel),
        );
      });

      if (matchedModel) {
        return this.callModel(matchedModel, prompt, token);
      }

      logger.warn("RLMParticipant", "Requested sub-model unavailable; falling back", {
        requestedModel,
      });
      return this.callModel(allModels[0], prompt, token);
    }

    const preferredModels = await vscode.lm.selectChatModels({ family: "gpt-4o" });
    if (preferredModels.length > 0) {
      return this.callModel(preferredModels[0], prompt, token);
    }

    const allModels = await vscode.lm.selectChatModels();
    if (allModels.length === 0) {
      throw new Error("No language models available. Check your Copilot subscription.");
    }

    return this.callModel(allModels[0], prompt, token);
  }

  private async callModel(
    model: vscode.LanguageModelChat,
    prompt: string,
    token: vscode.CancellationToken,
  ): Promise<SubLlmResponse> {
    const messages = [vscode.LanguageModelChatMessage.User(prompt)];

    let timer: ReturnType<typeof setTimeout> | undefined;
    const modelCall = (async () => {
      const response = await model.sendRequest(messages, {}, token);
      const parts: string[] = [];
      for await (const fragment of response.text) {
        parts.push(fragment);
      }
      const text = parts.join("");
      return {
        text,
        promptTokens: this.estimateTokens(prompt),
        completionTokens: this.estimateTokens(text),
      };
    })();

    const timeout = new Promise<never>((_, reject) => {
      timer = setTimeout(
        () => reject(new Error(`Sub-LLM query timed out after ${SUB_LLM_TIMEOUT_MS / 1000}s`)),
        SUB_LLM_TIMEOUT_MS,
      );
    });

    try {
      return await Promise.race([modelCall, timeout]);
    } catch (error: unknown) {
      if (error instanceof vscode.LanguageModelError) {
        const code = error.code;
        const msg = error.message;
        if (code === "NoPermissions" || msg.includes("quota") || msg.includes("rate")) {
          throw new Error(`Model quota/rate limit exceeded. (${msg})`, { cause: error });
        }
        if (code === "Blocked") {
          throw new Error(`Request blocked by content filter. (${msg})`, { cause: error });
        }
        if (code === "NotFound") {
          throw new Error(`Model not available. Check Copilot subscription. (${msg})`, {
            cause: error,
          });
        }
        throw new Error(`Language Model error [${code}]: ${msg}`, { cause: error });
      }
      throw error;
    } finally {
      clearTimeout(timer);
    }
  }

  private estimateTokens(text: string): number {
    const normalized = text.trim();
    if (normalized.length === 0) {
      return 0;
    }
    return Math.max(1, Math.ceil(normalized.length / 4));
  }

  private async evaluateChatExtensionUtils(): Promise<void> {
    if (this.chatExtensionUtilsStatus !== "unchecked") {
      return;
    }

    try {
      const moduleName = "@vscode/chat-extension-utils";
      const moduleValue = (await import(moduleName)) as Record<string, unknown>;
      if (typeof moduleValue["runWithTools"] === "function") {
        this.runWithToolsFn = moduleValue["runWithTools"] as RunWithToolsFn;
        this.chatExtensionUtilsStatus = "available";
        logger.info("RLMParticipant", "@vscode/chat-extension-utils available — agent-mode tool orchestration enabled");
        return;
      }
    } catch {
      // optional dependency; ignore
    }

    this.chatExtensionUtilsStatus = "missing";
    logger.debug("RLMParticipant", "@vscode/chat-extension-utils not installed; using native participant path");
  }

  // ── Reference resolution ──────────────────────────────────────────

  private async resolveReferences(request: vscode.ChatRequest): Promise<string | null> {
    if (request.references.length === 0) {
      return null;
    }

    const parts: string[] = [];

    for (const ref of request.references) {
      const resolved = await this.resolveOneReference(ref);
      if (resolved) {
        parts.push(resolved);
      }
    }

    return parts.length > 0 ? parts.join("\n\n") : null;
  }

  private buildHistoryContext(chatContext: vscode.ChatContext): string | null {
    const prompts: string[] = [];
    for (const turn of chatContext.history) {
      if (turn instanceof vscode.ChatRequestTurn) {
        const prompt = turn.prompt.trim();
        if (prompt) {
          prompts.push(prompt);
        }
      }
    }

    if (prompts.length === 0) {
      return null;
    }

    const lastPrompts = prompts.slice(-8);
    const lines = lastPrompts.map((prompt, index) => `${index + 1}. ${prompt}`);
    return `--- Prior chat prompts ---\n${lines.join("\n")}`;
  }

  private mergeContexts(historyContext: string | null, referenceContext: string | null): string | null {
    if (historyContext && referenceContext) {
      return `${historyContext}\n\n${referenceContext}`;
    }
    if (historyContext) {
      return historyContext;
    }
    if (referenceContext) {
      return referenceContext;
    }
    return null;
  }

  /** Resolve a single chat reference to text, or return null on failure. */
  private async resolveOneReference(ref: vscode.ChatPromptReference): Promise<string | null> {
    try {
      const value = ref.value;

      if (value instanceof vscode.Uri) {
        const doc = await vscode.workspace.openTextDocument(value);
        return `--- File: ${value.fsPath} ---\n${doc.getText()}`;
      }
      if (value instanceof vscode.Location) {
        const doc = await vscode.workspace.openTextDocument(value.uri);
        return `--- Selection from ${value.uri.fsPath} ---\n${doc.getText(value.range)}`;
      }
      if (typeof value === "string") {
        return value;
      }
      // Object with a .uri property (e.g. workspace folder)
      if (typeof value === "object" && value !== null && "uri" in value) {
        const uri = (value as { uri: vscode.Uri }).uri;
        if (uri instanceof vscode.Uri) {
          const doc = await vscode.workspace.openTextDocument(uri);
          return `--- File: ${uri.fsPath} ---\n${doc.getText()}`;
        }
      }
      return null;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      logger.warn("RLMParticipant", "Failed to resolve reference", { error: msg });
      return null;
    }
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
      subBackendKwargs,
      maxIterations: cfg.maxIterations,
      maxOutputChars: cfg.maxOutputChars,
      environment: cfg.environment,
    };
  }
}
