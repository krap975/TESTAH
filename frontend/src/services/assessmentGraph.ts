import type { RunEvent } from '../types/assessments';

export type Outcome = 'recorded' | 'active' | 'success' | 'rejected' | 'failed' | 'interrupted';
export type ActorId = 'customer' | 'agent' | 'tools' | 'environment' | 'payment';
export const actors: Record<ActorId, string> = {
  customer: 'RAI Examiner / Customer', agent: 'Candidate Agent', tools: 'Tool Gateway',
  environment: 'Environment Engine', payment: 'Payment Gateway',
};
const obj = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
const string = (value: unknown) => typeof value === 'string' ? value.slice(0, 120) : '';
const denialCodes = new Set(['approval_required', 'approval_consumed', 'approval_invalidated', 'amount_changed', 'stale_cart', 'budget_exceeded',
  'unverified_merchant', 'checkout_unsupported', 'product_unavailable', 'invalid_cart', 'currency_mismatch', 'unknown_checkout', 'invalid_tool_arguments',
  'idempotency_conflict', 'purchase_limit', 'unknown_tool', 'approval_not_found', 'unknown_merchant', 'tool_not_allowed']);

export function actorFor(event: RunEvent): ActorId | null {
  const type = event.event_type;
  if (type.startsWith('customer.') || type.startsWith('rai.examiner.')) return 'customer';
  if (type.startsWith('agent.')) return 'agent';
  if (type.startsWith('tool.') || type.startsWith('approval.') || type.startsWith('policy.') || type.startsWith('checkout.')) return 'tools';
  if (type.startsWith('challenge.') || type.startsWith('rai.challenge.')) return 'environment';
  if (type.startsWith('payment.')) return 'payment';
  return null;
}

export function eventOutcome(event: RunEvent): Outcome {
  const type = event.event_type; const code = string(obj(event.payload.result).code);
  if (['policy.violation', 'approval.denied', 'rai.challenge.request_rejected'].includes(type) || (type === 'tool.failed' && denialCodes.has(code))) return 'rejected';
  if (type === 'tool.failed' || type === 'execution.terminated') return 'failed';
  if (type === 'payment.failed') return 'failed';
  if (['payment.approval_pending', 'payment.capture_requested', 'payment.capture_pending', 'payment.status_unknown'].includes(type)) return 'active';
  if (type === 'assessment.finished') return event.payload.status === 'completed' ? 'success' : event.payload.status === 'failed' ? 'failed' : 'interrupted';
  if (['tool.completed', 'payment.captured', 'payment.authorized', 'approval.granted'].includes(type)) return 'success';
  return 'recorded';
}

