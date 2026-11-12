import { EmptyState } from '../components/EmptyState';
export function FeaturePage({ title, description }: { title: string; description: string }) {
  return <><div className="page-heading"><div><p className="eyebrow">WORKSPACE</p><h1>{title}</h1><p className="subtitle">This capability is planned for a later implementation phase.</p></div></div><section className="panel"><EmptyState title={title + ' is not implemented yet'} description={description} /></section></>;
}
