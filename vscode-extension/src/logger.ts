/**
 * Structured JSONL logger for the RLM extension.
 *
 * Features:
 *  - JSONL format (one JSON object per line) for machine-parsable logs
 *  - Log level filtering (debug / info / warn / error / off)
 *  - Automatic size-based rolling (configurable; default 10 MB)
 *  - Sensitive value redaction (API keys, tokens, secrets — including arrays)
 *  - Buffered writes with sync flush on WARN+ for crash safety
 *  - Final flush on dispose and on uncaughtException/unhandledRejection
 *  - Toggle-able: when tracing is disabled, only WARN+ are written
 *  - Singleton — import { logger } from "./logger"
 */

import * as fs from "fs";
import * as path from "path";

// ── Types ───────────────────────────────────────────────────────────

export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
  OFF = 4,
}

interface LogEntry {
  readonly ts: string;
  readonly level: string;
  readonly component: string;
  readonly message: string;
  readonly data?: Record<string, unknown>;
  readonly spanId?: string;
  readonly durationMs?: number;
}

// ── Redaction ───────────────────────────────────────────────────────

const REDACT_PATTERNS: readonly RegExp[] = [
  // OpenAI / OpenRouter / generic sk- keys
  /sk-[a-zA-Z0-9_-]{20,}/g,
  // Generic key- prefix tokens
  /key-[a-zA-Z0-9_-]{20,}/g,
  // Bearer tokens
  /Bearer\s+[a-zA-Z0-9_.+/=-]+/gi,
  // api_key / api-key fields with value
  /api[_-]?key["':\s]*["']?[a-zA-Z0-9_-]{16,}/gi,
  // Google / Gemini API keys (AIza prefix)
  /AIza[a-zA-Z0-9_-]{35}/g,
  // GitHub PATs (ghp_ and gho_)
  /gh[po]_[a-zA-Z0-9]{36}/g,
  // Generic "token" fields
  /token["':\s]*["']?[a-zA-Z0-9_.+/=-]{20,}/gi,
  // Generic "secret" fields
  /secret["':\s]*["']?[a-zA-Z0-9_.+/=-]{16,}/gi,
  // Generic "password" fields
  /password["':\s]*["']?[^\s"']{8,}/gi,
];

const REDACTION = "[REDACTED]";

function redact(value: string): string {
  let result = value;
  for (const pattern of REDACT_PATTERNS) {
    pattern.lastIndex = 0;
    result = result.replace(pattern, REDACTION);
  }
  return result;
}

function redactUnknown(value: unknown): unknown {
  if (typeof value === "string") {
    return redact(value);
  }
  if (Array.isArray(value)) {
    return value.map(redactUnknown);
  }
  if (typeof value === "object" && value !== null) {
    return redactObject(value as Record<string, unknown>);
  }
  return value;
}

function redactObject(obj: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    result[key] = redactUnknown(value);
  }
  return result;
}

// ── Log level helpers ───────────────────────────────────────────────

const LEVEL_NAMES: Record<LogLevel, string> = {
  [LogLevel.DEBUG]: "DEBUG",
  [LogLevel.INFO]: "INFO",
  [LogLevel.WARN]: "WARN",
  [LogLevel.ERROR]: "ERROR",
  [LogLevel.OFF]: "OFF",
};

function parseLogLevel(level: string): LogLevel {
  switch (level.toLowerCase()) {
    case "debug":
      return LogLevel.DEBUG;
    case "info":
      return LogLevel.INFO;
    case "warn":
      return LogLevel.WARN;
    case "error":
      return LogLevel.ERROR;
    case "off":
      return LogLevel.OFF;
    default:
      return LogLevel.DEBUG;
  }
}

// ── Logger ──────────────────────────────────────────────────────────

class Logger {
  private fd: number | null = null;
  private logPath = "";
  private minLevel: LogLevel = LogLevel.DEBUG;
  private maxSizeBytes: number = 10 * 1024 * 1024;
  private buffer: string[] = [];
  private flushTimer: ReturnType<typeof setInterval> | null = null;
  private currentSize = 0;
  private initialized = false;
  private tracingEnabled = true;
  private crashHandlersRegistered = false;

  /**
   * Initialize the logger.
   * @param logDir   Directory for log files (e.g. globalStorageUri.fsPath)
   * @param level    Minimum log level string
   * @param maxMb    Maximum log file size in MB
   */
  init(logDir: string, level: string = "debug", maxMb: number = 10): void {
    if (this.initialized) {
      this.dispose();
    }

    this.minLevel = parseLogLevel(level);
    this.maxSizeBytes = maxMb * 1024 * 1024;

    fs.mkdirSync(logDir, { recursive: true });
    this.logPath = path.join(logDir, "rlm.jsonl");

    try {
      this.fd = fs.openSync(this.logPath, "a");
      const stat = fs.fstatSync(this.fd);
      this.currentSize = stat.size;
    } catch {
      this.fd = null;
    }

    this.flushTimer = setInterval(() => this.flush(), 2000);

    // Crash-safe: flush on unhandled errors (register only once)
    if (!this.crashHandlersRegistered) {
      this.crashHandlersRegistered = true;
      process.on("uncaughtException", (err: Error) => {
        this.error("Process", "Uncaught exception", { error: err.message, stack: err.stack });
        this.flush();
      });
      process.on("unhandledRejection", (reason: unknown) => {
        const msg = reason instanceof Error ? reason.message : String(reason);
        this.error("Process", "Unhandled rejection", { error: msg });
        this.flush();
      });
    }

    this.initialized = true;
  }

  /** Update log level at runtime. */
  setLevel(level: string): void {
    this.minLevel = parseLogLevel(level);
  }

  /** Enable or disable tracing. When disabled only WARN+ are written. */
  setTracingEnabled(enabled: boolean): void {
    this.tracingEnabled = enabled;
  }

  /** Path to the current log file. */
  getLogPath(): string {
    return this.logPath;
  }

  // ── Log methods ─────────────────────────────────────────────────

  debug(component: string, message: string, data?: Record<string, unknown>): void {
    this.log(LogLevel.DEBUG, component, message, data);
  }

  info(component: string, message: string, data?: Record<string, unknown>): void {
    this.log(LogLevel.INFO, component, message, data);
  }

  warn(component: string, message: string, data?: Record<string, unknown>): void {
    this.log(LogLevel.WARN, component, message, data);
  }

  error(component: string, message: string, data?: Record<string, unknown>): void {
    this.log(LogLevel.ERROR, component, message, data);
  }

  /** Emit a structured trace span. */
  span(
    component: string,
    message: string,
    spanId: string,
    durationMs: number,
    data?: Record<string, unknown>,
  ): void {
    if (!this.tracingEnabled) {
      return;
    }
    this.writeEntry({
      ts: new Date().toISOString(),
      level: "TRACE",
      component,
      message,
      spanId,
      durationMs,
      ...(data ? { data: redactObject(data) } : {}),
    });
  }

  // ── Core write ──────────────────────────────────────────────────

  private log(
    level: LogLevel,
    component: string,
    message: string,
    data?: Record<string, unknown>,
  ): void {
    if (level < this.minLevel) {
      return;
    }

    // When tracing is off, only WARN+ go through
    if (!this.tracingEnabled && level < LogLevel.WARN) {
      return;
    }

    this.writeEntry({
      ts: new Date().toISOString(),
      level: LEVEL_NAMES[level],
      component,
      message,
      ...(data ? { data: redactObject(data) } : {}),
    });

    // Sync flush on WARN+ for crash safety
    if (level >= LogLevel.WARN) {
      this.flush();
    }
  }

  private writeEntry(entry: LogEntry): void {
    const line = JSON.stringify(entry) + "\n";
    this.buffer.push(line);
  }

  // ── Flush & rotation ────────────────────────────────────────────

  flush(): void {
    if (this.buffer.length === 0 || this.fd === null) {
      return;
    }

    const combined = this.buffer.join("");
    this.buffer = [];

    try {
      fs.writeSync(this.fd, combined);
      this.currentSize += Buffer.byteLength(combined, "utf-8");
    } catch {
      return;
    }

    if (this.currentSize > this.maxSizeBytes) {
      this.rotate();
    }
  }

  /**
   * Rotate the log file. Keeps newest entries by:
   * 1. Reading the current file
   * 2. Keeping only the last ~50% of lines
   * 3. Writing them to a new file
   *
   * Falls back to simple rename + truncate if read fails.
   */
  private rotate(): void {
    if (this.fd === null) {
      return;
    }

    try {
      fs.closeSync(this.fd);
    } catch {
      // ignore
    }

    try {
      const content = fs.readFileSync(this.logPath, "utf-8");
      const lines = content.split("\n").filter(Boolean);
      const keepCount = Math.max(1, Math.floor(lines.length / 2));
      const kept = lines.slice(lines.length - keepCount);
      fs.writeFileSync(this.logPath, kept.join("\n") + "\n", "utf-8");
    } catch {
      const backupPath = this.logPath + ".1";
      try {
        if (fs.existsSync(backupPath)) {
          fs.unlinkSync(backupPath);
        }
        fs.renameSync(this.logPath, backupPath);
      } catch {
        // If rename fails, just truncate
      }
    }

    try {
      this.fd = fs.openSync(this.logPath, "a");
      const stat = fs.fstatSync(this.fd);
      this.currentSize = stat.size;
    } catch {
      this.fd = null;
      this.currentSize = 0;
    }
  }

  // ── Cleanup ─────────────────────────────────────────────────────

  dispose(): void {
    this.flush();

    if (this.flushTimer) {
      clearInterval(this.flushTimer);
      this.flushTimer = null;
    }

    if (this.fd !== null) {
      try {
        fs.closeSync(this.fd);
      } catch {
        // ignore
      }
      this.fd = null;
    }

    this.initialized = false;
  }
}

// ── Singleton export ────────────────────────────────────────────────

export const logger = new Logger();
