/**
 * BackendBridge — spawns and manages the Python rlm_backend.py process.
 *
 * This is the TypeScript ↔ Python communication layer. It:
 *  1. Spawns `python rlm_backend.py` as a child process
 *  2. Sends JSON-over-newline commands (configure, completion, execute)
 *  3. Routes inbound messages (result, llm_request, progress, error)
 *  4. In "builtin" mode, relays llm_request → vscode.lm → llm_response
 *
 * Replaces the old replBridge.ts — this talks to the full RLM backend
 * instead of a bare REPL subprocess.
 */

import * as cp from "child_process";
import * as crypto from "crypto";
import * as path from "path";
import { logger } from "./logger";
import type {
  ProviderConfig,
  InboundMessage,
  OutboundMessage,
  CompletionMessage,
  LlmResponseMessage,
  PendingRequest,
  REPLResult,
} from "./types";

interface LlmHandlerResult {
  readonly text: string;
  readonly promptTokens?: number;
  readonly completionTokens?: number;
}

// ── Constants ───────────────────────────────────────────────────────

const READY_TIMEOUT_MS = 30_000;
const COMPLETION_TIMEOUT_MS = 600_000; // 10 min for long RLM runs
const SOFT_CANCEL_FALLBACK_MS = 5_000;

// ── BackendBridge class ─────────────────────────────────────────────

export class BackendBridge {
  private proc: cp.ChildProcess | null = null;
  private buffer = "";
  private ready = false;
  private readyPromise: Promise<void> | null = null;
  private readyResolve: (() => void) | null = null;
  private readyReject: ((err: Error) => void) | null = null;
  private disposed = false;

  /** Monotonically increasing generation counter — used to ignore stale
   *  exit/error events from a previous process after restart. */
  private generation = 0;

  /** Pending completion requests waiting for a result. */
  private readonly pendingCompletions = new Map<string, PendingRequest>();

  /** Pending exec requests. */
  private readonly pendingExecs = new Map<string, PendingRequest<REPLResult>>();

  /** Callback for LLM requests in builtin mode. */
  private llmHandler:
    | ((prompt: string, model: string | null) => Promise<LlmHandlerResult>)
    | null = null;

  /** Callback for progress messages. */
  private progressHandler:
    | ((nonce: string, iteration: number, maxIterations: number, text: string) => void)
    | null = null;

  /** Callback for chunk messages. */
  private chunkHandler: ((nonce: string, text: string) => void) | null = null;

  /** Timer used to escalate soft cancel to hard process kill. */
  private cancelFallbackTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(private readonly pythonPath: string) {}

  // ── Lifecycle ───────────────────────────────────────────────────

  /**
   * Spawn the Python backend process and wait for the "ready" message.
   */
  async start(config: ProviderConfig): Promise<void> {
    if (this.disposed) {
      throw new Error("BackendBridge has been disposed");
    }

    // Kill any existing process
    this.killProcess();

    // Bump generation so stale exit/error handlers from the old process
    // cannot resolve/reject callbacks that belong to this new session.
    const gen = ++this.generation;

    const scriptPath = path.join(__dirname, "..", "python", "rlm_backend.py");
    logger.info("BackendBridge", "Spawning backend", { scriptPath, pythonPath: this.pythonPath });

    // Set up ready promise before spawning
    this.readyPromise = new Promise<void>((resolve, reject) => {
      this.readyResolve = resolve;
      this.readyReject = reject;
    });

    const repoRoot = path.join(__dirname, "..", "..");
    const processHandle = this.spawnBackendProcess(scriptPath, repoRoot);
    this.proc = processHandle;
    this.buffer = "";
    this.ready = false;
    this.wireProcessStreams(processHandle);
    this.wireProcessLifecycle(processHandle, gen);
    await this.waitForReadyOrTimeout();
    this.sendConfigure(config);

    logger.info("BackendBridge", "Backend started and configured");
  }

  /** Check if the backend process is alive and ready. */
  isAlive(): boolean {
    return this.proc !== null && this.ready && !this.disposed;
  }

  /** Gracefully dispose of the backend. */
  dispose(): void {
    this.disposed = true;
    this.send({ type: "shutdown" });
    setTimeout(() => this.killProcess(), 2000);
  }

