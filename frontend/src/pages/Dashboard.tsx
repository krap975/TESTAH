import { Link } from 'react-router-dom';
import { AssessmentActivity } from '../components/AssessmentActivity';
import { RaiProviderStatus } from '../components/RaiProviderStatus';
import { useRaiConfiguration } from '../hooks/useRaiConfiguration';
import { useHealth } from '../hooks/useHealth';
export function Dashboard() {
  const { state, refresh } = useHealth();
  const rai = useRaiConfiguration();
  return <>
    <div className="page-heading"><div><p className="eyebrow">YOUR TESTING WORKSPACE</p><h1>Dashboard</h1><p className="subtitle">A clear view of your agent assessment workspace.</p></div><span className="phase-label">Phase 9 / Reporting</span></div>
    <section className="intro-panel"><div><p className="eyebrow">BUILT FOR VERIFIABLE BEHAVIOR</p><h2>Put financial agents<br />to the test.</h2><p>Testah will bring controlled simulations, observed actions, and evidence-based evaluation into one workspace.</p></div><div className="intro-detail"><span className="detail-number">/ 01</span><h3>Execution is here.</h3><p>Connect to the backend below. Register agent connections and compile commerce environments. Run assessments and inspect their recorded evidence.</p></div></section>
    <section className="panel health-panel" aria-labelledby="health-title"><div className="section-header"><div><p className="eyebrow">SYSTEM CONNECTION</p><h2 id="health-title">Backend health</h2></div><button onClick={refresh} disabled={state.status === 'checking'}>Check again ↗</button></div>
      <div role="status" aria-live="polite" className="health-result"><span className={'status-light ' + state.status} /><div><strong>{state.status === 'connected' ? 'Backend reachable' : state.status === 'checking' ? 'Checking connection…' : 'Backend unavailable'}</strong><p>{state.status === 'connected' ? state.data.service + ' · status: ' + state.data.status + ' · database: ' + state.data.database : state.status === 'unavailable' ? state.message + ' Start the API and check your environment settings.' : 'Requesting /api/health from your configured API.'}</p></div><code>GET /api/health</code></div>
    </section>
    <section className="panel p-6 mb-5"><p className="eyebrow">RAI DESIGNER + EXAMINER</p><h2 className="text-xl mt-3">Design a controlled assessment</h2><RaiProviderStatus configuration={rai.configuration} />{rai.error && <p className="form-error" role="alert">{rai.error}</p>}<button onClick={rai.refresh}>Refresh RAI configuration</button><p className="form-help">Select a registered agent, generate and validate a proposal, review it, and choose the customer mode. Generation mode is shown explicitly; mock mode uses no LLM.</p><div className="agent-actions mt-5"><Link className="workspace-card" to="/rai">Generate with RAI →</Link><Link className="workspace-card" to="/environments">Advanced / Manual environments →</Link></div></section>
    <AssessmentActivity />
    <div className="grid gap-4 md:grid-cols-3 mt-5">{[{to:'/agents',title:'Connect an agent',text:'Register a candidate endpoint and verify its protocol.'},{to:'/environments',title:'Shape the test',text:'Inspect controlled scenarios, tools, and policies.'},{to:'/reports',title:'Follow the evidence',text:'Review observed behavior and evaluation findings.'}].map(item => <Link className="workspace-card" to={item.to} key={item.to}><span className="eyebrow">WORKSPACE ↗</span><h3>{item.title}</h3><p>{item.text}</p></Link>)}</div>
  </>;
}
