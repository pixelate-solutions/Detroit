import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  ArrowLeftRight, BookOpen, Bot, Check, ChevronDown,
  ChevronRight, FileSearch, FolderOpen, GitBranch, HardDrive, LoaderCircle,
  Eye, EyeOff, History, LockKeyhole, LogOut, Mail, MessageSquarePlus, Network, Plus,
  Search, Send, Share2, ShieldCheck, Sparkles, Square, Trash2,
  UploadCloud, UserPlus, UserRound, Users, X, Zap, KeyRound, ScrollText, Quote, ExternalLink,
} from 'lucide-react'
import { api, post } from './api'
import DocumentViewer from './components/DocumentViewer'
import FileExplorer from './components/FileExplorer'
import ConfirmDialog from './components/ui/ConfirmDialog'
import RecordCombobox from './components/ui/RecordCombobox'
import AccessAudit from './components/AccessAudit'
import { BrandMark, ClassificationBadge, TypeBadge, classificationOrder } from './components/ui/Badges'

const GraphView = lazy(() => import('./components/GraphView'))

const tabs = [
  { id: 'ask', label: 'Ask the records', icon: Bot },
  { id: 'search', label: 'Search', icon: FileSearch },
  { id: 'files', label: 'Document library', icon: FolderOpen },
  { id: 'compare', label: 'Compare versions', icon: ArrowLeftRight },
  { id: 'graph', label: 'Knowledge graph', icon: Network },
  { id: 'access', label: 'Access & audit', icon: ScrollText },
  { id: 'upload', label: 'Add record', icon: UploadCloud },
]

const PRODUCT = 'Civic Records AI'

function EmptyState({ icon: Icon = BookOpen, title, children }) {
  return <div className="empty-state"><Icon /><h3>{title}</h3><p>{children}</p></div>
}

function ErrorNotice({ error, onClose }) {
  if (!error) return null
  return <div className="error-notice"><div><strong>Local service needs attention</strong><span>{error}</span></div>{onClose && <button onClick={onClose}><X size={16} /></button>}</div>
}

function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState('login')
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [demo, setDemo] = useState(null)

  useEffect(() => { api('/api/demo/accounts').then(setDemo).catch(() => setDemo(null)) }, [])

  async function demoLogin(email) {
    setLoading(true); setError('')
    try { const data = await post('/api/demo/login', { email }); onAuthenticated(data.user) }
    catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  async function submit(event) {
    event.preventDefault()
    if (mode === 'signup' && password !== confirmPassword) {
      setError('Passwords do not match. Please enter the same password twice.')
      return
    }
    setLoading(true); setError('')
    try {
      const payload = mode === 'signup'
        ? { display_name: displayName, email, password }
        : { email, password }
      const data = await post(`/api/auth/${mode}`, payload)
      onAuthenticated(data.user)
    } catch (err) {
      setError(err.status === 405
        ? 'The local server is running an older version. Stop Uvicorn, restart it, and then try again.'
        : err.message)
    }
    finally { setLoading(false) }
  }

  function switchMode(nextMode) {
    setMode(nextMode); setError(''); setPassword(''); setConfirmPassword(''); setShowPassword(false); setShowConfirmPassword(false)
  }

  return <main className="auth-page">
    <section className="auth-brand-panel">
      <div className="auth-brand"><BrandMark size={46} /><div><strong>{PRODUCT}</strong><small>On-prem document intelligence</small></div></div>
      <div className="auth-promise"><p className="eyebrow">For public safety and local government</p><h1>Every answer cites its source. No data leaves the building.</h1><p>Ask questions across incident reports, inspections, and SOPs. Answers come from a model running on your own hardware, filtered by each user's clearance and written to an audit log.</p></div>
      <div className="auth-local"><HardDrive size={16} /><span><strong>Air-gapped by design</strong><small>OCR, embeddings, vector search, and inference run on this server</small></span></div>
    </section>
    <section className="auth-form-panel">
      <div className="auth-card">
        <div className="auth-icon">{mode === 'signup' ? <UserPlus /> : <LockKeyhole />}</div>
        <p className="eyebrow">{mode === 'signup' ? 'Create your account' : 'Welcome back'}</p>
        <h2>{mode === 'signup' ? 'Create your account' : `Sign in to ${PRODUCT}`}</h2>
        <p className="auth-subtitle">{mode === 'signup' ? 'New accounts start with the Firefighter role. A records administrator can grant more access.' : 'Continue to your saved conversations and department records.'}</p>
        {demo?.enabled && mode === 'login' && <div className="demo-accounts">
          <div className="demo-accounts-head"><KeyRound size={13} /><span>Demo sign-in · {demo.deployment}</span></div>
          {demo.accounts.map(account => <button type="button" key={account.email} onClick={() => demoLogin(account.email)} disabled={loading}>
            <i>{account.display_name.replace(/^(Capt\.|FF)\s/, '').slice(0, 1)}</i><span><strong>{account.display_name}</strong><small>{account.role_label}</small></span><ChevronRight size={15} />
          </button>)}
        </div>}
        <div className="auth-tabs"><button className={mode === 'login' ? 'active' : ''} onClick={() => switchMode('login')}>Sign in</button><button className={mode === 'signup' ? 'active' : ''} onClick={() => switchMode('signup')}>Sign up</button></div>
        <form onSubmit={submit}>
          {mode === 'signup' && <label><span>Display name</span><div><UserRound size={16} /><input value={displayName} onChange={event => setDisplayName(event.target.value)} autoComplete="name" required minLength="2" placeholder="Jordan Lee" /></div></label>}
          <label><span>Email address</span><div><Mail size={16} /><input type="email" value={email} onChange={event => setEmail(event.target.value)} autoComplete="email" required placeholder="you@department.example" /></div></label>
          <label><span>Password</span><div><LockKeyhole size={16} /><input type={showPassword ? 'text' : 'password'} value={password} onChange={event => setPassword(event.target.value)} autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} required minLength={mode === 'signup' ? 10 : 1} placeholder={mode === 'signup' ? 'At least 10 characters' : 'Your password'} /><button className="auth-password-toggle" type="button" onClick={() => setShowPassword(value => !value)} aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword}>{showPassword ? <EyeOff size={16} /> : <Eye size={16} />}</button></div></label>
          {mode === 'signup' && <label><span>Confirm password</span><div><LockKeyhole size={16} /><input type={showConfirmPassword ? 'text' : 'password'} value={confirmPassword} onChange={event => setConfirmPassword(event.target.value)} autoComplete="new-password" required minLength={10} placeholder="Type your password again" aria-invalid={Boolean(confirmPassword && password !== confirmPassword)} /><button className="auth-password-toggle" type="button" onClick={() => setShowConfirmPassword(value => !value)} aria-label={showConfirmPassword ? 'Hide confirmed password' : 'Show confirmed password'} aria-pressed={showConfirmPassword}>{showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}</button></div></label>}
          {error && <div className="auth-error">{error}</div>}
          <button className="auth-submit" disabled={loading}>{loading ? <LoaderCircle className="spin" size={18} /> : mode === 'signup' ? 'Create account' : 'Sign in'}<ChevronRight size={17} /></button>
        </form>
      </div>
    </section>
  </main>
}

