import * as assert from "assert";
import { formatExecuteToolOutput, truncatePreview } from "./toolsFormatting";

function testTruncatePreviewNoTruncation(): void {
  const value = truncatePreview("short", 10);
  assert.strictEqual(value, "short");
}

function testTruncatePreviewWithTruncation(): void {
  const value = truncatePreview("abcdefghijklmnopqrstuvwxyz", 5);
  assert.strictEqual(value, "abcde...");
}

function testFormatExecuteToolOutputSuccess(): void {
  const output = formatExecuteToolOutput({
    stdout: "hello",
    stderr: "",
    error: false,
  });
  assert.ok(output.includes("status: ok"));
  assert.ok(output.includes("stdout:\nhello"));
  assert.ok(output.includes("stderr:\n(empty)"));
}

function testFormatExecuteToolOutputError(): void {
  const output = formatExecuteToolOutput({
    stdout: "",
    stderr: "boom",
    error: true,
  });
  assert.ok(output.includes("status: error"));
  assert.ok(output.includes("stdout:\n(empty)"));
  assert.ok(output.includes("stderr:\nboom"));
}

function runAllTests(): void {
  testTruncatePreviewNoTruncation();
  testTruncatePreviewWithTruncation();
  testFormatExecuteToolOutputSuccess();
  testFormatExecuteToolOutputError();
  console.log("toolsFormatting.test.ts: all tests passed");
}

runAllTests();
