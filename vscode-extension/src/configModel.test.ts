import * as assert from "assert";
import { DEFAULT_RLM_CONFIG, normalizeRlmConfig } from "./configModel";

function testDefaultsWhenRawIsEmpty(): void {
  const config = normalizeRlmConfig({});
  assert.deepStrictEqual(config, DEFAULT_RLM_CONFIG);
}

function testOptionalSubFieldsNormalizeToUndefined(): void {
  const config = normalizeRlmConfig({ subBackend: "", subModel: "" });
  assert.strictEqual(config.subBackend, undefined);
  assert.strictEqual(config.subModel, undefined);
}

function testConfiguredValuesOverrideDefaults(): void {
  const config = normalizeRlmConfig({
    provider: "api_key",
    backend: "anthropic",
    model: "claude-3-7-sonnet",
    maxIterations: 10,
    maxOutputChars: 1000,
    logLevel: "info",
    tracingEnabled: false,
  });

  assert.strictEqual(config.provider, "api_key");
  assert.strictEqual(config.backend, "anthropic");
  assert.strictEqual(config.model, "claude-3-7-sonnet");
  assert.strictEqual(config.maxIterations, 10);
  assert.strictEqual(config.maxOutputChars, 1000);
  assert.strictEqual(config.logLevel, "info");
  assert.strictEqual(config.tracingEnabled, false);
}

function runAllTests(): void {
  testDefaultsWhenRawIsEmpty();
  testOptionalSubFieldsNormalizeToUndefined();
  testConfiguredValuesOverrideDefaults();
  console.log("configModel.test.ts: all tests passed");
}

runAllTests();
