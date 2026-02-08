/**
 * Platform detection — is this VS Code (with Chat + LM APIs) or Cursor?
 *
 * Cursor ships a modified VS Code but does NOT expose `vscode.chat` or
 * `vscode.lm`.  The only reliable integration path for Cursor is MCP.
 *
 * This module detects the host editor so the extension can:
 *  • VS Code  → register Chat Participant, use vscode.lm for builtin mode
 *  • Cursor   → skip Chat Participant registration, default to api_key mode
 */

import * as vscode from "vscode";

export type EditorKind = "vscode" | "cursor" | "unknown";

let _detected: EditorKind | undefined;

/**
 * Detect the host editor.
 *
 * Heuristics (in order):
 *  1. `vscode.env.appName` contains "Cursor" → cursor
 *  2. `vscode.env.uriScheme` starts with "cursor" → cursor
 *  3. `vscode.lm` namespace exists → vscode
 *  4. Fallback → unknown (treated as vscode for safety)
 */
export function detectEditor(): EditorKind {
  if (_detected !== undefined) {
    return _detected;
  }

  const appName = vscode.env.appName.toLowerCase();
  const uriScheme = vscode.env.uriScheme.toLowerCase();

  if (appName.includes("cursor") || uriScheme.startsWith("cursor")) {
    _detected = "cursor";
  } else if (typeof vscode.lm !== "undefined") {
    _detected = "vscode";
  } else {
    _detected = "unknown";
  }

  return _detected;
}

/** True when the host is Cursor (no Chat Participant or LM API). */
export function isCursor(): boolean {
  return detectEditor() === "cursor";
}

/** True when the host supports vscode.lm (Language Model API). */
export function hasLanguageModelApi(): boolean {
  return typeof vscode.lm !== "undefined";
}

/** True when the host supports vscode.chat (Chat Participant API). */
export function hasChatApi(): boolean {
  return typeof vscode.chat !== "undefined";
}
