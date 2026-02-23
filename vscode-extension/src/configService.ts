/**
 * Centralized configuration service for the RLM extension.
 *
 * Single source of truth for all `rlm.*` settings. Emits a typed
 * change event so other modules can react to runtime config updates.
 *
 * Usage:
 *   const cfg = ConfigService.instance;
 *   cfg.init(context);
 *   const depth = cfg.get().maxIterations;
 *   cfg.onDidChange(() => { ... });
 */

import * as vscode from "vscode";
import type { ClientBackend, LlmProvider } from "./types";
import {
  DEFAULT_RLM_CONFIG,
  normalizeRlmConfig,
  type RlmConfig,
} from "./configModel";

export type { RlmConfig } from "./configModel";

// ── Service ─────────────────────────────────────────────────────────

export class ConfigService implements vscode.Disposable {
  private static _instance: ConfigService | undefined;
  private readonly _onDidChange = new vscode.EventEmitter<RlmConfig>();
  readonly onDidChange = this._onDidChange.event;

  private _config: RlmConfig = DEFAULT_RLM_CONFIG;
  private _disposables: vscode.Disposable[] = [];

  private constructor() {}

  static get instance(): ConfigService {
    if (!ConfigService._instance) {
      ConfigService._instance = new ConfigService();
    }
    return ConfigService._instance;
  }

  /** Wire up the settings-change listener. Call once during activation. */
  init(context: vscode.ExtensionContext): void {
    this._config = this.read();

    const watcher = vscode.workspace.onDidChangeConfiguration((e) => {
      if (!e.affectsConfiguration("rlm")) {
        return;
      }
      this._config = this.read();
      this._onDidChange.fire(this._config);
    });

    this._disposables.push(watcher);
    context.subscriptions.push(this);
  }

  /** Current configuration snapshot. */
  get(): RlmConfig {
    return this._config;
  }

  dispose(): void {
    this._onDidChange.dispose();
    for (const d of this._disposables) {
      d.dispose();
    }
    this._disposables = [];
  }

  // ── Private ─────────────────────────────────────────────────────

  private read(): RlmConfig {
    const s = vscode.workspace.getConfiguration("rlm");

    return normalizeRlmConfig({
      provider: s.get<LlmProvider>("llmProvider"),
      backend: s.get<ClientBackend>("backend"),
      model: s.get<string>("model"),
      baseUrl: s.get<string>("baseUrl"),
      subBackend: s.get<string>("subBackend"),
      subModel: s.get<string>("subModel"),
      maxIterations: s.get<number>("maxIterations"),
      maxOutputChars: s.get<number>("maxOutputChars"),
      pythonPath: s.get<string>("pythonPath"),
      showIterationDetails: s.get<boolean>("showIterationDetails"),
      environment: s.get<string>("environment"),
      tracingEnabled: s.get<boolean>("tracingEnabled"),
      logLevel: s.get<string>("logLevel"),
      logMaxSizeMB: s.get<number>("logMaxSizeMB"),
    });
  }
}
