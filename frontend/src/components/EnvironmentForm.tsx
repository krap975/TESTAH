import { useState, type FormEvent } from 'react';
import { environmentApi, formatMoney, parseMinorUnits } from '../services/environments';
import type { Currency, Environment, EnvironmentTemplate } from '../types/environments';

export function EnvironmentForm({ templates, onCreated, onCancel }: { templates: EnvironmentTemplate[]; onCreated: (environment: Environment) => void; onCancel: () => void }) {
  const [templateId, setTemplateId] = useState(templates[0].id);
  const selected = templates.find(item => item.id === templateId)!;
  const [name, setName] = useState('');
  const [budget, setBudget] = useState((selected.default_budget_minor / 100).toFixed(2));
  const [currency, setCurrency] = useState<Currency>(selected.default_currency);
  const [customer, setCustomer] = useState(selected.customer.name);
  const [objective, setObjective] = useState(selected.objective);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  function selectTemplate(id: string) {
    const next = templates.find(item => item.id === id)!;
    setTemplateId(id); setBudget((next.default_budget_minor / 100).toFixed(2)); setCurrency(next.default_currency);
    setCustomer(next.customer.name); setObjective(next.objective); setError('');
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); setError('');
    const minor = parseMinorUnits(budget);
    if (!name.trim() || !customer.trim() || !objective.trim()) { setError('Enter a name, a synthetic customer name, and an objective.'); return; }
    if (minor === null || minor < selected.min_budget_minor || minor > selected.max_budget_minor) {
      setError('Enter a budget between ' + formatMoney(selected.min_budget_minor, currency) + ' and ' + formatMoney(selected.max_budget_minor, currency) + ' with at most two decimal places.'); return;
    }
    setBusy(true);
    try { onCreated(await environmentApi.create({name: name.trim(), template_id: selected.id, template_version: selected.version, currency, budget_minor: minor, customer_name: customer.trim(), objective: objective.trim()})); }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to create the environment.'); }
    finally { setBusy(false); }
  }
  return <form className="agent-form" onSubmit={submit} aria-label="Create environment">
    <h2>Compile a commerce environment</h2>
    <p className="form-help">Choose a deterministic template. The server stores an independent synthetic snapshot.</p>
    <label>Template<select value={templateId} onChange={e => selectTemplate(e.target.value)} disabled={busy}>{templates.map(item => <option key={item.id} value={item.id}>{item.name} · v{item.version}</option>)}</select></label>
    <p className="form-help">{selected.description}</p>
    <label>Environment name<input required maxLength={100} value={name} onChange={e => setName(e.target.value)} disabled={busy} placeholder="My commerce scenario" /></label>
    <div className="environment-form-grid"><label>Currency<select value={currency} onChange={e => setCurrency(e.target.value as Currency)} disabled={busy}>{selected.supported_currencies.map(code => <option key={code}>{code}</option>)}</select></label>
    <label>Budget<input required inputMode="decimal" value={budget} onChange={e => setBudget(e.target.value)} disabled={busy} maxLength={12} aria-describedby="budget-help" /></label></div>
    <p id="budget-help" className="form-help">{formatMoney(selected.min_budget_minor, currency)}–{formatMoney(selected.max_budget_minor, currency)}. Synthetic catalog prices scale with this budget; currencies are nominal simulation units.</p>
    <label>Synthetic customer name<input value={customer} onChange={e => setCustomer(e.target.value)} required maxLength={100} disabled={busy} /></label>
    <label>Purchasing objective<textarea value={objective} onChange={e => setObjective(e.target.value)} required maxLength={1000} rows={3} disabled={busy} /></label>
    <div className="template-facts"><span>{selected.allowed_tools.length} tool definitions</span><span>{selected.challenge_summaries.length} challenge definitions</span><span>Budget and approval policies required</span></div>
    {error && <p role="alert" className="form-error mt-4">{error}</p>}
    <div className="agent-actions"><button type="submit" className="primary-button" disabled={busy}>{busy ? 'Creating…' : 'Create environment'}</button><button type="button" onClick={onCancel} disabled={busy}>Cancel</button></div>
  </form>;
}

