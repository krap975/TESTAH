import { useState, type FormEvent, type ReactNode } from 'react';
import { apiGet } from '../services/api';
import { setWorkspaceToken } from '../services/workspaceAccess';

export function WorkspaceAccess({ children }: { children: ReactNode }) {
  const required = import.meta.env?.PROD === true || import.meta.env?.VITE_REQUIRE_WORKSPACE_ACCESS === 'true';
  const [authorized, setAuthorized] = useState(false);
  const [token, setToken] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  if (!required) return <>{children}</>;
  const leave = () => { setWorkspaceToken(''); setAuthorized(false); };
  async function enter(event: FormEvent) {
    event.preventDefault(); setPending(true); setError(''); setWorkspaceToken(token);
    try {
      await apiGet('/api/agents');
      setToken(''); setAuthorized(true);
    } catch {
      setWorkspaceToken('');
      setError('Workspace access could not be verified. Check the token and API availability, then retry.');
    } finally { setPending(false); }
  }
  if (authorized) return <><div className="workspace-banner">Shared demo workspace <button type="button" onClick={leave}>Lock workspace</button></div>{children}</>;
  return <main className="workspace-login panel">
    <h1>Testah demo workspace</h1>
    <p>Enter the access token provided by the demo operator. Invited users share this workspace and its assessment records.</p>
    <form onSubmit={enter}>
      <label htmlFor="workspace-token">Workspace access token</label>
      <input id="workspace-token" type="password" autoComplete="off" required minLength={32} maxLength={512} value={token} onChange={event => setToken(event.target.value)} />
      <button type="submit" disabled={pending}>{pending ? 'Verifying access...' : 'Open workspace'}</button>
    </form>
    <p>The token stays in memory until the page is refreshed or locked. Monitoring and Sandbox payments require their separate operator tokens.</p>
    {error && <p role="alert">{error}</p>}
  </main>;
}
