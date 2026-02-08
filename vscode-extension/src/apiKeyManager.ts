/**
 * Secure API key storage using VS Code's SecretStorage API.
 *
 * Keys are stored per-backend (e.g. "rlm.apiKey.openai") and never
 * written to settings.json or any file on disk.
 */

import * as vscode from "vscode";

const KEY_PREFIX = "rlm.apiKey.";

export class ApiKeyManager {
  constructor(private readonly secrets: vscode.SecretStorage) {}

  /** Store an API key for a backend. */
  async set(backend: string, key: string): Promise<void> {
    await this.secrets.store(`${KEY_PREFIX}${backend}`, key);
  }

  /** Retrieve an API key for a backend. Returns undefined if not set. */
  async get(backend: string): Promise<string | undefined> {
    return this.secrets.get(`${KEY_PREFIX}${backend}`);
  }

  /** Delete a stored API key for a backend. */
  async delete(backend: string): Promise<void> {
    await this.secrets.delete(`${KEY_PREFIX}${backend}`);
  }

  /**
   * Prompt the user for an API key and store it.
   * Returns the key if entered, undefined if cancelled.
   */
  async promptAndStore(backend: string): Promise<string | undefined> {
    const key = await vscode.window.showInputBox({
      prompt: `Enter API key for ${backend}`,
      password: true,
      placeHolder: "sk-...",
      ignoreFocusOut: true,
      validateInput: (value: string) => {
        if (!value.trim()) {
          return "API key cannot be empty";
        }
        return undefined;
      },
    });

    if (key) {
      await this.set(backend, key.trim());
      vscode.window.showInformationMessage(`API key for ${backend} saved securely.`);
    }

    return key?.trim();
  }

  /**
   * Clear all stored API keys and confirm to user.
   */
  async clearAll(backends: readonly string[]): Promise<void> {
    for (const backend of backends) {
      await this.delete(backend);
    }
    vscode.window.showInformationMessage("All RLM API keys cleared.");
  }
}
