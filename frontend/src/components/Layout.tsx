import { NavLink, Outlet } from 'react-router-dom';
const navigation = [['/', 'Dashboard'], ['/agents', 'My Agents'], ['/rai', 'Generate with RAI'], ['/environments', 'Environments'], ['/assessments', 'Assessments'], ['/monitor', 'Live Monitor'], ['/logs', 'Execution Logs'], ['/reports', 'Reports']];
export function Layout() {
  return <div className="app-layout">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <aside className="sidebar"><NavLink to="/" className="brand" aria-label="Testah home"><span className="brand-icon">t.</span>testah<span className="brand-dot">/</span></NavLink>
      <p className="nav-caption">WORKSPACE</p><nav aria-label="Main navigation">{navigation.map(([url,label],index) => <NavLink key={url} to={url} end={url === '/'} className={({isActive}) => 'nav-link ' + (isActive ? 'active' : '')}><span className="nav-mark" aria-hidden="true">0{index + 1}</span>{label}</NavLink>)}</nav>
      <div className="sidebar-note">{import.meta.env?.PROD ? 'Shared demo workspace' : 'Local development'}<p>Reporting & analytics</p></div>
    </aside><div className="main-shell"><header className="topbar"><span>Financial AI agent testing</span><span className="outline-badge">{import.meta.env?.PROD ? 'SANDBOX DEMO' : 'DEVELOPMENT'}</span></header><main id="main-content" tabIndex={-1}><Outlet /></main><footer>Testah <span>/</span> Controlled environments. Observable evidence.</footer></div>
  </div>;
}
