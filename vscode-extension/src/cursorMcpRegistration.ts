import * as vscode from "vscode";
import { logger } from "./logger";

const CURSOR_SERVER_NAME = "rlm-gateway";

type CursorStdioServerConfig = {
  name: string;
  server: {
    command: string;
    args: readonly string[];
    env?: Record<string, string>;
  };
};

type CursorMcpApi = {
  registerServer(config: CursorStdioServerConfig): void;
  unregisterServer(name: string): void;
};

function getWorkspaceRoot(): string | undefined {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}

function getCursorMcpApi(): CursorMcpApi | undefined {
  const vscodeRecord = vscode as unknown as Record<string, unknown>;
  const cursorNamespace = vscodeRecord["cursor"];
  if (typeof cursorNamespace !== "object" || cursorNamespace === null) {
    return undefined;
  }

  const mcpNamespace = (cursorNamespace as Record<string, unknown>)["mcp"];
  if (typeof mcpNamespace !== "object" || mcpNamespace === null) {
    return undefined;
  }

  const registerServer = (mcpNamespace as Record<string, unknown>)["registerServer"];
  const unregisterServer = (mcpNamespace as Record<string, unknown>)["unregisterServer"];
  if (typeof registerServer !== "function" || typeof unregisterServer !== "function") {
    return undefined;
  }

  return mcpNamespace as unknown as CursorMcpApi;
}

export function registerCursorMcpServer(context: vscode.ExtensionContext): void {
  const cursorMcpApi = getCursorMcpApi();
  if (cursorMcpApi === undefined) {
    logger.info("MCP", "Cursor MCP registration API unavailable");
    return;
  }

  const workspaceRoot = getWorkspaceRoot();
  if (workspaceRoot === undefined) {
    logger.warn("MCP", "Skipping Cursor MCP registration because no workspace is open");
    return;
  }

  const config: CursorStdioServerConfig = {
    name: CURSOR_SERVER_NAME,
    server: {
      command: "uv",
      args: ["run", "python", "scripts/rlm_mcp_gateway.py"],
      env: {
        PYTHONPATH: workspaceRoot,
      },
    },
  };

  cursorMcpApi.registerServer(config);
  logger.info("MCP", "Registered Cursor MCP server", {
    server: CURSOR_SERVER_NAME,
    workspaceRoot,
  });

  context.subscriptions.push({
    dispose: () => {
      cursorMcpApi.unregisterServer(CURSOR_SERVER_NAME);
      logger.info("MCP", "Unregistered Cursor MCP server", {
        server: CURSOR_SERVER_NAME,
      });
    },
  });
}
