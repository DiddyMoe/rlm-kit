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
import type { LlmProvider, ClientBackend } from "./types";

// ── Config shape ────────────────────────────────────────────────────

export interface RlmConfig {
  readonly provider: LlmProvider;
  readonly backend: ClientBackend;
  readonly model: string;
  readonly baseUrl: string;
  readonly subBackend: ClientBackend | undefined;
  readonly subModel: string | undefined;
  readonly maxIterations: number;
  readonly maxOutputChars: number;
  readonly pythonPath: string;
  readonly showIterationDetails: boolean;
  readonly tracingEnabled: boolean;
  readonly logLevel: string;
  readonly logMaxSizeMB: number;
}

// ── Defaults ────────────────────────────────────────────────────────

const DEFAULTS: RlmConfig = {
  provider: "builtin",
  backend: "openai",
  model: "gpt-4o",
  baseUrl: "",
  subBackend: undefined,
  subModel: undefined,
  maxIterations: 30,
  maxOutputChars: 20_000,
  pythonPath: "python3",
  showIterationDetails: true,
  tracingEnabled: true,
  logLevel: "debug",
  logMaxSizeMB: 10,
};

// ── Service ─────────────────────────────────────────────────────────

export class ConfigService implements vscode.Disposable {
  private static _instance: ConfigService | undefined;
  private readonly _onDidChange = new vscode.EventEmitter<RlmConfig>();
  readonly onDidChange = this._onDidChange.event;

  private _config: RlmConfig = DEFAULTS;
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

    const rawSubBackend = s.get<string>("subBackend", "");
    const rawSubModel = s.get<string>("subModel", "");

    return {
      provider: s.get<LlmProvider>("llmProvider", DEFAULTS.provider),
      backend: s.get<ClientBackend>("backend", DEFAULTS.backend),
      model: s.get<string>("model", DEFAULTS.model),
      baseUrl: s.get<string>("baseUrl", DEFAULTS.baseUrl),
      subBackend: rawSubBackend ? (rawSubBackend as ClientBackend) : undefined,
      subModel: rawSubModel || undefined,
      maxIterations: s.get<number>("maxIterations", DEFAULTS.maxIterations),
      maxOutputChars: s.get<number>("maxOutputChars", DEFAULTS.maxOutputChars),
      pythonPath: s.get<string>("pythonPath", DEFAULTS.pythonPath),
      showIterationDetails: s.get<boolean>("showIterationDetails", DEFAULTS.showIterationDetails),
      tracingEnabled: s.get<boolean>("tracingEnabled", DEFAULTS.tracingEnabled),
      logLevel: s.get<string>("logLevel", DEFAULTS.logLevel),
      logMaxSizeMB: s.get<number>("logMaxSizeMB", DEFAULTS.logMaxSizeMB),
    };
  }
}
