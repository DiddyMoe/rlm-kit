export type EditorKind = "vscode" | "cursor" | "unknown";

export function detectEditorKind(
  appName: string,
  uriScheme: string,
  hasLanguageModelApi: boolean,
): EditorKind {
  const normalizedAppName = appName.toLowerCase();
  const normalizedUriScheme = uriScheme.toLowerCase();

  if (normalizedAppName.includes("cursor") || normalizedUriScheme.startsWith("cursor")) {
    return "cursor";
  }
  if (hasLanguageModelApi) {
    return "vscode";
  }
  return "unknown";
}