  /**
   * Cancel all in-flight completions.  Kills the backend process so
   * Python threads are torn down immediately, then rejects every
   * pending promise.
   */
  cancelAll(): void {
    if (!this.isAlive()) {
      return;
    }

    this.send({ type: "cancel" });
    if (this.pendingCompletions.size === 0) {
      return;
    }

    this.clearCancelFallbackTimer();
    this.cancelFallbackTimer = setTimeout(() => {
      if (this.pendingCompletions.size === 0) {
        return;
      }
      logger.warn("BackendBridge", "Soft cancellation timed out; terminating backend", {
        pendingCompletions: this.pendingCompletions.size,
      });
      this.killProcess();
    }, SOFT_CANCEL_FALLBACK_MS);
  }

  // ── Public API ────────────────────────────────────────────────────

  /**
   * Run a full RLM completion through the Python backend.
   * Returns the final answer text.
   */
  async completion(
    prompt: string,
    context?: string,
    rootPrompt?: string,
    persistent?: boolean,
  ): Promise<string> {
    if (!this.isAlive()) {
      throw new Error("Backend is not running");
    }

    const nonce = this.generateNonce();
    const msg: CompletionMessage = {
      type: "completion",
      nonce,
      prompt,
      context,
      rootPrompt,
      persistent,
    };

    return new Promise<string>((resolve, reject) => {
      // Timeout
      const timer = setTimeout(() => {
        this.pendingCompletions.delete(nonce);
        reject(new Error(`Completion timed out after ${COMPLETION_TIMEOUT_MS / 1000}s`));
      }, COMPLETION_TIMEOUT_MS);

      this.pendingCompletions.set(nonce, {
        resolve: (value: string) => {
          clearTimeout(timer);
          this.maybeClearCancelFallbackTimer();
          resolve(value);
        },
        reject: (err: Error) => {
          clearTimeout(timer);
          this.maybeClearCancelFallbackTimer();
          reject(err);
        },
      });

      this.send(msg);
    });
  }

