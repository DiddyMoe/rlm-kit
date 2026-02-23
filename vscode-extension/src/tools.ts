import * as vscode from "vscode";
import { logger } from "./logger";
import type { RLMChatParticipant } from "./rlmParticipant";
import { formatExecuteToolOutput, truncatePreview } from "./toolsFormatting";

interface AnalyzeInput {
  readonly prompt: string;
  readonly context?: string;
}

interface ExecuteInput {
  readonly code: string;
}

class RlmAnalyzeTool implements vscode.LanguageModelTool<AnalyzeInput> {
  constructor(private readonly participantProvider: () => RLMChatParticipant | null) {}

  prepareInvocation(
    options: vscode.LanguageModelToolInvocationPrepareOptions<AnalyzeInput>,
    _token: vscode.CancellationToken,
  ): Promise<vscode.PreparedToolInvocation> {
    const preview = truncatePreview(options.input.prompt, 120);

    return Promise.resolve({
      invocationMessage: "Running recursive analysis with RLM",
      confirmationMessages: {
        title: "Run recursive RLM analysis",
        message: new vscode.MarkdownString(
          `Analyze this prompt with RLM?\n\n> ${preview}`,
        ),
      },
    });
  }

  async invoke(
    options: vscode.LanguageModelToolInvocationOptions<AnalyzeInput>,
    token: vscode.CancellationToken,
  ): Promise<vscode.LanguageModelToolResult> {
    if (token.isCancellationRequested) {
      throw new Error("RLM analysis tool invocation was cancelled");
    }

    const participant = this.participantProvider();
    if (!participant) {
      throw new Error("RLM participant is not available");
    }

    const text = await participant.runToolCompletion(options.input.prompt, options.input.context);
    return new vscode.LanguageModelToolResult([new vscode.LanguageModelTextPart(text)]);
  }
}

class RlmExecuteTool implements vscode.LanguageModelTool<ExecuteInput> {
  constructor(private readonly participantProvider: () => RLMChatParticipant | null) {}

  prepareInvocation(
    options: vscode.LanguageModelToolInvocationPrepareOptions<ExecuteInput>,
    _token: vscode.CancellationToken,
  ): Promise<vscode.PreparedToolInvocation> {
    const preview = truncatePreview(options.input.code, 160);

    return Promise.resolve({
      invocationMessage: "Executing Python code with RLM REPL",
      confirmationMessages: {
        title: "Execute Python via RLM REPL",
        message: new vscode.MarkdownString(`Run this Python code?\n\n\`\`\`python\n${preview}\n\`\`\``),
      },
    });
  }

  async invoke(
    options: vscode.LanguageModelToolInvocationOptions<ExecuteInput>,
    token: vscode.CancellationToken,
  ): Promise<vscode.LanguageModelToolResult> {
    if (token.isCancellationRequested) {
      throw new Error("RLM execute tool invocation was cancelled");
    }

    const participant = this.participantProvider();
    if (!participant) {
      throw new Error("RLM participant is not available");
    }

    const result = await participant.runToolExecute(options.input.code);
    const output = formatExecuteToolOutput(result);

    return new vscode.LanguageModelToolResult([new vscode.LanguageModelTextPart(output)]);
  }
}

export function registerLanguageModelTools(
  context: vscode.ExtensionContext,
  participantProvider: () => RLMChatParticipant | null,
): void {
  try {
    context.subscriptions.push(
      vscode.lm.registerTool("rlm_analyze", new RlmAnalyzeTool(participantProvider)),
    );
    context.subscriptions.push(
      vscode.lm.registerTool("rlm_execute", new RlmExecuteTool(participantProvider)),
    );

    logger.info("Tools", "Registered language model tools", {
      tools: ["rlm_analyze", "rlm_execute"],
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    logger.error("Tools", "Failed to register language model tools", {
      error: message,
    });
  }
}
