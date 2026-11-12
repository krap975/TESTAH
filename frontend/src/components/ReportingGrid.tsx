import { ClientSideRowModelModule, ClientSideRowModelApiModule, TextFilterModule, NumberFilterModule, DateFilterModule,
  QuickFilterModule, PaginationModule, PaginationPageNumbersModule, ColumnApiModule, RowApiModule, ScrollApiModule,
  RowAutoHeightModule, TooltipModule, colorSchemeDark, ModuleRegistry, themeQuartz } from 'ag-grid-community';
import type { ColDef, GridApi, GridReadyEvent } from 'ag-grid-community';
import { AgGridReact } from 'ag-grid-react';

// Register only the Community modules used by reporting; no Enterprise dependency.
const modules = [ClientSideRowModelModule, ClientSideRowModelApiModule, TextFilterModule, NumberFilterModule, DateFilterModule,
  QuickFilterModule, PaginationModule, PaginationPageNumbersModule, ColumnApiModule, RowApiModule, ScrollApiModule, RowAutoHeightModule, TooltipModule];
ModuleRegistry.registerModules(modules);
const theme = themeQuartz.withPart(colorSchemeDark).withParams({
  backgroundColor: '#101720', foregroundColor: '#e9eef3', headerBackgroundColor: '#17222d',
  borderColor: '#2e3c4c', accentColor: '#b7f775', fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif',
  fontSize: 12, rowHeight: 46, headerHeight: 44, wrapperBorderRadius: 8,
});

export interface ReportingGridProps<T> {
  rows: T[]; columns: ColDef<T>[]; label: string; rowId: (row: T) => string;
  ready?: (api: GridApi<T>) => void; updated?: (api: GridApi<T>) => void;
}
export function ReportingGrid<T>({ rows, columns, label, rowId, ready, updated }: ReportingGridProps<T>) {
  return <div className="report-grid screen-only" role="region" aria-label={label}>
    <AgGridReact<T> theme={theme} modules={modules} rowData={rows} columnDefs={columns}
      getRowId={params => rowId(params.data)} defaultColDef={{ sortable: true, filter: true, resizable: true, minWidth: 110, flex: 1 }}
      pagination paginationPageSize={25} paginationPageSizeSelector={[25, 50, 100]} animateRows={false}
      suppressCellFocus={false} ensureDomOrder enableCellTextSelection
      overlayNoRowsTemplate="No recorded rows match this selection."
      onGridReady={(event: GridReadyEvent<T>) => ready?.(event.api)}
      onRowDataUpdated={event => updated?.(event.api)} />
  </div>;
}
