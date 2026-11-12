import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { EnvironmentForm } from '../components/EnvironmentForm';
import { EnvironmentDetails } from '../components/EnvironmentDetails';
import { environmentApi, formatMoney } from '../services/environments';
import type { Environment, EnvironmentSummary, EnvironmentTemplate } from '../types/environments';

export function EnvironmentsPage() {
  const { environmentId } = useParams();
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<EnvironmentTemplate[]>([]);
  const [items, setItems] = useState<EnvironmentSummary[]>([]);
  const [detail, setDetail] = useState<Environment | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(''); setDetail(null); setCreating(false);
    Promise.all([environmentApi.templates(controller.signal), environmentApi.list(offset, controller.signal), environmentId ? environmentApi.get(environmentId, controller.signal) : Promise.resolve(null)])
      .then(([definitions, environments, record]) => { if (!controller.signal.aborted) { setTemplates(definitions); setItems(environments); setDetail(record); } })
      .catch(err => { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Unable to load environments.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [environmentId, offset, revision]);
  return <>
    <div className="page-heading"><div><p className="eyebrow">CONTROLLED SIMULATION DATA</p><h1>Environments</h1><p className="subtitle">Create isolated commerce snapshots from deterministic templates.</p></div><button className="primary-button" disabled={loading || templates.length === 0} onClick={() => setCreating(true)}>New environment</button></div>
    {error && <div className="form-error mb-5" role="alert">{error} <button onClick={() => setRevision(value => value + 1)}>Retry loading</button></div>}
    {loading ? <p role="status" className="muted">Loading environments…</p> : <div className="environment-workspace">
      <section className="panel agent-list" aria-label="Saved environments"><div className="section-header"><h2>Saved environments</h2></div>{items.length === 0 ? <div className="p-6 muted text-sm">{error ? 'The saved environment list could not be loaded.' : offset ? 'No snapshots on this page.' : 'No environments yet. Choose a template to create your first synthetic snapshot.'}</div> : items.map(item => <Link className={'agent-list-item ' + (item.id === environmentId ? 'selected' : '')} key={item.id} to={'/environments/' + item.id}><strong>{item.name}</strong><span>{formatMoney(item.budget_minor, item.currency)} · Compiled</span><span>{item.template_id.replaceAll('_', ' ')}</span></Link>)}<div className="agent-actions p-4"><button disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - 100))}>Previous</button><button disabled={items.length < 100} onClick={() => setOffset(value => value + 100)}>Next</button></div></section>
      <section className="panel" aria-label="Environment workspace">{creating && templates.length > 0 ? <EnvironmentForm templates={templates} onCreated={record => { setCreating(false); navigate('/environments/' + record.id); }} onCancel={() => setCreating(false)} /> : detail ? <EnvironmentDetails environment={detail} /> : <div className="p-6"><h2 className="text-lg">Choose a commerce template</h2><p className="form-help">Every snapshot contains clearly synthetic data. Run assessments against independent copies from the Assessments page.</p><div className="template-grid">{templates.map(template => <article className="template-preview" key={template.id}><span className="eyebrow">VERSION {template.version}</span><h3>{template.name}</h3><p>{template.description}</p><p>Default budget: {formatMoney(template.default_budget_minor, template.default_currency)}</p></article>)}</div><p className="form-help mt-4">Select New environment to customize a template, or choose a saved snapshot for details.</p></div>}</section>
    </div>}
  </>;
}

