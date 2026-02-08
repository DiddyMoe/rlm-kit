/**
 * Structured JSONL logger for the RLM extension.
 *
 * Features:
 *  • JSONL format (one JSON object per line) for machine-parsable logs
 *  • Log level filtering (debug/info/warn/error/off)
 *  • Automatic size-based rotation (configurable max size)
 *  • Sensitive value redaction (API keys, tokens)
 *  • Buffered writes with sync flush on WARN+
 *  • Crash-safe: flush buffer on dispose
 *  • Singleton pattern — import { logger } from "./logger"
 *
 * Replaces the old plain-text logger with zero external dependencies.
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
}

// ── Redaction ───────────────────────────────────────────────────────

const REDACT_PATTERNS = [
  /sk-[a-zA-Z0-9_-]{20,}/g,
  /key-[a-zA-Z0-9_-]{20,}/g,
  /Bearer\s+[a-zA-Z0-9_.-]+/gi,
  /api[_-]?key["':\s]*["']?[a-zA-Z0-9_-]{16,}/gi,
];

function redact(value: string): string {
  let result = value;
  for (const pattern of REDACT_PATTERNS) {
    // Reset lastIndex for global regex reuse
    pattern.lastIndex = 0;
    result = result.replace(pattern, "[REDACTED]");
  }
  return result;
}

function redactObject(obj: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    if (typeof value === "string") {
      result[key] = redact(value);
    } else if (typeof value === "object" && value !== null && !Array.isArray(value)) {
      result[key] = redactObject(value as Record<string, unknown>);
    } else {
      result[key] = value;
    }
  }
  return result;
}

// ── Logger ──────────────────────────────────────────────────────────

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

class Logger {
  private fd: number | null = null;
  private logPath = "";
  private minLevel: LogLevel = LogLevel.DEBUG;
  private maxSizeBytes: number = 5 * 1024 * 1024;
  private buffer: string[] = [];
  private flushTimer: ReturnType<typeof setInterval> | null = null;
  private currentSize = 0;
  private initialized = false;

  /**
   * Initialize the logger.
   * @param logDir   Directory for log files (e.g. globalStorageUri.fsPath)
   * @param level    Minimum log level string
   * @param maxMb    Maximum log file size in MB
   */
  init(logDir: string, level: string = "debug", maxMb: number = 5): void {
    if (this.initialized) {
      this.dispose();
    }

    this.minLevel = parseLogLevel(level);
    this.maxSizeBytes = maxMb * 1024 * 1024;

    // Ensure directory exists
    fs.mkdirSync(logDir, { recursive: true });

    this.logPath = path.join(logDir, "rlm.jsonl");

    // Open for append
    try {
      this.fd = fs.openSync(this.logPath, "a");
      const stat = fs.fstatSync(this.fd);
      this.currentSize = stat.size;
    } catch {
      // Fallback: log to console only
      this.fd = null;
    }

    // Flush buffer every 2 seconds
    this.flushTimer = setInterval(() => this.flush(), 2000);

    this.initialized = true;
  }

  /** Update log level at runtime (e.g. from settings change). */
  setLevel(level: string): void {
    this.minLevel = parseLogLevel(level);
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

    const entry: LogEntry = {
      ts: new Date().toISOString(),
      level: LEVEL_NAMES[level],
      component,
      message,
      ...(data ? { data: redactObject(data) } : {}),
    };

    const line = JSON.stringify(entry) + "\n";
    this.buffer.push(line);

    // Sync flush on WARN+ for crash safety
    if (level >= LogLevel.WARN) {
      this.flush();
    }
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
      // File write failed — drop silently
      return;
    }

    // Check rotation
    if (this.currentSize > this.maxSizeBytes) {
      this.rotate();
    }
  }

  private rotate(): void {
    if (this.fd === null) {
      return;
    }

    try {
      fs.closeSync(this.fd);
    } catch {
      // ignore
    }

    // Keep one backup
    const backupPath = this.logPath + ".1";
    try {
      if (fs.existsSync(backupPath)) {
        fs.unlinkSync(backupPath);
      }
      fs.renameSync(this.logPath, backupPath);
    } catch {
      // If rename fails, just truncate
    }

    try {
      this.fd = fs.openSync(this.logPath, "w");
      this.currentSize = 0;
    } catch {
      this.fd = null;
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
