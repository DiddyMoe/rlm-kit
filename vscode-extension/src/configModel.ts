import type { ClientBackend, LlmProvider, RlmEnvironment } from "./types";

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
  readonly environment: RlmEnvironment;
  readonly tracingEnabled: boolean;
  readonly logLevel: string;
  readonly logMaxSizeMB: number;
}

export interface RawRlmConfig {
  readonly provider?: LlmProvider | undefined;
  readonly backend?: ClientBackend | undefined;
  readonly model?: string | undefined;
  readonly baseUrl?: string | undefined;
  readonly subBackend?: string | undefined;
  readonly subModel?: string | undefined;
  readonly maxIterations?: number | undefined;
  readonly maxOutputChars?: number | undefined;
  readonly pythonPath?: string | undefined;
  readonly showIterationDetails?: boolean | undefined;
  readonly environment?: string | undefined;
  readonly tracingEnabled?: boolean | undefined;
  readonly logLevel?: string | undefined;
  readonly logMaxSizeMB?: number | undefined;
}

export const DEFAULT_RLM_CONFIG: RlmConfig = {
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
  environment: "local",
  tracingEnabled: true,
  logLevel: "debug",
  logMaxSizeMB: 10,
};

function withDefault<T>(value: T | undefined, fallback: T): T {
  return value ?? fallback;
}

function normalizeSubBackend(rawSubBackend: string | undefined): ClientBackend | undefined {
  if (!rawSubBackend) {
    return undefined;
  }
  return rawSubBackend as ClientBackend;
}

function normalizeSubModel(rawSubModel: string | undefined): string | undefined {
  return rawSubModel || undefined;
}

const VALID_ENVIRONMENTS = new Set(["local", "docker", "modal", "daytona", "prime", "e2b"]);

function normalizeEnvironment(rawEnvironment: string | undefined): RlmEnvironment {
  if (rawEnvironment && VALID_ENVIRONMENTS.has(rawEnvironment)) {
    return rawEnvironment as RlmEnvironment;
  }
  return DEFAULT_RLM_CONFIG.environment;
}

export function normalizeRlmConfig(raw: RawRlmConfig): RlmConfig {
  const normalizedSubBackend = normalizeSubBackend(raw.subBackend);
  const normalizedSubModel = normalizeSubModel(raw.subModel);

  return {
    provider: withDefault(raw.provider, DEFAULT_RLM_CONFIG.provider),
    backend: withDefault(raw.backend, DEFAULT_RLM_CONFIG.backend),
    model: withDefault(raw.model, DEFAULT_RLM_CONFIG.model),
    baseUrl: withDefault(raw.baseUrl, DEFAULT_RLM_CONFIG.baseUrl),
    subBackend: normalizedSubBackend,
    subModel: normalizedSubModel,
    maxIterations: withDefault(raw.maxIterations, DEFAULT_RLM_CONFIG.maxIterations),
    maxOutputChars: withDefault(raw.maxOutputChars, DEFAULT_RLM_CONFIG.maxOutputChars),
    pythonPath: withDefault(raw.pythonPath, DEFAULT_RLM_CONFIG.pythonPath),
    showIterationDetails: withDefault(
      raw.showIterationDetails,
      DEFAULT_RLM_CONFIG.showIterationDetails,
    ),
    environment: normalizeEnvironment(raw.environment),
    tracingEnabled: withDefault(raw.tracingEnabled, DEFAULT_RLM_CONFIG.tracingEnabled),
    logLevel: withDefault(raw.logLevel, DEFAULT_RLM_CONFIG.logLevel),
    logMaxSizeMB: withDefault(raw.logMaxSizeMB, DEFAULT_RLM_CONFIG.logMaxSizeMB),
  };
}
