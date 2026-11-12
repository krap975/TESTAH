import { lazy, StrictMode, Suspense } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { WorkspaceAccess } from './components/WorkspaceAccess';
import { EnvironmentsPage } from './pages/EnvironmentsPage';
import { AgentsPage } from './pages/AgentsPage';
import { AssessmentsPage } from './pages/AssessmentsPage';
import { RaiDesignerPage } from './pages/RaiDesignerPage';
import { Dashboard } from './pages/Dashboard';
import './styles.css';
const MonitorPage = lazy(() => import('./pages/MonitorPage').then(module => ({ default: module.MonitorPage })));
const ReportsPage = lazy(() => import('./pages/ReportsPage').then(module => ({ default: module.ReportsPage })));
const LogsPage = lazy(() => import('./pages/LogsPage').then(module => ({ default: module.LogsPage })));
const reportsPage = <Suspense fallback={<p role="status">Loading reports…</p>}><ReportsPage /></Suspense>;
const logsPage = <Suspense fallback={<p role="status">Loading evidence…</p>}><LogsPage /></Suspense>;
const monitorPage = <Suspense fallback={<p role="status" className="muted">Loading assessment monitor…</p>}><MonitorPage /></Suspense>;
createRoot(document.getElementById('root')!).render(<StrictMode><WorkspaceAccess><BrowserRouter><Routes><Route element={<Layout />}>
  <Route index element={<Dashboard />} />
  <Route path="environments" element={<EnvironmentsPage />} /><Route path="environments/:environmentId" element={<EnvironmentsPage />} />
  <Route path="agents" element={<AgentsPage />} /><Route path="agents/:agentId" element={<AgentsPage />} />
  <Route path="assessments" element={<AssessmentsPage />} /><Route path="assessments/:runId" element={<AssessmentsPage />} />
  <Route path="monitor" element={monitorPage} /><Route path="monitor/:runId" element={monitorPage} />
  <Route path="rai" element={<RaiDesignerPage />} /><Route path="rai/:proposalId" element={<RaiDesignerPage />} />
  <Route path="reports" element={reportsPage} /><Route path="reports/:runId" element={reportsPage} /><Route path="logs" element={logsPage} />
  <Route path="*" element={<div className="panel p-8"><h1>Page not found</h1><Link to="/">Return to dashboard</Link></div>} />
</Route></Routes></BrowserRouter></WorkspaceAccess></StrictMode>);
