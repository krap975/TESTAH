import type { Assessment, RunEvent, RunStatus } from '../types/assessments';
import { apiUrl } from './api';
import { workspaceHeaders } from './workspaceAccess';

export type ConnectionStatus = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'settled' | 'error';
export const terminalStates = new Set<RunStatus>(['completed', 'failed', 'cancelled', 'inconclusive']);
const states = new Set(['created', 'running', ...terminalStates]);
const MAX_FRAME = 262144;
export class StreamProtocolError extends Error {}
interface Frame { event: string; id: string; data: string }

/** Incremental SSE decoder: supports split UTF-8 (at caller), CR/LF and multiline data. */
export class SseParser {
  private buffer = ''; private event = ''; private id = ''; private data: string[] = []; private size = 0;
  constructor(private emit: (frame: Frame) => void) {}
  feed(chunk: string) {
    this.buffer += chunk;
    for (;;) {
      const match = /\r\n|\n|\r(?!$)/.exec(this.buffer);
      if (!match) break;
      const line = this.buffer.slice(0, match.index);
      this.buffer = this.buffer.slice(match.index + match[0].length);
      this.size += line.length;
      if (this.size > MAX_FRAME) throw new StreamProtocolError('A stream frame exceeded the safety limit.');
      if (line === '') {
        if (this.data.length) this.emit({ event: this.event || 'message', id: this.id, data: this.data.join('\n') });
        this.event = ''; this.id = ''; this.data = []; this.size = 0;
      } else if (!line.startsWith(':')) {
        const colon = line.indexOf(':');
        const field = colon < 0 ? line : line.slice(0, colon);
        let value = colon < 0 ? '' : line.slice(colon + 1);
        if (value.startsWith(' ')) value = value.slice(1);
        if (field === 'event') this.event = value;
        if (field === 'id') { if (value.includes('\0')) throw new StreamProtocolError('Invalid event cursor.'); this.id = value; }
        if (field === 'data') this.data.push(value);
      }
    }
    if (this.size + this.buffer.length > MAX_FRAME) throw new StreamProtocolError('A stream frame exceeded the safety limit.');
  }
  finish() { if (this.buffer.endsWith('\r')) this.feed('\n'); }
}

const object = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const text = (value: unknown, limit = 128): value is string => typeof value === 'string' && value.length > 0 && value.length <= limit;
const integer = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
const date = (value: unknown): value is string => text(value) && Number.isFinite(Date.parse(value));
const nullableText = (value: unknown) => value === null || text(value);

export function parseRun(value: unknown, runId: string): Assessment {
  if (!object(value) || value.id !== runId || !text(value.status) || !states.has(value.status) ||
      !integer(value.event_sequence) || !text(value.agent_id) || !text(value.environment_id) ||
      !text(value.agent_name, 16000) || !text(value.environment_name, 16000) || !date(value.created_at) ||
      !(value.started_at === null || date(value.started_at)) || !(value.ended_at === null || date(value.ended_at)) ||
      !nullableText(value.termination_reason) || !nullableText(value.failure_origin) ||
      !['deterministic', 'rai'].includes(String(value.examiner_mode)) || !text(value.examiner_provider) ||
      !nullableText(value.examiner_model) || !text(value.protocol_version) ||
      !['simulated', 'paypal_sandbox'].includes(String(value.payment_mode))) throw new StreamProtocolError('Invalid assessment snapshot.');
  return value as unknown as Assessment;
}

export function parseRunEvent(value: unknown, runId: string, frameId: string): RunEvent {
  if (!object(value) || !text(value.id) || value.id !== frameId || value.run_id !== runId ||
      !integer(value.sequence) || value.sequence < 1 || !date(value.created_at) ||
      !text(value.event_type, 80) || !/^[a-z][a-z0-9_.]*$/.test(value.event_type) ||
      !nullableText(value.correlation_id) || !object(value.payload)) throw new StreamProtocolError('Invalid assessment event.');
  return value as unknown as RunEvent;
}

/** Accepted prefix is the only reconnect cursor. Never advance on malformed/gapped data. */
export class EventHistory {
  events: RunEvent[] = [];
  private byId = new Map<string, RunEvent>(); private characters = 0;
  constructor(readonly runId: string) {}
  get sequence() { return this.events.at(-1)?.sequence ?? 0; }
  get lastId() { return this.events.at(-1)?.id; }
  accept(event: RunEvent): boolean {
    const existing = this.byId.get(event.id);
    if (event.run_id !== this.runId) throw new StreamProtocolError('An event belongs to another assessment.');
    if (existing) {
      if (JSON.stringify(existing) !== JSON.stringify(event)) throw new StreamProtocolError('Conflicting stable event identifier.');
      return false;
    }
    if (event.sequence !== this.sequence + 1) throw new StreamProtocolError('Event history has a gap or conflicting sequence. Reconnect from the beginning.');
    const size = JSON.stringify(event).length;
    if (this.events.length >= 5000 || this.characters + size > 8 * 1024 * 1024) throw new StreamProtocolError('This history exceeds the monitor display limit. Use paginated REST history.');
    this.events.push(event); this.byId.set(event.id, event); this.characters += size;
    return true;
  }
}

