export function EmptyState({ title, description }: { title: string; description: string }) {
  return <div className="empty-state"><div className="empty-symbol" aria-hidden="true">[ ]</div><h2>{title}</h2><p>{description}</p><span className="phase-label">Available in a future phase</span></div>;
}
