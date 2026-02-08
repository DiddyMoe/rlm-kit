/**
 * Unit tests for the RLM logger.
 *
 * These tests exercise redaction, rotation, flush, and toggle behavior
 * without requiring the VS Code extension host.
 */

import * as fs from "fs";
import * as path from "path";
import * as os from "os";
import * as assert from "assert";
import { logger, LogLevel } from "./logger";

// ── Helpers ─────────────────────────────────────────────────────────

function createTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), "rlm-test-"));
}

function readLog(logDir: string): string[] {
  const logPath = path.join(logDir, "trace.jsonl");
  if (!fs.existsSync(logPath)) {
    return [];
  }
  return fs
    .readFileSync(logPath, "utf-8")
    .split("\n")
    .filter(Boolean);
}

function parseLogEntries(logDir: string): Array<Record<string, unknown>> {
  return readLog(logDir).map((line) => JSON.parse(line) as Record<string, unknown>);
}

// ── Tests ───────────────────────────────────────────────────────────

function testBasicLogging(): void {
  const dir = createTempDir();
  try {
    logger.init(dir, "debug", 5);
    logger.info("Test", "Hello world");
    logger.flush();

    const entries = parseLogEntries(dir);
    assert.strictEqual(entries.length, 1);
    assert.strictEqual(entries[0]["component"], "Test");
    assert.strictEqual(entries[0]["message"], "Hello world");
    assert.strictEqual(entries[0]["level"], "INFO");
    assert.ok(entries[0]["ts"]);
  } finally {
    logger.dispose();
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

function testLogLevelFiltering(): void {
  const dir = createTempDir();
  try {
    logger.init(dir, "warn", 5);
    logger.debug("Test", "Should be filtered");
    logger.info("Test", "Should be filtered");
    logger.warn("Test", "Should appear");
    logger.error("Test", "Should appear");

    const entries = parseLogEntries(dir);
    assert.strictEqual(entries.length, 2);
    assert.strictEqual(entries[0]["level"], "WARN");
    assert.strictEqual(entries[1]["level"], "ERROR");
  } finally {
    logger.dispose();
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

function testRedactionOpenAIKey(): void {
  const dir = createTempDir();
  try {
    logger.init(dir, "debug", 5);
    logger.info("Test", "Key test", { key: "sk-abcdefghijklmnopqrstuvwxyz1234567890" });
    logger.flush();

    const entries = parseLogEntries(dir);
    const data = entries[0]["data"] as Record<string, string>;
    assert.ok(!data["key"].includes("sk-"));
    assert.ok(data["key"].includes("[REDACTED]"));
  } finally {
    logger.dispose();
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

function testRedactionBearerToken(): void {
  const dir = createTempDir();
  try {
    logger.init(dir, "debug", 5);
    logger.info("Test", "Auth test", { header: "Bearer eyJabcdef.ghijklmnop.qrstuv" });
    logger.flush();

    const entries = parseLogEntries(dir);
    const data = entries[0]["data"] as Record<string, string>;
    assert.ok(!data["header"].includes("eyJ"));
    assert.ok(data["header"].includes("[REDACTED]"));
  } finally {
    logger.dispose();
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

function testRedactionArrays(): void {
  const dir = createTempDir();
  try {
    logger.init(dir, "debug", 5);
    logger.info("Test", "Array test", {
      keys: ["sk-abcdefghijklmnopqrstuvwxyz12345678", "normal-value"] as unknown as string,
    });
    logger.flush();

    const entries = parseLogEntries(dir);
    const data = entries[0]["data"] as Record<string, unknown>;
    const keys = data["keys"] as string[];
    assert.ok(Array.isArray(keys));
    assert.ok(!keys[0].includes("sk-"));
    assert.strictEqual(keys[1], "normal-value");
  } finally {
    logger.dispose();
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

function testRedactionNestedObjects(): void {
  const dir = createTempDir();
  try {
    logger.init(dir, "debug", 5);
    logger.info("Test", "Nested test", {
      config: {
        api_key: "sk-abcdefghijklmnopqrstuvwxyz12345678",
        model: "gpt-4o",
      } as unknown as string,
    });
    logger.flush();

    const entries = parseLogEntries(dir);
    const data = entries[0]["data"] as Record<string, Record<string, string>>;
    assert.ok(!data["config"]["api_key"].includes("sk-"));
    assert.strictEqual(data["config"]["model"], "gpt-4o");
  } finally {
    logger.dispose();
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

function testTracingToggle(): void {
  const dir = createTempDir();
  try {
    logger.init(dir, "debug", 5);
    logger.setTracingEnabled(false);

    logger.debug("Test", "Should be filtered");
    logger.info("Test", "Should be filtered");
    logger.warn("Test", "Should appear");
    logger.error("Test", "Should appear");

    const entries = parseLogEntries(dir);
    // Only WARN and ERROR should make it through when tracing is off
    assert.strictEqual(entries.length, 2);
    assert.strictEqual(entries[0]["level"], "WARN");
    assert.strictEqual(entries[1]["level"], "ERROR");

    // Re-enable tracing
    logger.setTracingEnabled(true);
    logger.info("Test", "Now visible");
    logger.flush();

    const entries2 = parseLogEntries(dir);
    assert.strictEqual(entries2.length, 3);
    assert.strictEqual(entries2[2]["level"], "INFO");
  } finally {
    logger.dispose();
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

function testRotation(): void {
  const dir = createTempDir();
  try {
    // Init with very small max (1 KB)
    logger.init(dir, "debug", 0.001); // ~1 KB

    // Write data in batches, flushing each time to trigger size checks
    for (let i = 0; i < 10; i++) {
      for (let j = 0; j < 10; j++) {
        logger.info("Test", `Long message ${i * 10 + j} with padding ${"x".repeat(50)}`);
      }
      logger.flush();
    }

    // File should still exist and be valid JSONL
    const logPath = path.join(dir, "trace.jsonl");
    assert.ok(fs.existsSync(logPath));

    const content = fs.readFileSync(logPath, "utf-8");
    const lines = content.split("\n").filter(Boolean);

    // Should have fewer lines than we wrote (rotation trimmed)
    assert.ok(lines.length < 100, `Expected fewer than 100 lines after rotation, got ${lines.length}`);
    assert.ok(lines.length > 0, "Should have at least some lines");

    // Each line should be valid JSON
    for (const line of lines) {
      JSON.parse(line); // throws if invalid
    }
  } finally {
    logger.dispose();
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

function testSpanEmission(): void {
  const dir = createTempDir();
  try {
    logger.init(dir, "debug", 5);
    logger.span("Orchestrator", "test span", "span-123", 1500, { result: "ok" });
    logger.flush();

    const entries = parseLogEntries(dir);
    assert.strictEqual(entries.length, 1);
    assert.strictEqual(entries[0]["level"], "TRACE");
    assert.strictEqual(entries[0]["spanId"], "span-123");
    assert.strictEqual(entries[0]["durationMs"], 1500);
  } finally {
    logger.dispose();
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

function testGeminiKeyRedaction(): void {
  const dir = createTempDir();
  try {
    logger.init(dir, "debug", 5);
    logger.info("Test", "Gemini test", { key: "AIzaSyB1234567890abcdefghijklmnopqrstuuuu" });
    logger.flush();

    const entries = parseLogEntries(dir);
    const data = entries[0]["data"] as Record<string, string>;
    assert.ok(!data["key"].includes("AIza"));
    assert.ok(data["key"].includes("[REDACTED]"));
  } finally {
    logger.dispose();
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

function testGitHubPatRedaction(): void {
  const dir = createTempDir();
  try {
    logger.init(dir, "debug", 5);
    logger.info("Test", "GitHub test", {
      token: "ghp_1234567890abcdefghijklmnopqrstuvwxyz",
    });
    logger.flush();

    const entries = parseLogEntries(dir);
    const data = entries[0]["data"] as Record<string, string>;
    assert.ok(!data["token"].includes("ghp_"));
    assert.ok(data["token"].includes("[REDACTED]"));
  } finally {
    logger.dispose();
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

function testDisposeFlushes(): void {
  const dir = createTempDir();
  try {
    logger.init(dir, "debug", 5);
    logger.info("Test", "Should be flushed on dispose");
    // Don't call flush — dispose should flush
    logger.dispose();

    const entries = parseLogEntries(dir);
    assert.strictEqual(entries.length, 1);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

// ── Runner ──────────────────────────────────────────────────────────

const tests = [
  ["basic logging", testBasicLogging],
  ["log level filtering", testLogLevelFiltering],
  ["redaction: OpenAI key", testRedactionOpenAIKey],
  ["redaction: Bearer token", testRedactionBearerToken],
  ["redaction: arrays", testRedactionArrays],
  ["redaction: nested objects", testRedactionNestedObjects],
  ["tracing toggle", testTracingToggle],
  ["rotation", testRotation],
  ["span emission", testSpanEmission],
  ["redaction: Gemini key", testGeminiKeyRedaction],
  ["redaction: GitHub PAT", testGitHubPatRedaction],
  ["dispose flushes", testDisposeFlushes],
] as const;

let passed = 0;
let failed = 0;

for (const [name, fn] of tests) {
  try {
    fn();
    console.log(`  ✓ ${name}`);
    passed++;
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`  ✗ ${name}: ${msg}`);
    failed++;
  }
}

console.log(`\n${passed} passed, ${failed} failed`);

if (failed > 0) {
  process.exit(1);
}

// Export for potential mocha use
export { LogLevel };