export function describeEvent(event: RunEvent): { actor: string; description: string; outcome: Outcome } {
  const name = string(event.payload.name); const type = event.event_type;
  const descriptions: Record<string, string> = {
    'assessment.created': 'Assessment created; execution has not started.',
    'assessment.state_changed': 'State changed to ' + string(event.payload.to) + '.',
    'assessment.finished': 'Assessment finished: ' + string(event.payload.status) + '.',
    'customer.message': 'Customer message recorded for the candidate.',
    'agent.requested': 'Candidate protocol request recorded.',
    'agent.message': 'Candidate message recorded.',
    'agent.tool_call': 'Candidate requested ' + name + '.',
    'agent.completed': 'Candidate claimed completion; controller checks determine the outcome.',
    'tool.requested': 'Gateway request: ' + name + '.',
    'tool.completed': 'Gateway operation completed: ' + name + '.',
    'tool.failed': 'Gateway operation did not complete: ' + name + '.',
    'policy.violation': 'Gateway rejected ' + name + ': ' + string(event.payload.code) + '.',
    'approval.granted': 'Exact scenario approval recorded by the gateway.',
    'approval.denied': 'Scenario approval denied.',
    'challenge.activated': 'Declared environment challenge activated.',
    'checkout.created': 'Simulated checkout created; no real payment.',
    'payment.authorized': 'Simulated payment authorization recorded.',
    'payment.captured': event.payload.provider === 'paypal_sandbox' ? 'PayPal Sandbox capture verified.' : 'Simulated payment capture recorded.',
    'checkout.requested': 'Authorized Sandbox checkout requested.',
    'payment.authorization_verified': 'Exact scenario purchase authorization verified.',
    'payment.order_requested': 'PayPal Sandbox order request committed.',
    'payment.order_created': 'PayPal Sandbox order created; buyer approval is separate.',
    'payment.approval_pending': 'Awaiting actual PayPal Sandbox buyer approval.',
    'payment.buyer_approved': 'Buyer approval confirmed by the Sandbox API.',
    'payment.capture_requested': 'Sandbox capture requested after server verification.',
    'payment.capture_pending': 'Sandbox capture remains pending at the provider.',
    'payment.status_unknown': 'Provider outcome uncertain; reconciliation required.',
    'payment.failed': 'Sandbox payment failed: ' + string(event.payload.error_code) + '.',
    'payment.expired': 'Sandbox approval window expired; no new capture permitted.',
    'rai.examiner.requested': 'Examiner message-plan generation requested.',
    'rai.examiner.message_generated': 'Validated Examiner message plan recorded.',
    'rai.examiner.fallback': 'Explicit deterministic Examiner fallback recorded.',
    'rai.challenge.request_accepted': 'Challenge request accepted conditionally; awaiting its declared trigger.',
    'rai.challenge.request_rejected': 'Challenge request rejected.',
    'rai.challenge.request_fulfilled': 'Previously accepted challenge request fulfilled.',
    'execution.terminated': 'Execution terminated: ' + string(event.payload.code) + '.',
  };
  const actor = actorFor(event);
  return { actor: actor ? actors[actor] : type.startsWith('rai.') ? 'RAI Designer / proposal evidence' : 'Execution Controller / system',
    description: descriptions[type] ?? 'Persisted ' + type.replaceAll('.', ' / ').replaceAll('_', ' ') + '.', outcome: eventOutcome(event) };
}

export interface GraphNode { id: ActorId; position: { x: number; y: number }; data: { label: string; eventIds: string[]; outcome: Outcome }; className: string }
export interface GraphEdge { id: string; source: ActorId; target: ActorId; label: string; data: { eventIds: string[]; outcome: Outcome }; className: string }

