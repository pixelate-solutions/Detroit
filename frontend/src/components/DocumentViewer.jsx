import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, ChevronRight, Download, LoaderCircle, Network, Search, Sparkles } from 'lucide-react'
import { api, post } from '../api'
import { ClassificationBadge, OcrBadge, TypeBadge } from './ui/Badges'

function highlightText(text, snippet) {
  const words = [...new Set((snippet || '').toLowerCase().match(/[a-z0-9-]{4,}/g) || [])].slice(0, 12)
  if (!words.length) return text
  const regex = new RegExp(`(${words.map(word => word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi')
  return text.split(regex).map((part, i) => words.includes(part.toLowerCase()) ? <mark key={i}>{part}</mark> : part)
}

function PdfPage({ pdf, pageNumber, targetPage, snippet }) {
  const canvasRef = useRef(null)
  const layerRef = useRef(null)
  const pageRef = useRef(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function render() {
      const page = await pdf.getPage(pageNumber)
      if (cancelled) return
      const viewport = page.getViewport({ scale: 1.28 })
      const ratio = window.devicePixelRatio || 1
      const canvas = canvasRef.current
      const context = canvas.getContext('2d')
      canvas.width = Math.floor(viewport.width * ratio)
      canvas.height = Math.floor(viewport.height * ratio)
      canvas.style.width = `${viewport.width}px`
      canvas.style.height = `${viewport.height}px`
      await page.render({ canvasContext: context, viewport, transform: ratio === 1 ? null : [ratio, 0, 0, ratio, 0, 0] }).promise
      if (cancelled) return
      const textContent = await page.getTextContent()
      const layer = layerRef.current
      layer.innerHTML = ''
      layer.style.width = `${viewport.width}px`; layer.style.height = `${viewport.height}px`
      const terms = [...new Set((snippet || '').toLowerCase().match(/[a-z0-9-]{4,}/g) || [])].slice(0, 14)
      for (const item of textContent.items) {
        if (!item.str) continue
        const transform = viewport.transform
        const tx = [
          transform[0] * item.transform[0] + transform[2] * item.transform[1],
          transform[1] * item.transform[0] + transform[3] * item.transform[1],
          transform[0] * item.transform[2] + transform[2] * item.transform[3],
          transform[1] * item.transform[2] + transform[3] * item.transform[3],
          transform[0] * item.transform[4] + transform[2] * item.transform[5] + transform[4],
          transform[1] * item.transform[4] + transform[3] * item.transform[5] + transform[5],
        ]
        const fontHeight = Math.hypot(tx[2], tx[3])
        const span = document.createElement('span')
        span.textContent = item.str
        span.style.left = `${tx[4]}px`; span.style.top = `${tx[5] - fontHeight}px`; span.style.fontSize = `${fontHeight}px`
        span.style.transform = `scaleX(${item.width && item.str.length ? Math.max(.65, Math.min(1.35, (item.width * viewport.scale) / (item.str.length * fontHeight * .5))) : 1})`
        if (pageNumber === targetPage && terms.some(term => item.str.toLowerCase().includes(term))) span.className = 'pdf-highlight'
        layer.appendChild(span)
      }
      setReady(true)
      if (pageNumber === targetPage && pageNumber > 1) {
        setTimeout(() => pageRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 120)
      }
    }
    render().catch(() => setReady(true))
    return () => { cancelled = true }
  }, [pdf, pageNumber, targetPage, snippet])

  return <section ref={pageRef} className={`pdf-page ${pageNumber === targetPage ? 'target' : ''}`}>
    <span className="page-label">Page {pageNumber}</span>
    <canvas ref={canvasRef} />
    <div ref={layerRef} className="pdf-text-layer" />
    {!ready && <LoaderCircle className="page-loader spin" />}
  </section>
}

function PdfViewer({ documentId, pageNumber, snippet }) {
  const [pdf, setPdf] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let current
    let cancelled = false
    async function load() {
      try {
        const pdfjs = await import('pdfjs-dist')
        const worker = await import('pdfjs-dist/build/pdf.worker.min.mjs?url')
        pdfjs.GlobalWorkerOptions.workerSrc = worker.default
        current = await pdfjs.getDocument(`/api/documents/${documentId}/file`).promise
        if (!cancelled) setPdf(current)
      } catch (err) { if (!cancelled) setError(err.message) }
    }
    load()
    return () => { cancelled = true; current?.destroy() }
  }, [documentId])
  if (error) return <div className="viewer-error">Could not render this PDF: {error}</div>
  if (!pdf) return <div className="document-loading"><LoaderCircle className="spin" /> Rendering local document…</div>
  return <div className="pdf-pages">{Array.from({ length: pdf.numPages }, (_, i) => <PdfPage key={i + 1} pdf={pdf} pageNumber={i + 1} targetPage={pageNumber} snippet={snippet} />)}</div>
}

export default function DocumentViewer({ documentId, page = 1, snippet = '', backLabel = 'Back', onBack, onOpenDocument }) {
  const [document, setDocument] = useState(null)
  const [related, setRelated] = useState([])
  const [error, setError] = useState('')
  useEffect(() => {
    setDocument(null); setRelated([]); setError('')
    api(`/api/documents/${documentId}`).then(data => {
      setDocument(data)
      post('/api/recommend', {
        text: `${data.title}\n${data.full_text.slice(0, 1400)}`,
        exclude_document_id: documentId,
        top_k: 4,
      }).then(result => setRelated(result.documents)).catch(() => setRelated([]))
    }).catch(err => setError(err.message))
  }, [documentId])

  if (error) return <div className="screen"><button className="back-button" onClick={onBack}><ArrowLeft /> {backLabel}</button><div className="error-notice"><div><strong>Access withheld</strong><span>{error} This attempt was recorded in the audit log.</span></div></div></div>
  if (!document) return <div className="screen document-loading"><LoaderCircle className="spin" /> Loading document…</div>
  const isPdf = document.filename.toLowerCase().endsWith('.pdf')

  return <div className="screen viewer-screen">
    <div className="viewer-toolbar"><button className="back-button" onClick={onBack}><ArrowLeft size={17} /> {backLabel}</button><div className="viewer-toolbar-actions"><div className="viewer-file-meta"><ClassificationBadge value={document.classification} /><OcrBadge status={document.ocr_status} /><TypeBadge type={document.doc_type} /><span>{document.page_count} {document.page_count === 1 ? 'page' : 'pages'}</span></div><a className="viewer-download-button" href={`/api/documents/${document.id}/file`} download={document.filename}><Download size={15} /><span>Download</span></a></div></div>
    <div className="viewer-title"><div><p className="eyebrow">Record #{document.id}{document.source_unit ? ` · ${document.source_unit}` : ''}</p><h1>{document.title}</h1></div>{snippet && <div className="match-indicator"><Search size={15} /> Matched passage highlighted on page {page}</div>}</div>
    <div className="viewer-layout">
      <div className="document-canvas-wrap">{isPdf ? <PdfViewer documentId={documentId} pageNumber={page} snippet={snippet} /> : <div className="plain-document">{document.full_text.split('\n').map((line, index) => <p key={index}>{highlightText(line, snippet)}</p>)}</div>}</div>
      <aside className="document-sidebar">
        <section><div className="panel-label"><Network size={14} /> Extracted entities · {document.entities.length}</div><div className="entity-list">{document.entities.map((entity, index) => <div key={`${entity.name}-${index}`}><span className={`entity-dot entity-${entity.entityType}`}></span><p><strong>{entity.name}</strong><small>{entity.entityType.replaceAll('_', ' ')}</small></p></div>)}</div>{!document.entities.length && <p className="muted">No entities extracted.</p>}</section>
        <section><div className="panel-label"><Sparkles size={14} /> Related records</div><div className="related-list">{related.map(item => <button key={item.document_id} onClick={() => onOpenDocument(item.document_id, 1, item.snippet)}><div><TypeBadge type={item.doc_type} /><strong>{item.title}</strong><small>{Math.round(item.score * 100)}% semantic match</small></div><ChevronRight size={15} /></button>)}</div>{!related.length && <p className="muted">No related records yet.</p>}</section>
      </aside>
    </div>
  </div>
}
