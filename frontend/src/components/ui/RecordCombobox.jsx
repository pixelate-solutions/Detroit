import { useEffect, useMemo, useRef, useState } from 'react'
import { Check, ChevronDown, FileText, Search, X } from 'lucide-react'

function matchScore(document, query, intent) {
  const title = document.title.toLowerCase()
  const filename = (document.filename || '').toLowerCase()
  const type = (document.doc_type || '').replaceAll('_', ' ').toLowerCase()
  let score = Number.POSITIVE_INFINITY
  if (title === query) score = 0
  else if (title.startsWith(query)) score = 1
  else if (title.split(/\s+/).some(word => word.startsWith(query))) score = 2
  else if (title.includes(query)) score = 3
  else if (filename.startsWith(query)) score = 4
  else if (filename.includes(query)) score = 5
  else if (type.includes(query)) score = 6
  if (Number.isFinite(score) && intent === 'original' && /original|prior|previous/.test(title)) score -= .75
  if (Number.isFinite(score) && intent === 'revised' && /amendment|revised|updated|final/.test(title)) score -= .75
  return score
}

export default function RecordCombobox({ documents, value, onChange, label, intent, placeholder = 'Type at least 3 letters…' }) {
  const [query, setQuery] = useState(value?.title || '')
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const rootRef = useRef(null)

  useEffect(() => { setQuery(value?.title || '') }, [value?.id])
  useEffect(() => {
    function close(event) { if (!rootRef.current?.contains(event.target)) setOpen(false) }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [])

  const results = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    if (normalized.length < 3) return []
    return documents
      .map(document => ({ document, score: matchScore(document, normalized, intent) }))
      .filter(item => Number.isFinite(item.score))
      .sort((a, b) => a.score - b.score || a.document.title.localeCompare(b.document.title))
      .slice(0, 15)
      .map(item => item.document)
  }, [documents, query, intent])

  function choose(document) {
    onChange(document)
    setQuery(document.title)
    setOpen(false)
  }

  function handleKeyDown(event) {
    if (event.key === 'Escape') { setOpen(false); return }
    if (!open || !results.length) return
    if (event.key === 'ArrowDown') {
      event.preventDefault(); setActiveIndex(index => (index + 1) % results.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault(); setActiveIndex(index => (index - 1 + results.length) % results.length)
    } else if (event.key === 'Enter') {
      event.preventDefault(); choose(results[activeIndex])
    }
  }

  return <label className="record-combobox" ref={rootRef}>
    <span>{label}</span>
    <div className={`record-combobox-input ${open ? 'open' : ''}`}>
      <Search size={16} />
      <input
        value={query}
        onFocus={() => query.trim().length >= 3 && setOpen(true)}
        onChange={event => {
          const next = event.target.value
          setQuery(next); setActiveIndex(0); setOpen(next.trim().length >= 3)
          if (!value || next !== value.title) onChange(null)
        }}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
        aria-controls={`${label.replaceAll(' ', '-').toLowerCase()}-options`}
      />
      {query ? <button type="button" aria-label={`Clear ${label}`} onClick={() => { setQuery(''); onChange(null); setOpen(false) }}><X size={14} /></button> : <ChevronDown size={15} />}
    </div>
    {query.trim().length > 0 && query.trim().length < 3 && <small className="combobox-hint">Type {3 - query.trim().length} more {3 - query.trim().length === 1 ? 'letter' : 'letters'}</small>}
    {open && <div className="record-combobox-menu" id={`${label.replaceAll(' ', '-').toLowerCase()}-options`} role="listbox">
      {results.map((document, index) => <button
        type="button"
        role="option"
        aria-selected={value?.id === document.id}
        className={index === activeIndex ? 'active' : ''}
        key={document.id}
        onPointerMove={() => setActiveIndex(index)}
        onClick={() => choose(document)}
      >
        <span className="combobox-file-icon"><FileText size={15} /></span>
        <span><strong>{document.title}</strong><small>{(document.doc_type || 'record').replaceAll('_', ' ')} · {document.filename}</small></span>
        {value?.id === document.id && <Check size={15} />}
      </button>)}
      {!results.length && <div className="combobox-empty">No matching records</div>}
    </div>}
  </label>
}