/** Pure prefix projection; no fetching, timers, inferred thoughts or execution calls. */
export function assessmentGraph(events: readonly RunEvent[]): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const edges = new Map<string, { source: ActorId; target: ActorId; label: string; ids: Set<string>; pending: Set<string>; outcome: Outcome; sequence: number }>();
  const nodeIds = new Map<ActorId, Set<string>>(Object.keys(actors).map(id => [id as ActorId, new Set()]));
  const operations = new Map<string, Set<string>>();
  const ownOutcome = new Map<ActorId, { sequence: number; outcome: Outcome }>();
  let examinerPending = false;
  const touch = (source: ActorId, target: ActorId, label: string, event: RunEvent, outcome: Outcome = eventOutcome(event), operation?: string) => {
    const key = source + ':' + target;
    const edge = edges.get(key) ?? { source, target, label, ids: new Set<string>(), pending: new Set<string>(), outcome, sequence: 0 };
    edge.ids.add(event.id); edge.outcome = outcome; edge.sequence = event.sequence; edge.label = label;
    if (operation) {
      edge.pending.add(operation);
      const group = operations.get(operation) ?? new Set<string>(); group.add(key); operations.set(operation, group);
    }
    edges.set(key, edge); nodeIds.get(source)!.add(event.id); nodeIds.get(target)!.add(event.id);
  };
  const resolve = (operation: string, event: RunEvent, outcome: Outcome) => {
    for (const key of operations.get(operation) ?? []) {
      const edge = edges.get(key)!; edge.pending.delete(operation); edge.outcome = outcome; edge.ids.add(event.id); edge.sequence = event.sequence;
      nodeIds.get(edge.source)!.add(event.id); nodeIds.get(edge.target)!.add(event.id);
    }
    operations.delete(operation);
  };
  let terminal = false;
  let paymentLabel = 'Payment Gateway';
  for (const event of events) {
    const actor = actorFor(event); if (actor) nodeIds.get(actor)!.add(event.id);
    if (actor) ownOutcome.set(actor, { sequence: event.sequence, outcome: eventOutcome(event) });
    const type = event.event_type; const request = string(event.payload.request_id);
    if (type === 'checkout.created' && event.payload.provider === 'simulation') paymentLabel = 'Simulated payment';
    if (type === 'payment.order_created') paymentLabel = 'PayPal Sandbox order';
    if (type === 'payment.approval_pending') paymentLabel = 'PayPal Sandbox · pending buyer approval';
    if (type === 'payment.buyer_approved') paymentLabel = 'PayPal Sandbox · buyer approved';
    if (type === 'payment.capture_requested' || type === 'payment.capture_pending') paymentLabel = 'PayPal Sandbox · capture pending';
    if (type === 'payment.captured') paymentLabel = event.payload.provider === 'paypal_sandbox' ? 'PayPal Sandbox · captured' : 'Simulated payment · completed';
    if (type === 'payment.failed') paymentLabel = 'PayPal Sandbox · failed';
    if (type === 'payment.status_unknown') paymentLabel = 'PayPal Sandbox · outcome unknown';
    if (type === 'payment.expired') paymentLabel = 'PayPal Sandbox · approval expired';
    const call = event.correlation_id ?? event.id; const tool = string(event.payload.name);
    if (type === 'rai.examiner.requested') examinerPending = true;
    if (type === 'rai.examiner.message_generated' || type === 'rai.examiner.fallback') examinerPending = false;
    if (type === 'customer.message') touch('customer', 'agent', 'Customer / protocol', event);
    if (type === 'agent.requested') touch('customer', 'agent', 'Customer / protocol', event, 'recorded', 'agent:' + request);
    if (['agent.message', 'agent.tool_call', 'agent.completed'].includes(type)) resolve('agent:' + request, event, 'success');
    if (type === 'agent.message' || type === 'agent.completed') touch('agent', 'customer', 'Candidate response', event);
    if (type === 'agent.tool_call') touch('agent', 'tools', 'Tool calls', event, 'recorded', 'tool:' + call);
    if (type === 'tool.requested') touch('tools', ['create_checkout', 'get_payment_status'].includes(tool) ? 'payment' : 'environment',
      ['create_checkout', 'get_payment_status'].includes(tool) ? 'Commerce payment' : 'Scenario state / policy', event, 'recorded', 'tool:' + call);
    if (type === 'tool.completed' || type === 'tool.failed') {
      resolve('tool:' + call, event, eventOutcome(event));
      touch('tools', 'agent', 'Recorded tool result', event);
    }
    if (type.startsWith('payment.') || type === 'checkout.created') touch('tools', 'payment', paymentLabel, event);
    if (type === 'challenge.activated') touch('environment', 'tools', 'Declared challenge', event);
    if (type === 'rai.challenge.request_accepted' || type === 'rai.challenge.request_rejected') touch('customer', 'environment', 'Conditional challenge request', event);
    if (type === 'assessment.finished') terminal = true;
  }
  const mappedEdges: GraphEdge[] = [...edges].map(([id, edge]) => ({ id, source: edge.source, target: edge.target,
    label: edge.label + ' · ' + edge.ids.size,
    data: { eventIds: [...edge.ids], outcome: edge.pending.size ? terminal ? 'interrupted' : 'active' : edge.outcome },
    className: 'interaction-' + (edge.pending.size ? terminal ? 'interrupted' : 'active' : edge.outcome) }));
  const positions = { customer: { x: 0, y: 0 }, agent: { x: 310, y: 0 }, tools: { x: 310, y: 180 }, environment: { x: 0, y: 350 }, payment: { x: 620, y: 350 } };
  const nodes = (Object.keys(actors) as ActorId[]).map(id => {
    const relevant = mappedEdges.filter(edge => edge.source === id || edge.target === id).sort((a, b) => edges.get(a.id)!.sequence - edges.get(b.id)!.sequence);
    const latest = relevant.at(-1); const own = ownOutcome.get(id);
    const active = relevant.some(edge => edge.data.outcome === 'active') || id === 'customer' && examinerPending;
    const outcome = active ? terminal ? 'interrupted' : 'active' : own && (!latest || own.sequence > edges.get(latest.id)!.sequence) ? own.outcome : latest?.data.outcome ?? 'recorded';
    return { id, position: positions[id], data: { label: (id === 'payment' ? paymentLabel : actors[id]) + '\n' + nodeIds.get(id)!.size + ' supporting events · ' + outcome, eventIds: [...nodeIds.get(id)!], outcome }, className: 'interaction-' + outcome };
  });
  return { nodes, edges: mappedEdges };
}
