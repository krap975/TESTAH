// Runtime-only secret. Never persist in storage, URLs, logs or VITE_* settings.
let workspaceToken = '';
export function setWorkspaceToken(value: string): void { workspaceToken = value; }
export function workspaceHeaders(): Record<string, string> {
  return workspaceToken ? { 'X-Testah-Workspace-Token': workspaceToken } : {};
}
