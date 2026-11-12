import type { GridApi } from 'ag-grid-community';
import type { RunEvent } from '../types/assessments';

/** A finding selection owns the investigation view; old filters cannot hide it. */
export function revealEvidence(api: GridApi<RunEvent>, eventId: string): boolean {
  if (api.isDestroyed()) return false;
  api.setGridOption('quickFilterText', ''); api.setFilterModel(null);
  api.applyColumnState({ defaultState: { sort: null }, state: [{ colId: 'sequence', sort: 'asc' }] });
  api.onFilterChanged();
  const node = api.getRowNode(eventId);
  if (!node || node.rowIndex === null) return false;
  api.paginationGoToPage(Math.floor(node.rowIndex / api.paginationGetPageSize()));
  api.ensureNodeVisible(node, 'top'); api.setFocusedCell(node.rowIndex, 'sequence');
  return true;
}