interface Callbacks {
  onStatus: (status: ConnectionStatus) => void;
  onRun: (run: Assessment) => void;
  onEvent: (event: RunEvent) => void;
  onError: (message: string) => void;
}
interface Options { fetcher?: typeof fetch; wait?: (ms: number, signal: AbortSignal) => Promise<void>; idleMs?: number }
export function abortableDelay(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise(resolve => {
    if (signal.aborted) { resolve(); return; }
    const done = () => { clearTimeout(timer); signal.removeEventListener('abort', done); resolve(); };
    const timer = setTimeout(done, ms); signal.addEventListener('abort', done, { once: true });
  });
}

export async function watchAssessment(runId: string, token: string, signal: AbortSignal, callbacks: Callbacks, options: Options = {}): Promise<void> {
  const history = new EventHistory(runId); let attempt = 0;
  const fetcher = options.fetcher ?? fetch; const wait = options.wait ?? abortableDelay;
  while (!signal.aborted) {
    callbacks.onStatus(attempt ? 'reconnecting' : 'connecting');
    const connection = new AbortController(); let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
    let timer = setTimeout(() => connection.abort(), 10000); let settled = false; let run: Assessment | null = null;
    try {
      const response = await fetcher(apiUrl('/api/assessments/' + encodeURIComponent(runId) + '/stream?after_sequence=' + history.sequence), {
        headers: { Accept: 'text/event-stream', ...workspaceHeaders(), Authorization: 'Bearer ' + token, ...(history.lastId ? { 'Last-Event-ID': history.lastId } : {}) },
        credentials: 'omit', cache: 'no-store', referrerPolicy: 'no-referrer', signal: AbortSignal.any([signal, connection.signal]),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null) as { error?: { code?: string } } | null;
        if ([401, 403, 404, 422].includes(response.status) || body?.error?.code === 'monitor_not_configured')
          throw new StreamProtocolError(response.status === 401 || response.status === 403 ? 'Monitoring authentication failed. Re-enter the monitoring token.' : body?.error?.code === 'monitor_not_configured' ? 'Monitoring is not configured on the API. Set TESTAH_MONITOR_TOKEN and restart.' : 'The assessment or resume cursor is unavailable.');
        throw new Error('Stream unavailable');
      }
      if (!response.headers.get('content-type')?.startsWith('text/event-stream') || !response.body) throw new StreamProtocolError('The API did not return an event stream.');
      callbacks.onStatus('connected'); callbacks.onError('');
      const parser = new SseParser(frame => {
        if (!['snapshot', 'assessment_event', 'settled', 'stream_error'].includes(frame.event)) return;
        let data: unknown;
        try { data = JSON.parse(frame.data); } catch { throw new StreamProtocolError('Malformed event-stream JSON.'); }
        if (frame.event === 'snapshot') {
          if (!object(data)) throw new StreamProtocolError('Invalid assessment snapshot.');
          run = parseRun(data.run, runId); callbacks.onRun(run);
        } else if (frame.event === 'assessment_event') {
          const event = parseRunEvent(data, runId, frame.id);
          if (history.accept(event)) callbacks.onEvent(event);
          attempt = 0;
        } else if (frame.event === 'settled') {
          if (!object(data) || data.run_id !== runId || data.last_sequence !== history.sequence || !run ||
              data.status !== run.status || !terminalStates.has(run.status) || run.event_sequence !== history.sequence)
            throw new StreamProtocolError('Invalid terminal stream marker.');
          settled = true;
        } else {
          if (object(data) && data.code === 'event_store_unavailable') throw new Error('Event storage unavailable');
          throw new StreamProtocolError('The stream stopped safely. Reload persisted history or reconnect.');
        }
      });
      reader = response.body.getReader(); const decoder = new TextDecoder('utf-8', { fatal: true });
      for (;;) {
        clearTimeout(timer); timer = setTimeout(() => connection.abort(), options.idleMs ?? 45000);
        const { value, done } = await reader.read();
        if (done) {
          try { parser.feed(decoder.decode()); parser.finish(); }
          catch (error) { if (error instanceof StreamProtocolError) throw error; throw new StreamProtocolError('Invalid UTF-8 event stream.'); }
          break;
        }
        try { parser.feed(decoder.decode(value, { stream: true })); }
        catch (error) { if (error instanceof StreamProtocolError) throw error; throw new StreamProtocolError('Invalid UTF-8 event stream.'); }
        if (settled) { callbacks.onStatus('settled'); return; }
      }
      if (settled) { callbacks.onStatus('settled'); return; }
      throw new Error('Stream interrupted');
    } catch (error) {
      if (signal.aborted) return;
      if (error instanceof StreamProtocolError) { callbacks.onStatus('error'); callbacks.onError(error.message); return; }
      callbacks.onStatus('reconnecting'); callbacks.onError('Monitoring connection interrupted. Resuming from the last accepted event…');
    } finally {
      clearTimeout(timer); connection.abort();
      if (reader) { await reader.cancel().catch(() => undefined); reader.releaseLock(); }
    }
    attempt += 1;
    await wait(Math.min(10000, 1000 * 2 ** Math.min(attempt - 1, 4)), signal);
  }
}