function MarkdownAnswer({ children, dark = false }) {
  return <div className={`markdown-body ${dark ? 'markdown-dark' : ''}`}>
    <ReactMarkdown remarkPlugins={[remarkGfm]}>{children || ''}</ReactMarkdown>
  </div>
}

function SearchScreen({ onOpenDocument, initialQuery = '' }) {
  const [query, setQuery] = useState(initialQuery)
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [searched, setSearched] = useState(false)

  async function runSearch(event) {
    event?.preventDefault()
    if (!query.trim()) return
    setLoading(true); setError(''); setSearched(true)
    try {
      const data = await post('/api/search', { query, top_k: 12 })
      setResults(data.results)
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  return <div className="screen search-screen">
    <div className="screen-heading split-heading">
      <div><p className="eyebrow">Hybrid retrieval</p><h1>Search the records you're cleared to see.</h1><p>SQLite full-text search and ChromaDB vector search, merged with reciprocal-rank fusion.</p></div>
      <div className="heading-stat"><span>0</span><small>external calls</small></div>
    </div>
    <form className="search-hero" onSubmit={runSearch}>
      <Search size={21} />
      <input autoFocus value={query} onChange={event => setQuery(event.target.value)} placeholder="Try “714 Marquette rear stair”" />
      <button className="primary-button" disabled={loading}>{loading ? <LoaderCircle className="spin" size={18} /> : 'Search'}</button>
    </form>
    <div className="query-suggestions">
      {['714 Marquette rear stair', 'standpipe attack line crew', 'e-bike battery reignition'].map(item =>
        <button key={item} onClick={() => setQuery(item)}>{item}</button>)}
    </div>
    <ErrorNotice error={error} onClose={() => setError('')} />
    {results.length > 0 && <div className="results-header"><span>{results.length} relevant passages</span><span>Combined ranking</span></div>}
    <div className="result-list">
      {results.map((result, index) => <button className="result-card" key={result.chunk_id} onClick={() => onOpenDocument(result.document_id, result.page_number, result.snippet)}>
        <div className="result-rank">{String(index + 1).padStart(2, '0')}</div>
        <div className="result-content">
          <div className="result-title-row"><h3>{result.title}</h3><TypeBadge type={result.doc_type} /><ClassificationBadge value={result.classification} compact /></div>
          <p>{result.snippet}</p>
          <div className="result-meta"><span>Page {result.page_number}</span><span>{result.matched_by.replace('+', ' + ')}</span></div>
        </div>
        <div className="score"><strong>{Math.round(result.score * 100)}</strong><small>match</small></div>
        <ChevronRight className="result-arrow" size={18} />
      </button>)}
    </div>
    {searched && !loading && !error && !results.length && <EmptyState icon={Search} title="No matching records">Try a broader topic or check the wording.</EmptyState>}
    {!searched && <div className="search-intro-grid">
      <article><Zap /><h3>Find meaning, not filenames</h3><p>Search concepts even when the records use different wording.</p></article>
      <article><ShieldCheck /><h3>Filtered by clearance</h3><p>Records above your role's classification never enter the result set.</p></article>
      <article><GitBranch /><h3>Follow the evidence</h3><p>Every result points to the exact source page and passage.</p></article>
    </div>}
  </div>
}

function ActivityTrace({ trace, reasoningSummary, reasoningComplete, loading, elapsed }) {
  const [open, setOpen] = useState(loading)
  useEffect(() => { if (loading) setOpen(true) }, [loading])
  if (!loading && !reasoningSummary) return null
  const seconds = Math.max(0, elapsed || 0) / 1000
  const roundedSeconds = Math.max(1, Math.round(seconds))
  const duration = seconds < 0.5 ? 'less than a second' : `${roundedSeconds} ${roundedSeconds === 1 ? 'second' : 'seconds'}`
  const generatingReasoning = loading && !reasoningComplete
  return <section className={`activity-trace ${loading ? 'is-live' : ''}`}>
    <button className="trace-toggle" onClick={() => setOpen(value => !value)} aria-expanded={open}>
      {generatingReasoning && <LoaderCircle className="spin" size={14} />}
      <strong>{loading ? generatingReasoning ? 'Reasoning…' : 'Reasoned' : `Reasoned for ${duration}`}</strong>
      <ChevronDown className={open ? 'open' : ''} size={16} />
    </button>
    {open && <div className="reasoning-copy" role="status" aria-live={generatingReasoning ? 'polite' : 'off'}>
      {reasoningSummary ? <p>{reasoningSummary}{generatingReasoning && <span className="reasoning-cursor" />}</p> : <p className="reasoning-awaiting">Reading the relevant records…</p>}
    </div>}
  </section>
}

const STOP = new Set('the and for with that this what does from were was are have has did how which when where who why about into than then there their they your you any all its not but can will shall'.split(' '))

function highlightTerms(text, question) {
  const terms = [...new Set((question || '').toLowerCase().match(/[a-z0-9][a-z0-9-]{2,}/g) || [])].filter(term => !STOP.has(term))
  if (!terms.length) return text
  const pattern = new RegExp(`(${terms.map(term => term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi')
  return text.split(pattern).map((part, index) => terms.includes(part.toLowerCase()) ? <mark key={index}>{part}</mark> : part)
}

function CitationList({ citations, question, onOpenDocument }) {
  if (!citations?.length) return null
  return <section className="citation-list" aria-label="Cited sources">
    <div className="citation-list-head"><Quote size={13} /><span>{citations.length} cited {citations.length === 1 ? 'passage' : 'passages'}</span><small>Click to open the source page</small></div>
    <ol>{citations.map(citation => <li key={citation.marker} id={`cite-${citation.marker}`}>
      <button onClick={() => onOpenDocument?.(citation.document_id, citation.page_number, citation.snippet)}>
        <span className="citation-marker">{citation.marker}</span>
        <div>
          <div className="citation-title"><strong>{citation.document_title}</strong>{citation.classification && <ClassificationBadge value={citation.classification} compact />}<small>Page {citation.page_number}</small></div>
          <p>{highlightTerms(citation.snippet, question)}</p>
        </div>
        <ExternalLink size={14} className="citation-open" />
      </button>
    </li>)}</ol>
  </section>
}

function withCitationLinks(content) {
  return (content || '').replace(/\[C(\d+)\]/g, '[C$1](#cite-C$1)')
}

function AnswerMarkdown({ children, citations, onOpenDocument }) {
  const byMarker = Object.fromEntries((citations || []).map(item => [item.marker, item]))
  return <div className="markdown-body">
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
      a: ({ href, children: label }) => {
        const marker = href?.startsWith('#cite-') ? href.slice(6) : null
        if (!marker) return <a href={href}>{label}</a>
        const citation = byMarker[marker]
        return <button type="button" className="cite-chip" title={citation ? `${citation.document_title}, page ${citation.page_number}` : marker}
          onClick={() => citation && onOpenDocument?.(citation.document_id, citation.page_number, citation.snippet)}>{marker.slice(1)}</button>
      },
    }}>{withCitationLinks(children)}</ReactMarkdown>
  </div>
}

function AssistantTurn({ message, activeElapsed, question, onOpenDocument }) {
  const streaming = message.status === 'streaming'
  const finalCitations = streaming ? [] : message.citations
  return <div className="chat-turn assistant-turn">
    <div className="chat-avatar assistant-avatar"><Sparkles size={16} /></div>
    <div className="chat-turn-body">
      <div className="chat-speaker"><strong>{PRODUCT}</strong>{streaming && <em>Streaming</em>}</div>
      <article className={`chat-bubble assistant-bubble ${streaming ? 'streaming' : ''}`}>
        <ActivityTrace trace={message.trace} reasoningSummary={message.reasoning_summary} reasoningComplete={message.reasoningComplete} loading={streaming} elapsed={streaming ? activeElapsed : message.elapsed} />
        {message.content ? <AnswerMarkdown citations={message.citations} onOpenDocument={onOpenDocument}>{message.content}</AnswerMarkdown> : streaming ? <div className="answer-awaiting"><span></span>Preparing the answer…</div> : null}
        {message.error && <div className="chat-error">{message.error}</div>}
        {streaming && message.content && <span className="stream-cursor" />}
        <CitationList citations={finalCitations} question={question} onOpenDocument={onOpenDocument} />
      </article>
    </div>
  </div>
}

function AskScreen({ onOpenDocument }) {
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState([])
  const [conversations, setConversations] = useState([])
  const [activeConversation, setActiveConversation] = useState(null)
  const [conversationSources, setConversationSources] = useState([])
  const [shares, setShares] = useState([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyError, setHistoryError] = useState('')
  const [shareOpen, setShareOpen] = useState(false)
  const [shareEmail, setShareEmail] = useState('')
  const [shareError, setShareError] = useState('')
  const [shareLoading, setShareLoading] = useState(false)
  const [sourcesOpen, setSourcesOpen] = useState(false)
  const [deleteConversationId, setDeleteConversationId] = useState(null)
  const [deleteConversationLoading, setDeleteConversationLoading] = useState(false)
  const [loading, setLoading] = useState(false)
  const [activeTurnId, setActiveTurnId] = useState(null)
  const [elapsed, setElapsed] = useState(0)
  const abortRef = useRef(null)
  const threadEndRef = useRef(null)

  useEffect(() => () => abortRef.current?.abort(), [])
  useEffect(() => { loadConversationList() }, [])
  useEffect(() => {
    if (!loading) return
    const started = Date.now() - elapsed
    const timer = window.setInterval(() => setElapsed(Date.now() - started), 100)
    return () => window.clearInterval(timer)
  }, [loading])
  const latestContent = messages.at(-1)?.content
  useEffect(() => {
    if (messages.length) window.requestAnimationFrame(() => threadEndRef.current?.scrollIntoView({ block: 'end' }))
  }, [messages.length, latestContent])

  function updateMessage(turnId, updater) {
    setMessages(current => current.map(message => message.id === turnId ? updater(message) : message))
  }

  function updateTrace(turnId, step) {
    updateMessage(turnId, message => {
      const index = message.trace.findIndex(item => item.id === step.id)
      const trace = [...message.trace]
      if (index === -1) trace.push(step)
      else trace[index] = { ...trace[index], ...step }
      return { ...message, trace }
    })
  }

  function handleStreamEvent(turnId, streamEvent) {
    if (streamEvent.type === 'conversation') {
      setActiveConversation(current => ({ ...(current || {}), ...streamEvent.conversation }))
    } else if (streamEvent.type === 'conversation_sources') {
      setConversationSources(streamEvent.sources || [])
    } else if (streamEvent.type === 'trace') {
      updateTrace(turnId, streamEvent)
    } else if (streamEvent.type === 'reasoning_delta') {
      updateMessage(turnId, message => ({ ...message, reasoning_summary: `${message.reasoning_summary || ''}${streamEvent.text || ''}` }))
    } else if (streamEvent.type === 'reasoning_done') {
      updateMessage(turnId, message => ({ ...message, reasoningComplete: true }))
    } else if (streamEvent.type === 'sources') {
      const citations = streamEvent.citations || []
      updateMessage(turnId, message => ({ ...message, citations, evidenceDocumentCount: new Set(citations.map(citation => citation.document_id)).size }))
    } else if (streamEvent.type === 'citations') {
      updateMessage(turnId, message => ({ ...message, citations: streamEvent.citations || [] }))
    } else if (streamEvent.type === 'delta') {
      updateMessage(turnId, message => ({ ...message, content: `${message.content}${streamEvent.text || ''}` }))
    } else if (streamEvent.type === 'done') {
      const turnElapsed = streamEvent.elapsed_ms || elapsed
      setElapsed(turnElapsed)
      updateMessage(turnId, message => ({ ...message, elapsed: turnElapsed, status: 'complete' }))
      loadConversationList()
    } else if (streamEvent.type === 'error') {
      throw new Error(streamEvent.message || 'The local answer stream stopped.')
    }
  }

  async function ask(event, suggested) {
    event?.preventDefault()
    const value = (suggested || question).trim()
    if (!value || loading) return
    const userTurn = { id: crypto.randomUUID(), role: 'user', content: value }
    const assistantTurn = { id: crypto.randomUUID(), role: 'assistant', content: '', reasoning_summary: '', reasoningComplete: false, citations: [], trace: [], evidenceDocumentCount: 0, elapsed: 0, status: 'streaming', error: '' }
    const controller = new AbortController()
    abortRef.current = controller
    setMessages(current => [...current, userTurn, assistantTurn])
    setQuestion(''); setLoading(true); setActiveTurnId(assistantTurn.id); setElapsed(0)
    const startedAt = performance.now()
    try {
      const response = await fetch('/api/ask/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: value, conversation_id: activeConversation?.id || null }),
        signal: controller.signal,
      })
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}))
        throw new Error(payload.detail || `Request failed (${response.status})`)
      }
      if (!response.body) throw new Error('This browser did not provide a response stream.')
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value: chunk } = await reader.read()
        buffer += decoder.decode(chunk || new Uint8Array(), { stream: !done })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          if (line.trim()) handleStreamEvent(assistantTurn.id, JSON.parse(line))
        }
        if (done) break
      }
      if (buffer.trim()) handleStreamEvent(assistantTurn.id, JSON.parse(buffer))
    } catch (err) {
      if (err.name !== 'AbortError') {
        updateMessage(assistantTurn.id, message => ({ ...message, error: err.message, status: 'error' }))
      }
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null
        setLoading(false)
        setActiveTurnId(null)
        const fallbackElapsed = Math.round(performance.now() - startedAt)
        updateMessage(assistantTurn.id, message => message.status === 'streaming' ? { ...message, elapsed: fallbackElapsed, status: 'complete' } : message)
      }
    }
  }

  function stopStreaming() {
    const turnId = activeTurnId
    abortRef.current?.abort()
    abortRef.current = null
    setLoading(false); setActiveTurnId(null)
    if (turnId) {
      updateTrace(turnId, { id: 'stopped', status: 'complete', kind: 'writing', title: 'Response stopped', detail: 'Kept the response received so far' })
      updateMessage(turnId, message => ({ ...message, elapsed, status: 'stopped' }))
    }
    window.setTimeout(loadConversationList, 500)
  }

  async function loadConversationList() {
    try {
      const data = await api('/api/conversations')
      setConversations(data.conversations || [])
      setHistoryError('')
    } catch (err) { setHistoryError(err.message) }
    finally { setHistoryLoading(false) }
  }

  async function openConversation(conversationId) {
    if (loading) return
    setHistoryLoading(true); setHistoryError('')
    try {
      const data = await api(`/api/conversations/${conversationId}`)
      setActiveConversation(data.conversation)
      setMessages(data.messages || [])
      setConversationSources(data.sources || [])
      setShares(data.shares || [])
      setQuestion(''); setElapsed(0)
    } catch (err) { setHistoryError(err.message) }
    finally { setHistoryLoading(false) }
  }

  function clearConversation() {
    if (loading) return
    setActiveConversation(null); setMessages([]); setConversationSources([]); setShares([])
    setQuestion(''); setElapsed(0); setActiveTurnId(null); setShareOpen(false); setSourcesOpen(false)
  }

  function requestConversationDelete(event, conversationId) {
    event.stopPropagation()
    setDeleteConversationId(conversationId)
  }

  async function confirmConversationDelete() {
    const conversationId = deleteConversationId
    if (!conversationId) return
    setDeleteConversationLoading(true)
    try {
      await api(`/api/conversations/${conversationId}`, { method: 'DELETE' })
      if (activeConversation?.id === conversationId) clearConversation()
      await loadConversationList()
      setDeleteConversationId(null)
    } catch (err) { setHistoryError(err.message) }
    finally { setDeleteConversationLoading(false) }
  }

  async function shareConversation(event) {
    event.preventDefault()
    if (!activeConversation?.id || !shareEmail.trim()) return
    setShareLoading(true); setShareError('')
    try {
      await post(`/api/conversations/${activeConversation.id}/shares`, { email: shareEmail })
      const data = await api(`/api/conversations/${activeConversation.id}`)
      setShares(data.shares || []); setShareEmail('')
      loadConversationList()
    } catch (err) { setShareError(err.message) }
    finally { setShareLoading(false) }
  }

  async function unshare(sharedUserId) {
    if (!activeConversation?.id) return
    try {
      await api(`/api/conversations/${activeConversation.id}/shares/${sharedUserId}`, { method: 'DELETE' })
      setShares(current => current.filter(item => item.id !== sharedUserId))
      loadConversationList()
    } catch (err) { setShareError(err.message) }
  }

  function handleComposerKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      ask(event)
    }
  }

  const suggestions = [
    'Was the rear exit stair violation at 714 Marquette Street actually resolved?',
    'What hose size and crew size does SOP 204 require now?',
    'How should crews handle an e-bike battery fire?',
  ]
  const readOnly = activeConversation?.access === 'shared'
  const conversationTitle = activeConversation?.title || 'New conversation'
  return <div className="screen ask-screen simple-ask-screen">
    <div className="simple-chat-shell">
      <aside className="conversation-history-panel">
        <button className="history-new-chat" onClick={clearConversation} disabled={loading}><MessageSquarePlus size={16} /><span>New chat</span></button>
        <div className="history-panel-heading"><span><History size={13} /> Chats</span></div>
        {historyError && <div className="history-error">{historyError}</div>}
        {historyLoading && !conversations.length && <div className="history-loading"><LoaderCircle className="spin" size={15} /> Loading chats…</div>}
        <div className="conversation-list">{conversations.map(conversation => <article className={activeConversation?.id === conversation.id ? 'active' : ''} key={conversation.id}>
          <button className="conversation-open" onClick={() => openConversation(conversation.id)} disabled={loading}>
            <strong>{conversation.title}</strong><small>{conversation.access === 'shared' ? `Shared by ${conversation.owner_name}` : `${conversation.message_count} messages`}</small>
          </button>
          {conversation.access === 'shared' ? <span className="shared-badge"><Users size={10} /> Shared</span> : <button className="conversation-delete" onClick={event => requestConversationDelete(event, conversation.id)} aria-label={`Delete ${conversation.title}`}><Trash2 size={13} /></button>}
        </article>)}</div>
        {!historyLoading && !conversations.length && <div className="history-empty">Your saved conversations will appear here.</div>}
      </aside>

      <section className="simple-chat-main">
        <header className="simple-chat-header">
          <div className="chat-header-identity"><span><Sparkles size={16} /></span><div><strong>{conversationTitle}</strong><small>{readOnly ? `Shared by ${activeConversation.owner_name}` : 'Answers cite records you are cleared to read'}</small></div></div>
          <div className="chat-header-actions">
            <button className={sourcesOpen ? 'active' : ''} onClick={() => setSourcesOpen(value => !value)} aria-expanded={sourcesOpen}><BookOpen size={14} /><span>Sources</span><small>{conversationSources.length}</small></button>
            {activeConversation?.access === 'owner' && <button onClick={() => setShareOpen(true)} disabled={loading}><Share2 size={14} /><span>Share</span></button>}
          </div>
        </header>

        {sourcesOpen && <section className="simple-sources-drawer" aria-label="Conversation sources">
          <div><strong>Sources used in this conversation</strong><small>Most cited first</small></div>
          <div className="conversation-source-list">{conversationSources.map(source => <button key={source.document_id} onClick={() => onOpenDocument(source.document_id, source.page_number, source.snippet)}>
            <span>{source.rank}</span><div><strong>{source.document_title}</strong><small>Used {source.usage_count} {source.usage_count === 1 ? 'time' : 'times'} · Page {source.page_number}</small></div><ChevronRight size={13} />
          </button>)}</div>
          {!conversationSources.length && <div className="evidence-empty"><BookOpen size={18} /><span>Cited records will appear here.</span></div>}
        </section>}

        <div className="simple-chat-content">
          {!messages.length && <div className="simple-chat-empty"><span><Sparkles size={22} /></span><h1>Ask the department's records</h1><p>Answers are drawn only from records your role can see, with every claim linked to its source page.</p><div className="ask-suggestions">{suggestions.map(item =>
            <button key={item} onClick={() => ask(null, item)}><p>{item}</p><ChevronRight size={15} /></button>)}</div></div>}
          {messages.length > 0 && <div className="conversation-thread">{messages.map(message => message.role === 'user'
            ? <div className="chat-turn user-turn" key={message.id}><div className="chat-turn-body"><div className="chat-speaker"><strong>You</strong></div><div className="chat-bubble user-bubble">{message.content}</div></div></div>
            : <AssistantTurn key={message.id} message={message} question={messages[messages.indexOf(message) - 1]?.content} onOpenDocument={onOpenDocument} activeElapsed={message.id === activeTurnId ? elapsed : message.elapsed} />)}<div ref={threadEndRef} /></div>}
        </div>

        {readOnly ? <div className="shared-readonly"><Users size={15} /><span><strong>Shared conversation</strong><small>You can read this chat and open its evidence. Only the owner can continue it.</small></span></div> : <form className="ask-composer" onSubmit={ask}><textarea value={question} onChange={event => setQuestion(event.target.value)} onKeyDown={handleComposerKeyDown} rows="1" aria-label="Ask a question about the records" placeholder={messages.length ? 'Ask a follow-up…' : 'Ask about incidents, inspections, SOPs…'} /><button type={loading ? 'button' : 'submit'} onClick={loading ? stopStreaming : undefined} disabled={!loading && !question.trim()} aria-label={loading ? 'Stop generating' : 'Send message'}>{loading ? <><Square size={14} fill="currentColor" /><span>Stop</span></> : <><Send size={16} /><span>Send</span></>}</button></form>}
      </section>
    </div>

    {shareOpen && <div className="dialog-backdrop" role="presentation"><section className="share-dialog" role="dialog" aria-modal="true" aria-labelledby="share-title">
      <button className="dialog-close" onClick={() => setShareOpen(false)} aria-label="Close share dialog"><X size={17} /></button>
      <div className="share-dialog-icon"><Share2 /></div><p className="eyebrow">Read-only collaboration</p><h2 id="share-title">Share this conversation</h2><p>Invite another registered user by email. They can read the chat, and open cited records only if their own role allows it.</p>
      <form onSubmit={shareConversation}><label><Mail size={15} /><input type="email" value={shareEmail} onChange={event => setShareEmail(event.target.value)} placeholder="colleague@department.example" required /></label><button disabled={shareLoading}>{shareLoading ? <LoaderCircle className="spin" size={15} /> : 'Share'}</button></form>
      {shareError && <div className="share-error">{shareError}</div>}
      <div className="shared-people"><span>People with access · {shares.length}</span>{shares.map(person => <div key={person.id}><i>{person.display_name.slice(0, 1).toUpperCase()}</i><p><strong>{person.display_name}</strong><small>{person.email}</small></p><button onClick={() => unshare(person.id)}>Remove</button></div>)}{!shares.length && <p>No one else has access yet.</p>}</div>
    </section></div>}
    <ConfirmDialog
      open={Boolean(deleteConversationId)}
      title="Delete this conversation?"
      description="This permanently deletes the chat for you and everyone it was shared with. This action cannot be undone."
      confirmLabel="Delete conversation"
      destructive
      busy={deleteConversationLoading}
      onCancel={() => setDeleteConversationId(null)}
      onConfirm={confirmConversationDelete}
    />
  </div>
}

function CompareScreen({ documents }) {
  const [a, setA] = useState(null)
  const [b, setB] = useState(null)
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [deleteComparisonId, setDeleteComparisonId] = useState(null)
  const [deleteComparisonLoading, setDeleteComparisonLoading] = useState(false)

  useEffect(() => { loadHistory() }, [])

  async function loadHistory() {
    try { const data = await api('/api/comparisons'); setHistory(data.comparisons || []) }
    catch (err) { setError(err.message) }
    finally { setHistoryLoading(false) }
  }

  async function runCompare() {
    if (!a || !b || a.id === b.id) return
    setLoading(true); setError('')
    try {
      setResult(await post('/api/compare', { document_id_a: a.id, document_id_b: b.id }))
      await loadHistory()
    }
    catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  async function openComparison(comparisonId) {
    if (loading) return
    setHistoryLoading(true); setError('')
    try {
      const data = await api(`/api/comparisons/${comparisonId}`)
      const comparison = data.comparison
      setResult(comparison); setA(comparison.document_a); setB(comparison.document_b)
    } catch (err) { setError(err.message) }
    finally { setHistoryLoading(false) }
  }

  function requestComparisonDelete(event, comparisonId) {
    event.stopPropagation()
    setDeleteComparisonId(comparisonId)
  }

  async function confirmComparisonDelete() {
    const comparisonId = deleteComparisonId
    if (!comparisonId) return
    setDeleteComparisonLoading(true)
    try {
      await api(`/api/comparisons/${comparisonId}`, { method: 'DELETE' })
      if (result?.id === comparisonId) { setResult(null); setA(null); setB(null) }
      await loadHistory()
      setDeleteComparisonId(null)
    } catch (err) { setError(err.message) }
    finally { setDeleteComparisonLoading(false) }
  }

  function newComparison() { if (!loading) { setA(null); setB(null); setResult(null); setError('') } }

  return <div className="screen compare-screen">
    <div className="compare-heading-row"><div className="screen-heading"><p className="eyebrow">Version intelligence</p><h1>See what changed—and what it means.</h1><p>Type at least three letters to find each record, then save the analysis automatically.</p></div><button className="new-compare-button" onClick={newComparison} disabled={loading}><Plus size={15} /> New comparison</button></div>
    <div className="compare-workspace">
      <aside className="comparison-history-panel">
        <div className="history-panel-heading"><span><History size={14} /> Comparisons</span></div>
        {historyLoading && !history.length && <div className="history-loading"><LoaderCircle className="spin" size={15} /> Loading history…</div>}
        <div className="comparison-history-list">{history.map(comparison => <article className={result?.id === comparison.id ? 'active' : ''} key={comparison.id}>
          <button className="comparison-history-open" onClick={() => openComparison(comparison.id)} disabled={loading}><strong>{comparison.document_a.title}</strong><span><ArrowLeftRight size={10} /> {comparison.document_b.title}</span><small>{new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(comparison.created_at))}</small></button>
          <button className="comparison-history-delete" onClick={event => requestComparisonDelete(event, comparison.id)} aria-label={`Delete comparison between ${comparison.document_a.title} and ${comparison.document_b.title}`}><Trash2 size={13} /></button>
        </article>)}</div>
        {!historyLoading && !history.length && <div className="history-empty">Completed comparisons will appear here.</div>}
      </aside>
      <section className="comparison-stage">
        <div className="compare-picker">
          <RecordCombobox label="Original record" intent="original" documents={documents} value={a} onChange={setA} />
          <div className="compare-arrow"><ArrowLeftRight size={20} /></div>
          <RecordCombobox label="Revised record" intent="revised" documents={documents} value={b} onChange={setB} />
          <button className="primary-button" onClick={runCompare} disabled={!a || !b || a.id === b.id || loading}>{loading ? <LoaderCircle className="spin" /> : 'Compare'}</button>
        </div>
        {a && b && a.id === b.id && <div className="compare-validation">Choose two different records.</div>}
        <ErrorNotice error={error} onClose={() => setError('')} />
        {result && <>
          <article className="change-summary"><div className="summary-icon"><Sparkles /></div><div><span>Substantive change analysis</span><MarkdownAnswer dark>{result.summary}</MarkdownAnswer></div></article>
          <div className="diff-header"><strong>Text comparison</strong><div><span className="legend added"></span>Added <span className="legend removed"></span>Removed</div></div>
          <div className="diff-view">{result.diff.map((line, index) => <div className={`diff-line ${line.type}`} key={index}><span>{line.type === 'added' ? '+' : line.type === 'removed' ? '−' : ' '}</span><code>{line.text || ' '}</code></div>)}</div>
        </>}
        {!result && !loading && <EmptyState icon={ArrowLeftRight} title="Choose two records">Type at least three letters in each field, for example “SOP 204”.</EmptyState>}
      </section>
    </div>
    <ConfirmDialog
      open={Boolean(deleteComparisonId)}
      title="Delete this saved comparison?"
      description="This removes the comparison from your history. The original records will not be affected."
      confirmLabel="Delete comparison"
      destructive
      busy={deleteComparisonLoading}
      onCancel={() => setDeleteComparisonId(null)}
      onConfirm={confirmComparisonDelete}
    />
  </div>
}

const uploadStages = ['Parsing document', 'OCR check', 'Creating passages', 'Building embeddings', 'Extracting entities', 'Ready']

function UploadScreen({ onComplete, user }) {
  const canIngest = user.permissions?.includes('ingest')
  const allowedClasses = classificationOrder.filter(item => user.classifications?.includes(item))
  const [classification, setClassification] = useState('internal')
  const [file, setFile] = useState(null)
  const [stage, setStage] = useState(-1)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)

  async function upload(selected = file) {
    if (!selected) return
    setFile(selected); setResult(null); setError(''); setStage(0)
    const timer = window.setInterval(() => setStage(value => Math.min(value + 1, 4)), 950)
    const body = new FormData(); body.append('file', selected); body.append('classification', classification)
    try {
      const data = await api('/api/documents/upload', { method: 'POST', body })
      setStage(5); setResult(data); onComplete?.()
    } catch (err) { setError(err.message); setStage(-1) }
    finally { window.clearInterval(timer) }
  }

  function choose(files) { const selected = files?.[0]; if (selected) upload(selected) }
  return <div className="screen upload-screen">
    <div className="screen-heading"><p className="eyebrow">Local ingestion</p><h1>Add a record to the collection.</h1><p>Parsing, OCR for scanned pages, chunking, embedding, and entity extraction all run on this server.</p></div>
    {!canIngest && <div className="policy-notice"><LockKeyhole size={16} /><span><strong>Your role can't add records.</strong> Ingestion requires the Fire Officer or Records Administrator role. This attempt would be logged.</span></div>}
    {canIngest && !result && stage < 0 && <div className="classify-row" role="radiogroup" aria-label="Classification for the new record"><span>Classify as</span>{allowedClasses.map(item => <button key={item} role="radio" aria-checked={classification === item} className={classification === item ? 'active' : ''} onClick={() => setClassification(item)}><ClassificationBadge value={item} /></button>)}</div>}
    {canIngest && !result && stage < 0 && <label className={`dropzone ${dragging ? 'dragging' : ''}`} onDragOver={e => { e.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={e => { e.preventDefault(); setDragging(false); choose(e.dataTransfer.files) }}>
      <input type="file" accept=".pdf,.docx,.txt,.md" onChange={e => choose(e.target.files)} />
      <div className="upload-icon"><UploadCloud /></div><h3>Drop a record here</h3><p>or click to browse · PDF, DOCX, TXT, MD</p>
    </label>}
    <ErrorNotice error={error} onClose={() => setError('')} />
    {stage >= 0 && !result && <div className="ingestion-card"><div className="file-chip"><div><BookOpen /></div><p><strong>{file?.name}</strong><span>{file ? `${(file.size / 1024).toFixed(1)} KB` : ''}</span></p></div><div className="stage-list">{uploadStages.map((item, index) =>
      <div key={item} className={index < stage ? 'done' : index === stage ? 'active' : ''}><span>{index < stage ? <Check size={15} /> : index === stage ? <LoaderCircle className="spin" size={15} /> : index + 1}</span><p>{item}</p><small>{index < stage ? 'Complete' : index === stage ? 'Working locally…' : 'Waiting'}</small></div>)}</div></div>}
    {result && <div className="upload-success"><div className="success-pulse"><Check /></div><p className="eyebrow">Ingestion complete</p><h2>{result.title}</h2><p>The record is searchable now for roles cleared for <strong>{result.classification}</strong> records, and the knowledge graph has been updated.</p><div className="ingest-metrics"><span><strong>{result.page_count}</strong> pages</span><span><strong>{result.chunk_count}</strong> passages</span><span><strong>{result.entity_count}</strong> entities</span><span><strong>{result.relation_count}</strong> links</span></div><button className="primary-button" onClick={() => onComplete(result.document_id)}>Open new document <ChevronRight size={16} /></button></div>}
  </div>
}

function AuthenticatedApp({ user, onLogout }) {
  const contentAreaRef = useRef(null)
  const viewerReturnScrollRef = useRef(0)
  const initialTab = tabs.some(tab => tab.id === window.location.hash.slice(1)) ? window.location.hash.slice(1) : 'ask'
  const [activeTab, setActiveTab] = useState(initialTab)
  const [visitedTabs, setVisitedTabs] = useState(() => new Set([initialTab]))
  const [documents, setDocuments] = useState([])
  const [hiddenCount, setHiddenCount] = useState(0)
  const [health, setHealth] = useState(null)
  const [viewer, setViewer] = useState(null)
  const [viewerHistory, setViewerHistory] = useState([])
  const [viewerReturnTab, setViewerReturnTab] = useState('search')

  async function refresh() {
    const [docData, healthData] = await Promise.all([api('/api/documents'), api('/api/health')]).catch(() => [{ documents: [] }, null])
    setDocuments(docData?.documents || []); setHiddenCount(docData?.hidden_by_policy || 0); setHealth(healthData)
  }
  useEffect(() => { refresh() }, [])

  function scrollContent(top = 0) {
    window.requestAnimationFrame(() => window.requestAnimationFrame(() => {
      contentAreaRef.current?.scrollTo({ top, left: 0 })
    }))
  }

  function openDocument(documentId, page = 1, snippet = '') {
    const nextViewer = { documentId, page, snippet }
    if (activeTab === 'viewer') {
      if (viewer) {
        const scrollTop = contentAreaRef.current?.scrollTop || 0
        setViewerHistory(history => [...history, { ...viewer, scrollTop }])
      }
    } else {
      setViewerReturnTab(activeTab)
      viewerReturnScrollRef.current = contentAreaRef.current?.scrollTop || 0
      setViewerHistory([])
    }
    setViewer(nextViewer)
    setActiveTab('viewer')
    scrollContent(0)
  }
  function backFromViewer() {
    if (viewerHistory.length) {
      const { scrollTop = 0, ...previousViewer } = viewerHistory.at(-1)
      setViewer(previousViewer)
      setViewerHistory(viewerHistory.slice(0, -1))
      scrollContent(scrollTop)
      return
    }
    setViewer(null)
    setActiveTab(viewerReturnTab)
    scrollContent(viewerReturnScrollRef.current)
  }
  function changeTab(id) {
    setVisitedTabs(current => current.has(id) ? current : new Set([...current, id]))
    setActiveTab(id)
    setViewer(null)
    setViewerHistory([])
    scrollContent(0)
  }
  const viewerBackLabel = viewerHistory.length
    ? 'Back to previous document'
    : {
        search: 'Back to search results',
        files: 'Back to files',
        ask: 'Back to question and answer',
        access: 'Back to access & audit',
        compare: 'Back to comparison',
        graph: 'Back to knowledge graph',
        upload: 'Back to upload',
      }[viewerReturnTab] || 'Back'

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><BrandMark size={40} /><div><strong>{PRODUCT}</strong><span>{health?.deployment || 'On-prem deployment'}</span></div></div>
      <nav>{tabs.map(tab => { const Icon = tab.icon; return <button key={tab.id} className={activeTab === tab.id ? 'active' : ''} onClick={() => changeTab(tab.id)}><Icon size={18} /><span>{tab.label}</span>{activeTab === tab.id && <i />}</button> })}</nav>
      <div className="role-card" aria-label="Your access level">
        <div className="role-card-head"><ShieldCheck size={14} /><span>{user.role_label}</span></div>
        <div className="role-levels">{classificationOrder.map(item => <span key={item} className={user.classifications?.includes(item) ? 'on' : 'off'} title={`${item}: ${user.classifications?.includes(item) ? 'visible' : 'withheld'}`}>{item.slice(0, 1).toUpperCase() + item.slice(1)}</span>)}</div>
        <small>{documents.length} records visible{hiddenCount ? ` · ${hiddenCount} withheld by policy` : ''}</small>
      </div>
      <div className="account-card"><span>{user.display_name.replace(/^(Capt\.|FF)\s/, '').slice(0, 1).toUpperCase()}</span><p><strong>{user.display_name}</strong><small>{user.email}</small></p><button onClick={onLogout} aria-label="Sign out"><LogOut size={15} /></button></div>
      <div className="local-status"><span className={health?.local_ai?.available ? 'online' : 'offline'}></span><div><strong>Air-gapped runtime</strong><small>{health?.local_ai?.provider === 'demo' ? 'Demo provider · no LLM' : health?.local_ai?.available ? `Local model · ${health.local_ai.llm_model}` : 'Local model unavailable'}</small></div></div>
    </aside>
    <main className="main-area">
      <header className="topbar"><BrandMark className="topbar-mark" size={34} /><div className="topbar-context"><span className="net-pill"><LockKeyhole size={12} /> Air-gapped · 0 external connections</span>{health?.demo_mode && <span className="demo-pill">Fictional demo data</span>}</div><div className="topbar-actions"><span className="topbar-user">{user.display_name}</span><button className="mobile-logout" onClick={onLogout} aria-label="Sign out"><span>{user.display_name.slice(0, 1).toUpperCase()}</span><LogOut size={13} /></button></div></header>
      <div className="content-area" ref={contentAreaRef}>
        {tabs.map(tab => visitedTabs.has(tab.id) && <div className={`screen-route ${activeTab === tab.id ? 'active' : ''}`} key={tab.id} aria-hidden={activeTab !== tab.id}>
          {tab.id === 'search' && <SearchScreen onOpenDocument={openDocument} />}
          {tab.id === 'files' && <FileExplorer onOpenDocument={openDocument} onDocumentsChanged={refresh} />}
          {tab.id === 'ask' && <AskScreen onOpenDocument={openDocument} />}
          {tab.id === 'compare' && <CompareScreen documents={documents} />}
          {tab.id === 'graph' && <Suspense fallback={<div className="screen document-loading"><LoaderCircle className="spin" /> Loading 3D workspace…</div>}><GraphView onOpenDocument={openDocument} /></Suspense>}
          {tab.id === 'access' && <AccessAudit user={user} />}
          {tab.id === 'upload' && <UploadScreen user={user} onComplete={(id) => { refresh(); if (id) openDocument(id) }} />}
        </div>)}
        {activeTab === 'viewer' && viewer && <DocumentViewer {...viewer} backLabel={viewerBackLabel} onBack={backFromViewer} onOpenDocument={openDocument} />}
      </div>
    </main>
  </div>
}

function App() {
  const [authLoading, setAuthLoading] = useState(true)
  const [user, setUser] = useState(null)

  useEffect(() => {
    api('/api/auth/me').then(data => setUser(data.user)).catch(() => setUser(null)).finally(() => setAuthLoading(false))
  }, [])

  async function logout() {
    try { await post('/api/auth/logout', {}) } catch { /* Clear the local UI session even if the server is restarting. */ }
    setUser(null)
  }

  if (authLoading) return <div className="auth-loading"><BrandMark size={40} /><LoaderCircle className="spin" /> Loading {PRODUCT}…</div>
  if (!user) return <AuthScreen onAuthenticated={setUser} />
  return <AuthenticatedApp user={user} onLogout={logout} />
}

export default App
