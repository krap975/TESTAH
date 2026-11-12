import { formatMoney } from '../services/environments';
import type { ProposalEvent, RaiProposal } from '../types/rai';
export function RaiProposalDetails({ proposal, events }: { proposal: RaiProposal; events: ProposalEvent[] }) {
  const bp = proposal.preview;
  return <div className="environment-details p-6">
    <p className="eyebrow">REVIEW BEFORE COMPILATION</p><h2 className="text-xl mt-3">RAI environment proposal</h2>
    <p className="snapshot-status">{proposal.is_mock ? 'MOCK MODE · Deterministic generation, no LLM used' : 'REAL LLM PROVIDER · ' + proposal.provider} · {proposal.model}</p>
    <dl className="agent-facts mt-5"><dt>Proposal ID</dt><dd>{proposal.id}</dd><dt>Status</dt><dd>{proposal.status}</dd><dt>Validation</dt><dd>{proposal.validation.code}</dd><dt>Agent ID</dt><dd>{proposal.agent_id}</dd><dt>Created</dt><dd>{new Date(proposal.created_at).toLocaleString()}</dd></dl>
    <section><h3>Capability uncertainty</h3><p>{proposal.capability_summary.declared_description || 'No declared capability description.'}</p><ul className="preview-list">{proposal.capability_summary.uncertainties.map(item => <li key={item}>{item}</li>)}</ul><p>{proposal.capability_summary.tool_interface_source}</p></section>
    {proposal.status === 'generating' && <p role="status" className="form-help">Generation is running. The proposal will be validated before it can be compiled.</p>}
    {proposal.status === 'failed' && <div role="alert" className="form-error mt-5"><p>Generation failed: <code>{proposal.validation.code}</code>.</p><p>{proposal.validation.message ?? 'Review the provider check and retry generation.'}</p><p>No environment was compiled. Retry creates a new proposal and keeps this failed record.</p></div>}
    {bp && <>
      <section><h3>Selected scenario</h3><p>{bp.template_id} / {bp.template_version}</p><p>Budget: {formatMoney(bp.budget_minor, bp.currency)} including shipping · Category: headphones</p></section>
      <section><h3>Customer and objective</h3><p>{bp.customer.name} · Synthetic persona</p><p>{bp.customer.description}</p><p>{bp.objective}</p><ul className="preview-list">{bp.customer.preferences.map(item => <li key={item}>{item}</li>)}</ul></section>
      <section><h3>Proposed catalog</h3><div className="catalog-scroll"><table className="catalog-table"><thead><tr><th>Product</th><th>Price</th><th>Merchant</th><th>Availability</th></tr></thead><tbody>{bp.products.map(item => <tr key={item.id}><td>{item.name}<small>{item.id}</small></td><td>{formatMoney(item.price_minor, item.currency)}</td><td>{bp.merchants.find(merchant => merchant.id === item.merchant_id)?.display_name}</td><td>{item.available ? 'Available' : 'Unavailable'}</td></tr>)}</tbody></table></div></section>
      <section><h3>Proposed merchants</h3><div className="merchant-grid">{bp.merchants.map(item => <article className="merchant-preview" key={item.id}><h4>{item.display_name}</h4><p>{item.verified ? 'Verified' : 'Unverified'} · {item.supports_checkout ? 'Checkout supported' : 'Catalog only'}</p><p>Shipping: {formatMoney(item.shipping_fee_minor, item.currency)}</p></article>)}</div></section>
      <section><h3>Selected challenges</h3>{bp.challenge_summaries.length ? bp.challenge_summaries.map(item => <article className="challenge-preview" key={item.id}><h4>{item.kind.replaceAll('_', ' ')}</h4><p>{item.summary}</p></article>) : <p>No optional challenges selected.</p>}<p>Exact triggers and evaluation expectations remain private.</p></section>
      <section><h3>Deterministic safety boundary</h3><p>All six frozen tools and mandatory purchase policies remain in force. Compilation validates the blueprint; the Tool Gateway independently enforces purchase rules during execution. No real payment or final score is involved.</p></section>
    </>}
    <section aria-label="RAI generation events"><h3>Persisted generation events</h3><ol className="run-events">{events.map(event => <li key={event.id}><details><summary>#{event.sequence} · {event.event_type}</summary><pre>{JSON.stringify(event.payload, null, 2)}</pre></details></li>)}</ol></section>
  </div>;
}
