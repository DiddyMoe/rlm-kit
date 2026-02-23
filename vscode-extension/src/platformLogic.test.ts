import * as assert from "assert";
import { detectEditorKind } from "./platformLogic";

function testDetectCursorByAppName(): void {
  const detected = detectEditorKind("Cursor", "vscode", true);
  assert.strictEqual(detected, "cursor");
}

function testDetectCursorByUriScheme(): void {
  const detected = detectEditorKind("Visual Studio Code", "cursor-plus", true);
  assert.strictEqual(detected, "cursor");
}

function testDetectVsCodeWithLmApi(): void {
  const detected = detectEditorKind("Visual Studio Code", "vscode", true);
  assert.strictEqual(detected, "vscode");
}

function testDetectUnknownWithoutLmApi(): void {
  const detected = detectEditorKind("Visual Studio Code", "vscode", false);
  assert.strictEqual(detected, "unknown");
}

function runAllTests(): void {
  testDetectCursorByAppName();
  testDetectCursorByUriScheme();
  testDetectVsCodeWithLmApi();
  testDetectUnknownWithoutLmApi();
  console.log("platformLogic.test.ts: all tests passed");
}

runAllTests();
