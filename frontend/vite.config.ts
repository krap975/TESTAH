import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ command, mode }) => {
  if (command === 'build' && process.env.RENDER === 'true') {
    const value = loadEnv(mode, process.cwd(), 'VITE_').VITE_API_BASE_URL ?? '';
    let valid = false;
    try {
      const url = new URL(value);
      valid = url.protocol === 'https:' && url.origin === value.replace(/\/$/, '') &&
        !url.username && !url.password && (!url.port || url.port === '443') &&
        /^[a-z0-9.-]+\.[a-z]{2,63}$/.test(url.hostname) &&
        !url.hostname.endsWith('.localhost') && !url.hostname.endsWith('.local') &&
        !url.hostname.endsWith('.internal');
    } catch { /* Never include the supplied URL in the error. */ }
    if (!valid) throw new Error('Render requires VITE_API_BASE_URL to be the exact public HTTPS API origin.');
  }
  return { plugins: [react()] };
});
