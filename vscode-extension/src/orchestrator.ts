/**
 * RLM Orchestrator — the boundary between the chat participant and the
 * Python backend.
 *
 * Responsibilities:
 *  - Bounded recursion depth enforcement
 *  - Work budget tracking (wall-clock time + step count)
 *  - Deterministic termination conditions
 *  - Trace span emission for every orchestration step
 *  - Externalized context management
 *  - Error boundary with structured logging
 *
 * The orchestrator does NOT duplicate the Python RLM iteration loop.
 * It wraps the BackendBridge call with safety, observability, and
 * configuration enforcement.
 */

import * as crypto from "crypto";
import { BackendBridge } from "./backendBridge";
import { logger } from "./logger";
import type { RlmConfig } from "./configService";

// ── Types ───────────────────────────────────────────────────────────

export interface OrchestrationRequest {
  readonly prompt: string;
  readonly context: string | undefined;
  readonly rootPrompt: string;
  readonly persistent: boolean;
}

export interface OrchestrationResult {
  readonly text: string;
  readonly spanId: string;
  readonly durationMs: number;
  readonly iterationsUsed: number;
  readonly budgetExhausted: boolean;
}

interface BudgetState {
  stepsUsed: number;
  readonly maxSteps: number;
  readonly maxWallClockMs: number;
  readonly startedAt: number;
}

// ── Constants ───────────────────────────────────────────────────────

/** Hard ceiling: no config can exceed this. */
const ABSOLUTE_MAX_ITERATIONS = 50;

/** Default wall-clock budget per orchestration call (10 minutes). */
const DEFAULT_WALL_CLOCK_MS = 600_000;

// ── Orchestrator ────────────────────────────────────────────────────

export class Orchestrator {
  private activeBudget: BudgetState | null = null;

  constructor(private readonly bridge: BackendBridge) {}

  /**
   * Run a single orchestrated RLM completion.
   *
   * Enforces:
   *  - maxIterations cap (from config, clamped to ABSOLUTE_MAX_ITERATIONS)
   *  - Wall-clock timeout
   *  - Trace spans for the full call
   */
  async run(
    request: OrchestrationRequest,
    config: RlmConfig,
    onProgress?: (iteration: number, maxIterations: number, text: string) => void,
    onChunk?: (text: string) => void,
  ): Promise<OrchestrationResult> {
    const spanId = crypto.randomUUID();
    const startTime = Date.now();

    const maxSteps = Math.min(config.maxIterations, ABSOLUTE_MAX_ITERATIONS);

    this.activeBudget = {
      stepsUsed: 0,
      maxSteps,
      maxWallClockMs: DEFAULT_WALL_CLOCK_MS,
      startedAt: startTime,
    };

    logger.info("Orchestrator", "Starting orchestrated completion", {
      spanId,
      maxSteps,
      promptLength: request.prompt.length,
      hasContext: request.context !== undefined,
    });
    this.wireProgressHandlers(onProgress, onChunk);

    try {
      const result = await this.executeWithBudget(request, spanId);
      return this.buildResult(result, spanId, startTime, maxSteps);
    } catch (err: unknown) {
      const durationMs = Date.now() - startTime;
      const message = err instanceof Error ? err.message : String(err);

      logger.span("Orchestrator", "Completion failed", spanId, durationMs, {
        error: message,
        stepsUsed: this.activeBudget.stepsUsed,
      });

      throw err;
    } finally {
      this.activeBudget = null;
    }
  }

  // ── Private ─────────────────────────────────────────────────────

  private wireProgressHandlers(
    onProgress?: (iteration: number, maxIterations: number, text: string) => void,
    onChunk?: (text: string) => void,
  ): void {
    if (onProgress) {
      this.bridge.setProgressHandler((_nonce, iteration, maxIterations, text) => {
        this.activeBudget = this.activeBudget
          ? { ...this.activeBudget, stepsUsed: iteration }
          : null;
        onProgress(iteration, maxIterations, text);
      });
    }
    if (onChunk) {
      this.bridge.setChunkHandler((_nonce, text) => {
        onChunk(text);
      });
    }
  }

  private buildResult(
    text: string,
    spanId: string,
    startTime: number,
    maxSteps: number,
  ): OrchestrationResult {
    const durationMs = Date.now() - startTime;
    const stepsUsed = this.activeBudget?.stepsUsed ?? 0;
    const budgetExhausted = stepsUsed >= maxSteps || durationMs >= DEFAULT_WALL_CLOCK_MS;

    logger.span("Orchestrator", "Completion finished", spanId, durationMs, {
      stepsUsed,
      maxSteps,
      budgetExhausted,
      resultLength: text.length,
    });

    return {
      text,
      spanId,
      durationMs,
      iterationsUsed: stepsUsed,
      budgetExhausted,
    };
  }

  private async executeWithBudget(
    request: OrchestrationRequest,
    spanId: string,
  ): Promise<string> {
    if (!this.activeBudget) {
      throw new Error("No active budget — call run() first");
    }

    const { maxWallClockMs, startedAt } = this.activeBudget;

    // Create a timeout race
    const completionPromise = this.bridge.completion(
      request.prompt,
      request.context,
      request.rootPrompt,
      request.persistent,
    );

    const remainingMs = Math.max(0, maxWallClockMs - (Date.now() - startedAt));

    let timer: ReturnType<typeof setTimeout> | undefined;
    const timeoutPromise = new Promise<never>((_resolve, reject) => {
      timer = setTimeout(() => {
        logger.warn("Orchestrator", "Wall-clock budget exhausted, cancelling", {
          spanId,
          elapsedMs: Date.now() - startedAt,
        });
        this.bridge.cancelAll();
        reject(new Error("Orchestration wall-clock budget exhausted"));
      }, remainingMs);
    });

    try {
      return await Promise.race([completionPromise, timeoutPromise]);
    } finally {
      clearTimeout(timer);
    }
  }
}
