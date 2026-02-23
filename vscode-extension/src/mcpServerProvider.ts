import * as vscode from "vscode";
import { logger } from "./logger";

const PROVIDER_ID = "rlm-chat.rlmMcpServer";
const SERVER_LABEL = "rlm-gateway";
const SERVER_COMMAND = "uv";
const SERVER_ARGS = ["run", "python", "scripts/rlm_mcp_gateway.py"];

type LmApiWithMcpProvider = {
  registerMcpServerDefinitionProvider(
    id: string,
    provider: {
      provideMcpServerDefinitions(
        token: vscode.CancellationToken,
      ): vscode.ProviderResult<vscode.McpServerDefinition[]>;
    },
  ): vscode.Disposable;
};

function hasMcpServerDefinitionProviderApi(lmApi: unknown): lmApi is LmApiWithMcpProvider {
  if (typeof lmApi !== "object" || lmApi === null) {
    return false;
  }
  const registerApi = (lmApi as Record<string, unknown>)["registerMcpServerDefinitionProvider"];
  return typeof registerApi === "function";
}

function getWorkspaceRoot(): string | undefined {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}

export function registerRlmMcpServerDefinitionProvider(context: vscode.ExtensionContext): void {
  if (!hasMcpServerDefinitionProviderApi(vscode.lm)) {
    logger.info("MCP", "MCP server provider API unavailable");
    return;
  }

  const provider = {
    provideMcpServerDefinitions: (_token: vscode.CancellationToken): vscode.McpServerDefinition[] => {
      const workspaceRoot = getWorkspaceRoot();
      if (workspaceRoot === undefined) {
        logger.warn("MCP", "Skipping MCP server registration because no workspace is open");
        return [];
      }

      const definition: vscode.McpStdioServerDefinition = {
        label: SERVER_LABEL,
        command: SERVER_COMMAND,
        args: SERVER_ARGS,
        cwd: vscode.Uri.file(workspaceRoot),
        env: {},
      };
      return [definition];
    },
  };

  const registration = vscode.lm.registerMcpServerDefinitionProvider(PROVIDER_ID, provider);
  context.subscriptions.push(registration);
  logger.info("MCP", "Registered MCP server definition provider", {
    providerId: PROVIDER_ID,
    command: SERVER_COMMAND,
    args: SERVER_ARGS,
  });
}
