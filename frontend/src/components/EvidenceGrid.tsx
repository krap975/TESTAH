import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ColDef, GridApi, ICellRendererParams } from 'ag-grid-community';
import type { RunEvent } from '../types/assessments';
import type { EvidenceRequest } from '../types/reports';
import { describeEvent } from '../services/assessmentGraph';
import { revealEvidence } from '../services/evidenceSelection';
import { ReportingGrid } from './ReportingGrid';

export function EvidenceGrid({ events, request, selectedId, select, label = 'Execution evidence' }: {
  events: RunEvent[]; request?: EvidenceRequest; selectedId?: string; select?: (id: string) => void; label?: string;
}) {
  const api = useRef<GridApi<RunEvent> | null>(null);
  const target = useRef<string | undefined>(undefined);
  const [quick, setQuick] = useState(''); const [scope, setScope] = useState<string[] | null>(null);
  const [localId, setLocalId] = useState<string>(); const [missing, setMissing] = useState(0);
  const inspect = useCallback((id: string) => { setLocalId(id); select?.(id); }, [select]);
  const rows = useMemo(() => scope ? events.filter(e => scope.includes(e.id)) : events, [events, scope]);
  const selected = events.find(e => e.id === (selectedId ?? localId));
  const locate = useCallback((grid: GridApi<RunEvent>) => { if (target.current) revealEvidence(grid, target.current); }, []);
  useEffect(() => {
    if (!request) return;
    const available = request.ids.filter(id => events.some(e => e.id === id));
    setQuick(''); setScope(request.ids); setMissing(request.ids.length - available.length);
    target.current = available[0];
    if (available[0]) { setLocalId(available[0]); select?.(available[0]); }
    if (api.current && !api.current.isDestroyed()) {
      api.current.setGridOption('quickFilterText', ''); api.current.setFilterModel(null);
      // Re-selecting the same finding may leave rowData unchanged. Reveal now as
      // well as after row updates, so existing pagination can never hide it.
      if (available[0]) revealEvidence(api.current, available[0]);
    }
  }, [request, events, select]);
  useEffect(() => { if (api.current && !api.current.isDestroyed()) api.current.setGridOption('quickFilterText', quick); }, [quick]);
  const columns = useMemo<ColDef<RunEvent>[]>(() => [
    { field: 'sequence', headerName: '#', width: 85, minWidth: 75, flex: 0, sort: 'asc', filter: 'agNumberColumnFilter',
      getQuickFilterText: p => `${p.data?.sequence ?? ''} ${p.data?.id ?? ''}` },
    { field: 'created_at', headerName: 'Recorded time', minWidth: 175, valueFormatter: p => new Date(p.value).toLocaleString() },
    { field: 'event_type', headerName: 'Event', minWidth: 200 },
    { colId: 'summary', headerName: 'Action / summary', minWidth: 260,
      valueGetter: p => p.data ? (typeof p.data.payload.name === 'string' ? p.data.payload.name + ' · ' : '') + describeEvent(p.data).description : '' },
    { colId: 'actor', headerName: 'Actor', minWidth: 150, valueGetter: p => p.data ? describeEvent(p.data).actor : '' },
    { field: 'correlation_id', headerName: 'Correlation', minWidth: 130 },
    { colId: 'outcome', headerName: 'Recorded outcome', valueGetter: p => p.data ? describeEvent(p.data).outcome : '' },
    { colId: 'inspect', headerName: 'Evidence', width: 115, minWidth: 115, flex: 0, sortable: false, filter: false,
      cellRenderer: (p: ICellRendererParams<RunEvent>) => p.data ? <button type="button" className="grid-action" aria-label={'Inspect event ' + p.data.sequence} onClick={() => inspect(p.data!.id)}>Inspect</button> : null },
  ], [inspect]);
  return <section className="report-evidence" aria-label={label} id="report-evidence">
    <div className="report-section-heading"><div><p className="eyebrow">INVESTIGATE</p><h2>{label}</h2></div><span className="muted">{rows.length} / {events.length} loaded events</span></div>
    <div className="report-grid-toolbar screen-only"><label>Search evidence<input value={quick} onChange={e => { target.current = undefined; setQuick(e.target.value); }} placeholder="Event type, actor, correlation…" /></label>
      <button onClick={() => { setScope(null); setQuick(''); setMissing(0); target.current = undefined; if (api.current && !api.current.isDestroyed()) { api.current.setFilterModel(null); api.current.setGridOption('quickFilterText', ''); } }}>Show all evidence / clear filters</button></div>
    {scope && <p role="status" className="form-help screen-only">Showing supporting events for the selected finding. Existing filters were cleared.</p>}
    {missing > 0 && <p role="alert" className="form-error">{missing} referenced event(s) are unavailable in the loaded evidence.</p>}
    <ReportingGrid rows={rows} columns={columns} label={label + ' table'} rowId={row => row.id} ready={grid => { api.current = grid; locate(grid); }} updated={locate} />
    <section className="report-inspector screen-only" aria-label="Selected evidence details" aria-live="polite">
      {selected ? <><div className="report-section-heading"><h3>#{selected.sequence} · {selected.event_type}</h3><button onClick={() => navigator.clipboard?.writeText(selected.id)}>Copy event ID</button></div>
        <p>{describeEvent(selected).description}</p><p className="form-help">Event {selected.id} · {new Date(selected.created_at).toLocaleString()}{selected.correlation_id ? ' · Correlation ' + selected.correlation_id : ''}</p>
        <pre>{JSON.stringify(selected.payload, null, 2)}</pre></> : <p className="muted">Choose Inspect to view an event’s sanitized payload and identifiers.</p>}
    </section>
  </section>;
}