  /**
   * Execute raw code in the REPL (used for testing / FINAL_VAR resolution).
   */
  async execute(code: string): Promise<REPLResult> {
    if (!this.isAlive()) {
      throw new Error("Backend is not running");
    }

    const nonce = this.generateNonce();
    return new Promise<REPLResult>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingExecs.delete(nonce);
        reject(new Error("Execute timed out after 60s"));
      }, 60_000);

      this.pendingExecs.set(nonce, {
        resolve: (value: REPLResult) => {
          clearTimeout(timer);
          resolve(value);
        },
        reject: (err: Error) => {
          clearTimeout(timer);
          reject(err);
        },
      });

      this.send({ type: "execute", nonce, code });
    });
  }

  /** Register a handler for LLM requests (builtin mode). */
  setLlmHandler(
    handler: (prompt: string, model: string | null) => Promise<LlmHandlerResult>,
  ): void {
    this.llmHandler = handler;
  }

  /** Register a handler for progress updates. */
  setProgressHandler(
    handler: (nonce: string, iteration: number, maxIterations: number, text: string) => void,
  ): void {
    this.progressHandler = handler;
  }

  /** Register a handler for streamed text chunks. */
  setChunkHandler(handler: (nonce: string, text: string) => void): void {
    this.chunkHandler = handler;
  }

  // ── Internal: message IO ──────────────────────────────────────────

  private send(msg: OutboundMessage): void {
    if (!this.proc?.stdin?.writable) {
      logger.debug("BackendBridge", "Attempted to send message but stdin is not writable", {
        type: msg.type,
      });
      return;
    }
    const line = JSON.stringify(msg) + "\n";
    this.proc.stdin.write(line);
  }

  private onStdout(chunk: string): void {
    this.buffer += chunk;

    // Process complete lines
    let newlineIdx: number;
    while ((newlineIdx = this.buffer.indexOf("\n")) !== -1) {
      const line = this.buffer.slice(0, newlineIdx).trim();
      this.buffer = this.buffer.slice(newlineIdx + 1);

      if (!line) {
        continue;
      }

      let msg: InboundMessage;
      try {
        msg = JSON.parse(line) as InboundMessage;
      } catch {
        logger.warn("BackendBridge", "Non-JSON output from backend", {
          text: line.slice(0, 200),
        });
        continue;
      }

      this.handleMessage(msg);
    }
  }

  private handleMessage(msg: InboundMessage): void {
    switch (msg.type) {
      case "ready":
        this.handleReadyMessage();
        break;

      case "configured":
        this.handleConfiguredMessage(msg);
        break;

      case "chunk":
        this.handleChunkMessage(msg);
        break;

      case "result":
        this.handleResultMessage(msg);
        break;

      case "exec_result":
        this.handleExecResultMessage(msg);
        break;

      case "llm_request":
        void this.handleLlmRequest(msg.nonce, msg.prompt, msg.model);
        break;

      case "progress":
        this.handleProgressMessage(msg);
        break;

      case "error":
        this.handleErrorMessage(msg.nonce, msg.error);
        break;

      case "pong":
        this.handlePongMessage();
        break;

      default:
        this.handleUnknownMessage(msg);
        break;
    }
  }

  private handleReadyMessage(): void {
    this.ready = true;
    if (!this.readyResolve) {
      return;
    }
    this.readyResolve();
    this.readyResolve = null;
    this.readyReject = null;
  }

  private handleConfiguredMessage(msg: Extract<InboundMessage, { type: "configured" }>): void {
    logger.info("BackendBridge", "Backend configured", {
      provider: msg.provider,
      backend: msg.backend,
    });
  }

  private handleChunkMessage(msg: Extract<InboundMessage, { type: "chunk" }>): void {
    if (this.chunkHandler) {
      this.chunkHandler(msg.nonce, msg.text);
    }
  }

  private handleResultMessage(msg: Extract<InboundMessage, { type: "result" }>): void {
    const pending = this.pendingCompletions.get(msg.nonce);
    if (pending) {
      this.pendingCompletions.delete(msg.nonce);
      pending.resolve(msg.text);
    }
    this.maybeClearCancelFallbackTimer();
  }

  private handleExecResultMessage(msg: Extract<InboundMessage, { type: "exec_result" }>): void {
    const pending = this.pendingExecs.get(msg.nonce);
    if (pending) {
      this.pendingExecs.delete(msg.nonce);
      pending.resolve({
        stdout: msg.stdout,
        stderr: msg.stderr,
        error: msg.error,
      });
    }
  }

  private handleProgressMessage(msg: Extract<InboundMessage, { type: "progress" }>): void {
    if (this.progressHandler) {
      this.progressHandler(msg.nonce, msg.iteration, msg.maxIterations, msg.text);
    }
  }

  private handlePongMessage(): void {
    logger.debug("BackendBridge", "Pong received");
  }

  private handleUnknownMessage(msg: InboundMessage): void {
    logger.warn("BackendBridge", "Unknown message type", { msg });
  }

  /** Route an error message to the correct pending request, or log it. */
  private handleErrorMessage(nonce: string | null | undefined, error: string): void {
    if (nonce) {
      const completion = this.pendingCompletions.get(nonce);
      if (completion) {
        this.pendingCompletions.delete(nonce);
        completion.reject(new Error(error));
        this.maybeClearCancelFallbackTimer();
        return;
      }
      const exec = this.pendingExecs.get(nonce);
      if (exec) {
        this.pendingExecs.delete(nonce);
        exec.reject(new Error(error));
        return;
      }
    }
    logger.error("BackendBridge", "Backend error", { error, nonce });
  }

  /**
   * Handle an LLM request from the Python backend.
   * In builtin mode, this calls the VS Code Language Model API.
   */
  private async handleLlmRequest(
    nonce: string,
    prompt: string,
    model: string | null,
  ): Promise<void> {
    if (!this.llmHandler) {
      this.send({
        type: "llm_response",
        nonce,
        error: "No LLM handler registered (not in builtin mode?)",
      });
      return;
    }

    try {
      const result = await this.llmHandler(prompt, model);
      const payload: LlmResponseMessage = {
        type: "llm_response",
        nonce,
        text: result.text,
        ...(result.promptTokens !== undefined
          ? { promptTokens: result.promptTokens }
          : {}),
        ...(result.completionTokens !== undefined
          ? { completionTokens: result.completionTokens }
          : {}),
      };
      this.send(payload);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      this.send({ type: "llm_response", nonce, error: message });
    }
  }

  // ── Utilities ─────────────────────────────────────────────────────

  /**
   * Build a sanitised copy of `process.env` for the child process.
   * Strips VS Code internals, cloud credentials, and other sensitive vars.
   */
  private static buildChildEnv(repoRoot: string): Record<string, string> {
    const BLOCKED_PREFIXES = [
      "ELECTRON_", "VSCODE_", "AWS_", "AZURE_", "GCP_",
      "GITHUB_", "GOOGLE_APPLICATION", "DATABASE_",
    ];
    const BLOCKED_SUFFIXES = ["_TOKEN", "_SECRET", "_PASSWORD", "_CREDENTIALS"];
    const BLOCKED_EXACT = new Set(["CHROME_DESKTOP"]);

    const env: Record<string, string> = {};
    for (const [k, v] of Object.entries(process.env)) {
      if (v === undefined) {
        continue;
      }
      const upper = k.toUpperCase();
      if (BLOCKED_EXACT.has(upper)) {
        continue;
      }
      if (BLOCKED_PREFIXES.some((p) => upper.startsWith(p))) {
        continue;
      }
      if (BLOCKED_SUFFIXES.some((s) => upper.endsWith(s))) {
        continue;
      }
      env[k] = v;
    }

    // Ensure the rlm package is importable
    env["PYTHONPATH"] = repoRoot + (env["PYTHONPATH"] ? `${path.delimiter}${env["PYTHONPATH"]}` : "");
    return env;
  }

  private spawnBackendProcess(scriptPath: string, repoRoot: string): cp.ChildProcess {
    const filteredEnv = BackendBridge.buildChildEnv(repoRoot);
    return cp.spawn(this.pythonPath, ["-u", scriptPath], {
      stdio: ["pipe", "pipe", "pipe"],
      env: filteredEnv,
      cwd: repoRoot,
    });
  }

  private wireProcessStreams(processHandle: cp.ChildProcess): void {
    processHandle.stdout?.setEncoding("utf-8");
    processHandle.stdout?.on("data", (chunk: string) => this.onStdout(chunk));

    processHandle.stderr?.setEncoding("utf-8");
    processHandle.stderr?.on("data", (chunk: string) => {
      logger.warn("BackendBridge", "Python stderr", { text: chunk.trim() });
    });
  }

  private wireProcessLifecycle(processHandle: cp.ChildProcess, gen: number): void {
    processHandle.on("exit", (code, signal) => {
      logger.info("BackendBridge", "Process exited", { code, signal });
      if (gen !== this.generation) {
        return;
      }
      this.proc = null;
      this.ready = false;

      const exitError = new Error(`Python backend exited (code=${code}, signal=${signal})`);
      for (const [, pending] of this.pendingCompletions) {
        pending.reject(exitError);
      }
      this.pendingCompletions.clear();
      for (const [, pending] of this.pendingExecs) {
        pending.reject(exitError);
      }
      this.pendingExecs.clear();

      if (this.readyReject) {
        this.readyReject(exitError);
        this.readyResolve = null;
        this.readyReject = null;
      }
    });

    processHandle.on("error", (err) => {
      logger.error("BackendBridge", "Process spawn error", { error: err.message });
      if (gen !== this.generation) {
        return;
      }
      if (this.readyReject) {
        this.readyReject(err);
        this.readyResolve = null;
        this.readyReject = null;
      }
    });
  }

  private async waitForReadyOrTimeout(): Promise<void> {
    let readyTimer: ReturnType<typeof setTimeout> | undefined;
    const timeout = new Promise<never>((_, reject) => {
      readyTimer = setTimeout(
        () => reject(new Error(`Backend did not become ready within ${READY_TIMEOUT_MS}ms`)),
        READY_TIMEOUT_MS,
      );
    });

    try {
      await Promise.race([this.readyPromise, timeout]);
    } finally {
      clearTimeout(readyTimer);
    }
  }

  private sendConfigure(config: ProviderConfig): void {
    this.send({
      type: "configure",
      provider: config.provider,
      backend: config.backend,
      model: config.model,
      backendKwargs: config.backendKwargs,
      subBackend: config.subBackend,
      subBackendKwargs: config.subBackendKwargs,
      maxIterations: config.maxIterations,
      maxOutputChars: config.maxOutputChars,
      environment: config.environment,
    });
  }

  private generateNonce(): string {
    return crypto.randomUUID();
  }

  private clearCancelFallbackTimer(): void {
    if (this.cancelFallbackTimer) {
      clearTimeout(this.cancelFallbackTimer);
      this.cancelFallbackTimer = null;
    }
  }

  private maybeClearCancelFallbackTimer(): void {
    if (this.pendingCompletions.size === 0) {
      this.clearCancelFallbackTimer();
    }
  }

  private killProcess(): void {
    this.clearCancelFallbackTimer();

    if (this.proc) {
      try {
        this.proc.kill("SIGTERM");
      } catch (err: unknown) {
        logger.debug("BackendBridge", "kill() failed — process already dead", {
          error: err instanceof Error ? err.message : String(err),
        });
      }
      this.proc = null;
      this.ready = false;
    }

    // Reject any dangling ready/pending promises so callers aren't stuck.
    const cancelError = new Error("Backend process killed");
    if (this.readyReject) {
      this.readyReject(cancelError);
      this.readyResolve = null;
      this.readyReject = null;
    }
    for (const [, pending] of this.pendingCompletions) {
      pending.reject(cancelError);
    }
    this.pendingCompletions.clear();
    for (const [, pending] of this.pendingExecs) {
      pending.reject(cancelError);
    }
    this.pendingExecs.clear();
  }
}
