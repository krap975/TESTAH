import { useEffect, useState } from 'react';
import type { Assessment } from '../types/assessments';
import { apiRequest } from '../services/api';

interface Payment {
  checkout_id: string; status: string; total_minor: number; currency: string;
  order_id: string | null; capture_id: string | null; error_code: string | null; approval_url: string | null;
}
const path = (id: string) => '/api/assessments/' + encodeURIComponent(id) + '/payments';
function safeApproval(payment: Payment): string | null {
  if (!payment.approval_url || !payment.order_id) return null;
  try {
    const url = new URL(payment.approval_url);
    return url.origin === 'https://www.sandbox.paypal.com' && url.pathname === '/checkoutnow' && url.searchParams.get('token') === payment.order_id ? url.href : null;
  } catch { return null; }
}

export function SandboxCheckout({ run }: { run: Assessment }) {
  const [token, setToken] = useState(''); const [draft, setDraft] = useState('');
  const [payments, setPayments] = useState<Payment[]>([]); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const access = token;
  useEffect(() => {
    setPayments([]); setError('');
    if (!access || run.payment_mode !== 'paypal_sandbox') return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const load = async () => {
      try {
        const rows = await apiRequest<Payment[]>(path(run.id), { signal: controller.signal, credentials: 'omit', cache: 'no-store', headers: { Authorization: 'Bearer ' + access } });
        if (!controller.signal.aborted) { setPayments(rows); setError(''); }
      } catch (err) { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Unable to load checkout.'); }
      finally { if (!controller.signal.aborted) timer = setTimeout(() => void load(), 3000); }
    };
    void load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [access, run.id, run.payment_mode]);
  if (run.payment_mode !== 'paypal_sandbox') return null;
  async function reconcile(payment: Payment, capture: boolean) {
    setBusy(true); setError('');
    try {
      const updated = await apiRequest<Payment>(path(run.id) + '/' + encodeURIComponent(payment.checkout_id) + '/reconcile', {
        method: 'POST', credentials: 'omit', cache: 'no-store', headers: { Authorization: 'Bearer ' + access }, body: JSON.stringify({ capture_if_approved: capture }),
      });
      setPayments(rows => rows.map(row => row.checkout_id === updated.checkout_id ? updated : row));
    } catch (err) { setError(err instanceof Error ? err.message : 'Payment verification failed.'); }
    finally { setBusy(false); }
  }
  return <section className="panel agent-form mb-5" aria-label="PayPal Sandbox checkout">
    <h2>PayPal Sandbox checkout</h2><p className="form-help">No real money. Scenario authorization and PayPal buyer approval are separate. Sign in at PayPal using a Sandbox personal buyer account.</p>
    {!access && <form onSubmit={event => { event.preventDefault(); setToken(draft.trim()); setDraft(''); }}>
      <label>Payment operator access token<input type="password" autoComplete="off" minLength={32} required value={draft} onChange={event => setDraft(event.target.value)} /></label>
      <button>Load checkout</button><p className="form-help">Use the separate TESTAH_PAYMENT_OPERATOR_TOKEN. It stays in memory. Never enter PayPal credentials here.</p>
    </form>}
    {access && payments.length === 0 && <p className="muted">No Sandbox checkout has been recorded for this assessment.</p>}
    {payments.map(payment => <div className="panel p-4" key={payment.checkout_id}>
      <p><strong>{payment.currency} {(payment.total_minor / 100).toFixed(2)}</strong> · {payment.status.replaceAll('_', ' ')}</p>
      <dl className="agent-facts"><dt>Checkout</dt><dd>{payment.checkout_id}</dd><dt>Sandbox order</dt><dd>{payment.order_id ?? 'Not created'}</dd><dt>Capture</dt><dd>{payment.capture_id ?? 'No verified capture'}</dd></dl>
      {payment.error_code && <p className="form-error">{payment.error_code}</p>}
      <div className="agent-actions">
        {payment.status === 'awaiting_buyer_approval' && run.status === 'running' && safeApproval(payment) && <a className="primary-button" href={safeApproval(payment)!} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">Approve with PayPal Sandbox</a>}
        {!['completed', 'failed', 'expired'].includes(payment.status) && <>
          <button disabled={busy} onClick={() => void reconcile(payment, false)}>Check provider status</button>
          {run.status === 'running' && <button className="primary-button" disabled={busy} onClick={() => void reconcile(payment, true)}>Verify approval and capture</button>}
        </>}
      </div>
      {payment.status === 'unknown' && <p className="form-help">The provider outcome is uncertain. Reconciliation does not repeat an uncertain financial operation.</p>}
    </div>)}
    {token && <button onClick={() => { setToken(''); setPayments([]); }}>Clear operator token</button>}
    {error && <p role="alert" className="form-error">{error}</p>}
  </section>;
}
