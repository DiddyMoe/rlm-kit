export interface ExecuteToolResult {
  readonly stdout: string;
  readonly stderr: string;
  readonly error: boolean;
}

export function truncatePreview(text: string, maxChars: number): string {
  if (text.length <= maxChars) {
    return text;
  }
  return `${text.slice(0, maxChars)}...`;
}

export function formatExecuteToolOutput(result: ExecuteToolResult): string {
  const status = result.error ? "error" : "ok";
  return [
    `status: ${status}`,
    `stdout:\n${result.stdout || "(empty)"}`,
    `stderr:\n${result.stderr || "(empty)"}`,
  ].join("\n\n");
}
