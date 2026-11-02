import { useEffect, useState } from 'react'
import { Check, FileText, LoaderCircle, Minus, ScrollText, ShieldAlert, ShieldCheck, UserRound } from 'lucide-react'
import { api } from '../api'
import { ClassificationBadge } from './ui/Badges'

const actionLabels = {
  'ask': 'Asked a question',
  'search': 'Searched records',
  'document.view': 'Viewed record',
  'document.download': 'Downloaded record',
  'document.ingest': 'Ingested record',
  'document.update': 'Updated record',
  'compare': 'Compared versions',
  'auth.login': 'Signed in',
  'auth.signup': 'Created account',
}

function formatTime(value) {
  const date = new Date(value)
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }).format(date)
}

export default function AccessAudit({ user }) {
  const [policy, setPolicy] = useState(null)
  const [audit, setAudit] = useState(null)
  const [filter, setFilter] = useState('all')
  const [error, setError] = useState('')

  useEffect(() => {
    api('/api/access-policy').then(setPolicy).catch(err => setError(err.message))
  }, [])
  useEffect(() => {
    const query = { denied: '?outcome=denied&include_sign_ins=true', ask: '?action=ask', signin: '?action=auth.login&include_sign_ins=true' }[filter] || ''
    api(`/api/audit${query}`).then(setAudit).catch(err => setError(err.message))
  }, [filter])

  if (error) return <div className="screen"><div className="error-notice"><span>{error}</span></div></div>
  if (!policy || !audit) return <div className="screen document-loading"><LoaderCircle className="spin" /> Loading access policy…</div>

  const myRole = policy.roles.find(role => role.id === user.role)
  const summary = audit.summary
  return <div className="screen access-screen">
    <div className="screen-heading split-heading">
      <div><p className="eyebrow">Governance</p><h1>Access control and audit</h1><p>Retrieval is filtered by classification before any passage reaches the model. Every question, view, and denial is logged.</p></div>
    </div>

    <section className="clearance-card" aria-label="Your clearance">
      <div className="clearance-id"><span><UserRound size={18} /></span><div><small>Signed in as</small><strong>{user.display_name}</strong><em>{myRole?.label}</em></div></div>
      <div className="clearance-levels">{policy.classifications.map(item => <div key={item.id} className={item.visible ? 'granted' : 'withheld'}>
        <ClassificationBadge value={item.id} />
        <strong>{item.document_count}</strong><small>{item.visible ? 'records visible' : 'records withheld'}</small>
      </div>)}</div>
    </section>

    <div className="access-grid">
      <section className="panel policy-panel" aria-labelledby="policy-title">
        <header><ShieldCheck size={16} /><h2 id="policy-title">Role policy</h2></header>
        <table className="policy-table">
          <thead><tr><th scope="col">Role</th>{policy.classifications.map(item => <th scope="col" key={item.id}><ClassificationBadge value={item.id} compact /></th>)}</tr></thead>
          <tbody>{policy.roles.map(role => <tr key={role.id} className={role.id === user.role ? 'current' : ''}>
            <th scope="row">{role.label}{role.id === user.role && <span className="you-pill">You</span>}</th>
            {policy.classifications.map(item => <td key={item.id}>{role.classifications.includes(item.id)
              ? <Check className="yes" size={15} aria-label="Allowed" />
              : <Minus className="no" size={15} aria-label="Not allowed" />}</td>)}
          </tr>)}</tbody>
        </table>
        <dl className="class-defs">{policy.classifications.map(item => <div key={item.id}><dt><ClassificationBadge value={item.id} compact /></dt><dd>{item.description}</dd></div>)}</dl>
      </section>

      <section className="panel audit-panel" aria-labelledby="audit-title">
        <header>
          <ScrollText size={16} /><h2 id="audit-title">{audit.scope === 'all' ? 'Department audit log' : 'Your activity'}</h2>
          <div className="segmented" role="group" aria-label="Filter audit events">
            {[['all', 'Record activity'], ['ask', 'Questions'], ['denied', 'Denied'], ['signin', 'Sign-ins']].map(([id, label]) =>
              <button key={id} className={filter === id ? 'active' : ''} onClick={() => setFilter(id)} aria-pressed={filter === id}>{label}</button>)}
          </div>
        </header>
        {summary && <div className="audit-stats">
          <div><strong>{summary.total}</strong><small>events</small></div>
          <div><strong>{summary.questions}</strong><small>questions</small></div>
          <div><strong>{summary.document_views}</strong><small>record views</small></div>
          <div className="warn"><strong>{summary.denied}</strong><small>denied</small></div>
        </div>}
        {audit.scope === 'self' && <p className="audit-scope-note">Department-wide logs require the Records Administrator role. You can see your own activity.</p>}
        <ol className="audit-list">{audit.events.slice(0, 40).map(event => <li key={event.id} className={event.outcome === 'denied' ? 'denied' : ''}>
          <span className="audit-icon">{event.outcome === 'denied' ? <ShieldAlert size={14} /> : <FileText size={14} />}</span>
          <div>
            <p><strong>{event.display_name || event.user_email || 'Unknown user'}</strong> {actionLabels[event.action] || event.action}{event.outcome === 'denied' && <span className="denied-pill">Denied</span>}</p>
            {event.detail && <small>{event.detail}</small>}
          </div>
          <time dateTime={event.created_at}>{formatTime(event.created_at)}</time>
        </li>)}</ol>
        {!audit.events.length && <p className="muted">No matching events.</p>}
      </section>
    </div>
  </div>
}
