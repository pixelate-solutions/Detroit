import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ArchiveRestore, ArrowDownAZ, ArrowUpAZ, ChevronLeft, ChevronRight, Download, File, FileText,
  Folder, FolderOpen, Grid2X2, HardDrive, Home, LayoutList, LoaderCircle, MoreHorizontal,
  Move, Pencil, Plus, RefreshCw, Search, Star, Trash2, Upload, X,
} from 'lucide-react'
import { api, post } from '../api'
import SelectMenu from './ui/SelectMenu'
import { ClassificationBadge, OcrBadge } from './ui/Badges'

const emptyData = { folders: [], files: [], breadcrumbs: [], counts: { documents: 0, starred: 0, trash: 0 } }
const itemDragType = 'application/x-civic-records-items'

function formatSize(bytes) {
  if (!bytes) return '0 KB'
  const units = ['B', 'KB', 'MB', 'GB']
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const value = bytes / (1024 ** index)
  return `${value >= 10 || index === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[index]}`
}

function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(date)
}

function itemKey(item) { return `${item.kind}:${item.id}` }

function FileGlyph({ item }) {
  if (item.kind === 'folder') return <span className="explorer-glyph folder"><Folder size={21} fill="currentColor" /></span>
  return <span className={`explorer-glyph file ${item.extension}`}><FileText size={20} /></span>
}

function ExplorerDialog({ dialog, folders, onClose, onSubmit, onCreateFolder, busy }) {
  const [name, setName] = useState(dialog?.initialName || '')
  const [destination, setDestination] = useState(dialog?.initialFolder ?? 'root')
  const [creatingDestination, setCreatingDestination] = useState(false)
  const [destinationName, setDestinationName] = useState('')
  const [createdFolders, setCreatedFolders] = useState([])
  const [createError, setCreateError] = useState('')
  useEffect(() => {
    setName(dialog?.initialName || '')
    setDestination(dialog?.initialFolder ?? 'root')
    setCreatingDestination(false)
    setDestinationName('')
    setCreatedFolders([])
    setCreateError('')
  }, [dialog])
  if (!dialog) return null
  const isMove = dialog.type === 'move'
  const isConfirm = dialog.type === 'confirm'
  const folderItemCount = dialog.items?.length || 0
  const title = dialog.type === 'new-folder'
    ? folderItemCount ? `Create a folder for ${folderItemCount} ${folderItemCount === 1 ? 'item' : 'items'}` : 'Create a folder'
    : dialog.type === 'rename' ? `Rename ${dialog.kind}`
      : isMove ? 'Move selected items'
        : dialog.restore ? 'Restore selected files?' : 'Move selected items to Trash?'
  const optionFolders = [...folders, ...createdFolders].filter((folder, index, values) => values.findIndex(value => value.id === folder.id) === index)
  const options = [{ value: 'root', label: 'All records' }, ...optionFolders.filter(folder => !dialog.excludeIds?.includes(folder.id)).map(folder => ({ value: folder.id, label: folder.name }))]

  async function createDestination() {
    const cleanName = destinationName.trim()
    if (!cleanName) return
    setCreateError('')
    try {
      const folder = await onCreateFolder(cleanName, destination === 'root' ? null : destination)
      setCreatedFolders(current => [...current, folder])
      setDestination(folder.id)
      setDestinationName('')
      setCreatingDestination(false)
    } catch (err) { setCreateError(err.message) }
  }

  return <div className="dialog-backdrop" role="presentation"><section className="explorer-dialog" role="dialog" aria-modal="true" aria-labelledby="explorer-dialog-title">
    <button className="dialog-close" onClick={onClose} aria-label="Close dialog"><X size={17} /></button>
    <div className="explorer-dialog-icon">{isMove ? <Move /> : dialog.type === 'new-folder' ? <Folder /> : isConfirm ? dialog.restore ? <ArchiveRestore /> : <Trash2 /> : <Pencil />}</div>
    <p className="eyebrow">File organization</p><h2 id="explorer-dialog-title">{title}</h2>
    <form onSubmit={event => { event.preventDefault(); onSubmit(isMove ? destination : name) }}>
      {isConfirm ? <p className="explorer-confirm-copy">{dialog.restore ? 'The files will return to their previous folders.' : 'Documents can be restored later from Trash. Empty folders are removed from your organization view.'}</p> : isMove ? <>
        <label>Destination</label>
        <SelectMenu value={destination} onValueChange={setDestination} options={options} ariaLabel="Choose destination folder" className="move-folder-select" />
        {!creatingDestination ? <button type="button" className="move-new-folder-button" onClick={() => setCreatingDestination(true)}><Plus size={15} /> New folder</button> : <div className="move-new-folder-form">
          <label htmlFor="move-new-folder-name">New folder name</label>
          <div><input id="move-new-folder-name" value={destinationName} onChange={event => setDestinationName(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); createDestination() } }} autoFocus maxLength="180" placeholder="Folder name" /><button type="button" onClick={createDestination} disabled={busy || !destinationName.trim()}>{busy ? <LoaderCircle className="spin" size={14} /> : 'Create'}</button><button type="button" aria-label="Cancel new folder" onClick={() => { setCreatingDestination(false); setDestinationName(''); setCreateError('') }}><X size={14} /></button></div>
          {createError && <span role="alert">{createError}</span>}
        </div>}
      </> : <><label htmlFor="explorer-name">Name</label><input id="explorer-name" value={name} onChange={event => setName(event.target.value)} autoFocus maxLength="180" required /></>}
      <div className="explorer-dialog-actions"><button type="button" onClick={onClose}>Cancel</button><button className="primary-button" disabled={busy || creatingDestination || (!isMove && !isConfirm && !name.trim())}>{busy ? <LoaderCircle className="spin" size={15} /> : isConfirm ? dialog.restore ? 'Restore files' : 'Move to Trash' : isMove ? 'Move here' : dialog.type === 'new-folder' ? folderItemCount ? 'Create and move' : 'Create folder' : 'Save name'}</button></div>
    </form>
  </section></div>
}

export default function FileExplorer({ onOpenDocument, onDocumentsChanged }) {
  const [data, setData] = useState(emptyData)
  const [allFolders, setAllFolders] = useState([])
  const [view, setView] = useState('root')
  const [folderId, setFolderId] = useState(null)
  const [query, setQuery] = useState('')
  const [display, setDisplay] = useState('list')
  const [sort, setSort] = useState('name')
  const [ascending, setAscending] = useState(true)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState('10')
  const [selected, setSelected] = useState(new Set())
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [dialog, setDialog] = useState(null)
  const [dragTargetId, setDragTargetId] = useState(null)
  const [draggingItemKeys, setDraggingItemKeys] = useState([])
  const [externalDragActive, setExternalDragActive] = useState(false)
  const [externalDragCount, setExternalDragCount] = useState(0)
  const [refreshKey, setRefreshKey] = useState(0)
  const uploadRef = useRef(null)
  const dragItemsRef = useRef([])
  const selectionAnchorRef = useRef(null)
  const externalDragDepthRef = useRef(0)

  const effectiveView = query.trim() ? 'search' : view
  useEffect(() => {
    const timer = window.setTimeout(async () => {
      setLoading(true); setError('')
      try {
        const params = new URLSearchParams({ view: effectiveView })
        if (effectiveView === 'folder' && folderId) params.set('folder_id', folderId)
        if (effectiveView === 'search') params.set('query', query.trim())
        const [filesData, folderData] = await Promise.all([api(`/api/files?${params}`), api('/api/file-folders')])
        setData(filesData); setAllFolders(folderData.folders || []); setSelected(new Set()); selectionAnchorRef.current = null
      } catch (err) { setError(err.message) }
      finally { setLoading(false) }
    }, query.trim() ? 180 : 0)
    return () => window.clearTimeout(timer)
  }, [effectiveView, folderId, query, refreshKey])

  const items = useMemo(() => {
    const combined = [
      ...data.folders.map(folder => ({ ...folder, kind: 'folder', modified_at: folder.updated_at, size_bytes: 0 })),
      ...data.files.map(file => ({ ...file, kind: 'file' })),
    ]
    const direction = ascending ? 1 : -1
    return combined.sort((a, b) => {
      if (a.kind !== b.kind) return a.kind === 'folder' ? -1 : 1
      let left = a.name.toLowerCase(); let right = b.name.toLowerCase()
      if (sort === 'size') { left = a.size_bytes; right = b.size_bytes }
      if (sort === 'modified') { left = a.modified_at || ''; right = b.modified_at || '' }
      if (sort === 'type') { left = a.kind === 'folder' ? 'folder' : a.extension; right = b.kind === 'folder' ? 'folder' : b.extension }
      return (left < right ? -1 : left > right ? 1 : 0) * direction
    })
  }, [data, sort, ascending])

  const pageLimit = Number(pageSize)
  const totalPages = Math.max(1, Math.ceil(items.length / pageLimit))
  const pageItems = useMemo(() => items.slice((page - 1) * pageLimit, page * pageLimit), [items, page, pageLimit])
  const pageNumbers = useMemo(() => {
    const start = Math.max(1, Math.min(page - 2, totalPages - 4))
    const end = Math.min(totalPages, start + 4)
    return Array.from({ length: end - start + 1 }, (_, index) => start + index)
  }, [page, totalPages])
  const pageStart = items.length ? (page - 1) * pageLimit + 1 : 0
  const pageEnd = Math.min(page * pageLimit, items.length)

  const selectedItems = useMemo(() => items.filter(item => selected.has(itemKey(item))), [items, selected])
  const oneSelected = selectedItems.length === 1 ? selectedItems[0] : null

  useEffect(() => { setPage(1) }, [effectiveView, folderId, query, sort, ascending, pageSize])
  useEffect(() => { setPage(current => Math.min(current, totalPages)) }, [totalPages])

  useEffect(() => {
    function createFolderWithShortcut(event) {
      if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== 'n') return
      const target = event.target
      const isTyping = target instanceof HTMLElement && (
        target.isContentEditable
        || Boolean(target.closest('textarea, select'))
        || Boolean(target.closest('input:not([type="checkbox"]):not([type="radio"]):not([type="button"])'))
      )
      if (isTyping) return
      event.preventDefault()
      if (dialog || busy || view === 'trash') return
      setDialog({ type: 'new-folder', items: selectedItems })
    }
    window.addEventListener('keydown', createFolderWithShortcut)
    return () => window.removeEventListener('keydown', createFolderWithShortcut)
  }, [busy, dialog, selectedItems, view])

  function reload() { setRefreshKey(value => value + 1) }
  function navigate(nextView, nextFolder = null) { setQuery(''); setView(nextView); setFolderId(nextFolder); setSelected(new Set()); selectionAnchorRef.current = null }
  function openNewFolderDialog() { setDialog({ type: 'new-folder', items: [] }) }
  function openItem(item) { if (item.kind === 'folder') navigate('folder', item.id); else onOpenDocument(item.id, 1, '') }
  function downloadItem(item) {
    if (!item || item.kind !== 'file') return
    const link = window.document.createElement('a')
    link.href = `/api/documents/${item.id}/file`
    link.download = item.filename || item.name
    window.document.body.appendChild(link)
    link.click()
    link.remove()
  }
  function toggle(item, checked, shiftKey = false) {
    const key = itemKey(item)
    const anchorIndex = selectionAnchorRef.current
      ? items.findIndex(candidate => itemKey(candidate) === selectionAnchorRef.current)
      : -1
    const itemIndex = items.findIndex(candidate => itemKey(candidate) === key)
    setSelected(current => {
      const next = new Set(current)
      if (shiftKey && anchorIndex >= 0 && itemIndex >= 0) {
        const start = Math.min(anchorIndex, itemIndex)
        const end = Math.max(anchorIndex, itemIndex)
        items.slice(start, end + 1).forEach(candidate => {
          const candidateKey = itemKey(candidate)
          if (checked) next.add(candidateKey); else next.delete(candidateKey)
        })
      } else if (checked) next.add(key)
      else next.delete(key)
      return next
    })
    if (!shiftKey || anchorIndex < 0) selectionAnchorRef.current = key
  }
  function selectFromItemSurface(event, item) {
    if (event.target.closest('button, a, input, label')) return
    const key = itemKey(item)
    if (event.shiftKey && selectionAnchorRef.current) {
      event.preventDefault()
      toggle(item, true, true)
      return
    }
    if (event.metaKey || event.ctrlKey) {
      toggle(item, !selected.has(key))
      return
    }
    setSelected(new Set([key]))
    selectionAnchorRef.current = key
  }
  function toggleAll(checked) {
    setSelected(current => {
      const next = new Set(current)
      pageItems.forEach(item => { if (checked) next.add(itemKey(item)); else next.delete(itemKey(item)) })
      return next
    })
    selectionAnchorRef.current = null
  }

  function excludedFolderIds(moveItems) {
    const excluded = new Set(moveItems.filter(item => item.kind === 'folder').map(item => item.id))
    let changed = true
    while (changed) {
      changed = false
      allFolders.forEach(folder => {
        if (folder.parent_id && excluded.has(folder.parent_id) && !excluded.has(folder.id)) {
          excluded.add(folder.id)
          changed = true
        }
      })
    }
    return [...excluded]
  }

  function canMoveItemsTo(moveItems, destinationId) {
    if (!destinationId) return true
    return !excludedFolderIds(moveItems).includes(destinationId)
  }

  async function updateItemLocations(moveItems, destination) {
    for (const item of moveItems) {
      if (item.kind === 'file' && item.folder_id === destination) continue
      if (item.kind === 'folder' && item.parent_id === destination) continue
      await api(item.kind === 'folder' ? `/api/file-folders/${item.id}` : `/api/files/${item.id}`, {
        method: 'PATCH',
        body: JSON.stringify(item.kind === 'folder' ? { parent_id: destination } : { folder_id: destination }),
      })
    }
  }

  async function submitDialog(value) {
    setBusy(true); setError('')
    try {
      if (dialog.type === 'new-folder') {
        const result = await post('/api/file-folders', { name: value, parent_id: view === 'folder' ? folderId : null })
        await updateItemLocations(dialog.items || [], result.folder.id)
      } else if (dialog.type === 'rename') {
        const item = dialog.item
        await api(item.kind === 'folder' ? `/api/file-folders/${item.id}` : `/api/files/${item.id}`, { method: 'PATCH', body: JSON.stringify({ name: value }) })
      } else if (dialog.type === 'move') {
        const destination = value === 'root' ? null : value
        await updateItemLocations(dialog.items, destination)
      } else if (dialog.type === 'confirm') {
        const folders = dialog.items.filter(item => item.kind === 'folder')
        const files = dialog.items.filter(item => item.kind === 'file')
        for (const item of files) {
          await api(`/api/files/${item.id}`, { method: 'PATCH', body: JSON.stringify({ trashed: !dialog.restore }) })
        }
        for (const item of folders) {
          await api(`/api/file-folders/${item.id}`, { method: 'DELETE' })
        }
      }
      setDialog(null); reload()
    } catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }

  async function createDestinationFolder(name, parentId) {
    setBusy(true); setError('')
    try {
      const result = await post('/api/file-folders', { name, parent_id: parentId })
      setAllFolders(current => [...current, result.folder].sort((a, b) => a.name.localeCompare(b.name)))
      return result.folder
    } catch (err) {
      setError(err.message)
      throw err
    } finally { setBusy(false) }
  }

  function beginItemDrag(event, item) {
    if (view === 'trash') return
    const draggedItems = selected.has(itemKey(item))
      ? items.filter(candidate => selected.has(itemKey(candidate)))
      : [item]
    const payloadItems = draggedItems.map(candidate => ({ kind: candidate.kind, id: candidate.id }))
    const payload = { items: payloadItems, count: draggedItems.length }
    dragItemsRef.current = draggedItems
    setDraggingItemKeys(draggedItems.map(itemKey))
    if (!selected.has(itemKey(item))) setSelected(new Set([itemKey(item)]))
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData(itemDragType, JSON.stringify(payload))
    event.dataTransfer.setData('text/plain', draggedItems.map(candidate => candidate.name).join(', '))

    const preview = window.document.createElement('div')
    preview.className = 'explorer-drag-preview'
    const count = window.document.createElement('strong')
    count.textContent = draggedItems.length === 1 ? draggedItems[0].name : `${draggedItems.length} items`
    const detail = window.document.createElement('span')
    detail.textContent = draggedItems.length === 1 ? `Move ${draggedItems[0].kind}` : 'Moving selected items together'
    preview.append(count, detail)
    window.document.body.appendChild(preview)
    event.dataTransfer.setDragImage(preview, 24, 20)
    window.requestAnimationFrame(() => preview.remove())
  }

  function itemsFromDragEvent(event) {
    try {
      const rawPayload = event.dataTransfer.getData(itemDragType)
      if (rawPayload) {
        const parsed = JSON.parse(rawPayload)
        const payloadItems = Array.isArray(parsed) ? parsed : parsed.items
        if (Array.isArray(payloadItems)) {
          const itemsByKey = new Map(items.map(candidate => [itemKey(candidate), candidate]))
          const resolvedItems = payloadItems
            .map(candidate => itemsByKey.get(`${candidate.kind}:${candidate.id}`))
            .filter(Boolean)
          if (resolvedItems.length) return resolvedItems
        }
      }
    } catch {
      // Fall back to the in-memory drag batch if a browser blocks custom drag data.
    }
    return dragItemsRef.current
  }

  function dragOverFolder(event, destinationId) {
    const hasItemPayload = dragItemsRef.current.length
      || Array.from(event.dataTransfer.types || []).includes(itemDragType)
    if (!hasItemPayload || busy || !canMoveItemsTo(dragItemsRef.current, destinationId)) return
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
    setDragTargetId(destinationId)
  }

  function leaveFolder(event, destinationId) {
    if (event.currentTarget.contains(event.relatedTarget)) return
    setDragTargetId(current => current === destinationId ? null : current)
  }

  async function dropItemsIntoFolder(event, destinationId) {
    event.preventDefault()
    if (busy) return
    const moveItems = itemsFromDragEvent(event)
    if (!moveItems.length || !canMoveItemsTo(moveItems, destinationId)) return
    dragItemsRef.current = []
    setDragTargetId(null)
    setDraggingItemKeys([])
    setBusy(true); setError('')
    try {
      await updateItemLocations(moveItems, destinationId)
      setSelected(new Set())
      reload()
    } catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }

  function finishItemDrag() {
    dragItemsRef.current = []
    setDragTargetId(null)
    setDraggingItemKeys([])
  }

  function hasExternalFiles(event) {
    const types = Array.from(event.dataTransfer?.types || [])
    return types.includes('Files') && !types.includes(itemDragType)
  }

  function enterExternalFiles(event) {
    if (!hasExternalFiles(event)) return
    event.preventDefault()
    externalDragDepthRef.current += 1
    const count = Array.from(event.dataTransfer?.items || []).filter(item => item.kind === 'file').length
    setExternalDragCount(count)
    setExternalDragActive(true)
  }

  function overExternalFiles(event) {
    if (!hasExternalFiles(event)) return
    event.preventDefault()
    event.dataTransfer.dropEffect = busy ? 'none' : 'copy'
  }

  function leaveExternalFiles(event) {
    externalDragDepthRef.current = Math.max(0, externalDragDepthRef.current - 1)
    if (externalDragDepthRef.current === 0) {
      setExternalDragActive(false)
      setExternalDragCount(0)
    }
  }

  function dropExternalFiles(event) {
    if (!hasExternalFiles(event)) return
    event.preventDefault()
    event.stopPropagation()
    externalDragDepthRef.current = 0
    setExternalDragActive(false)
    setExternalDragCount(0)
    if (busy) return
    const destinationId = view === 'folder' && folderId ? folderId : null
    uploadFiles(Array.from(event.dataTransfer.files || []), destinationId)
  }

  async function patchFiles(payload) {
    const files = selectedItems.filter(item => item.kind === 'file')
    if (!files.length) return
    setBusy(true); setError('')
    try {
      for (const item of files) {
        await api(`/api/files/${item.id}`, { method: 'PATCH', body: JSON.stringify(payload) })
      }
      reload()
    }
    catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }

  async function toggleStar(item) {
    setBusy(true); setError('')
    try {
      await api(`/api/files/${item.id}`, { method: 'PATCH', body: JSON.stringify({ starred: !item.starred }) })
      reload()
    } catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }

  function removeSelected() { setDialog({ type: 'confirm', items: selectedItems, restore: view === 'trash' }) }

  async function uploadFiles(files, destinationId = view === 'folder' && folderId ? folderId : null) {
    if (!files?.length) return
    setBusy(true); setError('')
    try {
      for (const file of files) {
        const body = new FormData(); body.append('file', file)
        const uploaded = await api('/api/documents/upload', { method: 'POST', body })
        if (destinationId) await api(`/api/files/${uploaded.document_id}`, { method: 'PATCH', body: JSON.stringify({ folder_id: destinationId }) })
      }
      onDocumentsChanged?.(); reload()
    } catch (err) { setError(err.message) }
    finally { setBusy(false); if (uploadRef.current) uploadRef.current.value = '' }
  }

  const heading = query.trim() ? `Search results for “${query.trim()}”` : view === 'starred' ? 'Starred' : view === 'trash' ? 'Trash' : data.breadcrumbs.at(-1)?.name || 'All records'
  const sortOptions = [
    { value: 'name', label: 'Name' }, { value: 'modified', label: 'Modified' }, { value: 'size', label: 'File size' }, { value: 'type', label: 'File type' },
  ]
  const pageSizeOptions = [
    { value: '10', label: '10 per page' }, { value: '20', label: '20 per page' }, { value: '50', label: '50 per page' },
  ]
  const uploadDestinationName = view === 'folder' && folderId
    ? data.breadcrumbs.at(-1)?.name || 'this folder'
    : 'All records'

  return <div className="screen explorer-screen" onDragEnter={enterExternalFiles} onDragOver={overExternalFiles} onDragLeave={leaveExternalFiles} onDrop={dropExternalFiles}>
    <div className="explorer-heading"><div><p className="eyebrow">Document library</p><h1>Records</h1><p>Every record you're cleared to see, with its classification and how its text was extracted.</p></div><button className="primary-button" onClick={openNewFolderDialog} title="New folder (Command/Ctrl+N)"><Plus size={16} /> New folder</button></div>
    {error && <div className="error-notice"><div><strong>File operation needs attention</strong><span>{error}</span></div><button onClick={() => setError('')}><X size={16} /></button></div>}
    <div className={`explorer-shell ${externalDragActive ? 'external-drag-active' : ''}`}>
      {externalDragActive && <div className="external-file-drop" role="status" aria-live="polite"><div><Upload size={27} /><strong>Drop {externalDragCount || ''} {externalDragCount === 1 ? 'file' : 'files'} to upload</strong><span>Upload to <b>{uploadDestinationName}</b></span><small>PDF, DOCX, TXT, and MD files are supported</small></div></div>}
      <aside className="explorer-sidebar">
        <nav>
          <button className={view === 'root' && !query ? 'active' : ''} onClick={() => navigate('root')}><HardDrive size={16} /><span>All records</span><small>{data.counts.documents}</small></button>
          <button className={view === 'starred' && !query ? 'active' : ''} onClick={() => navigate('starred')}><Star size={16} /><span>Starred</span><small>{data.counts.starred}</small></button>
          <button className={view === 'trash' && !query ? 'active' : ''} onClick={() => navigate('trash')}><Trash2 size={16} /><span>Trash</span><small>{data.counts.trash}</small></button>
        </nav>
        <div className="folder-tree-heading"><span>Folders</span><button onClick={openNewFolderDialog} aria-label="Create folder" title="New folder (Command/Ctrl+N)"><Plus size={14} /></button></div>
        <div className="folder-tree">{allFolders.filter(folder => folder.parent_id === null).map(folder => <button className={`${folderId === folder.id && !query ? 'active' : ''} ${dragTargetId === folder.id ? 'drop-target' : ''}`} data-folder-id={folder.id} key={folder.id} onClick={() => navigate('folder', folder.id)} onDragEnter={event => dragOverFolder(event, folder.id)} onDragOver={event => dragOverFolder(event, folder.id)} onDragLeave={event => leaveFolder(event, folder.id)} onDrop={event => dropItemsIntoFolder(event, folder.id)}><Folder size={15} fill="currentColor" /><span>{folder.name}</span>{dragTargetId === folder.id && draggingItemKeys.length > 1 && <small className="folder-drop-count">{draggingItemKeys.length}</small>}</button>)}{!allFolders.length && <small>No folders yet</small>}</div>
      </aside>
      <section className="explorer-main">
        <div className="explorer-topline">
          <div className="explorer-breadcrumbs"><button onClick={() => navigate('root')} aria-label="All records"><Home size={15} /></button>{data.breadcrumbs.map(crumb => <span key={crumb.id}><ChevronRight size={13} /><button onClick={() => navigate('folder', crumb.id)}>{crumb.name}</button></span>)}</div>
          <label className="explorer-search"><Search size={15} /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search files and folders" />{query && <button onClick={() => setQuery('')} aria-label="Clear search"><X size={13} /></button>}</label>
        </div>
        <div className="explorer-toolbar">
          <div className="explorer-file-actions">
            <input ref={uploadRef} type="file" multiple accept=".pdf,.docx,.txt,.md" onChange={event => uploadFiles(event.target.files)} />
            <button onClick={() => uploadRef.current?.click()} disabled={busy}><Upload size={15} /> Upload</button>
            <button disabled={oneSelected?.kind !== 'file' || busy} onClick={() => downloadItem(oneSelected)}><Download size={14} /> Download</button>
            <button disabled={!oneSelected || busy} onClick={() => setDialog({ type: 'rename', kind: oneSelected?.kind, item: oneSelected, initialName: oneSelected?.name })}><Pencil size={14} /> Rename</button>
            <button disabled={!selectedItems.length || busy || view === 'trash'} onClick={() => setDialog({ type: 'move', items: selectedItems, initialFolder: view === 'folder' ? folderId : 'root', excludeIds: excludedFolderIds(selectedItems) })}><Move size={14} /> Move</button>
            <button disabled={!selectedItems.some(item => item.kind === 'file') || busy || view === 'trash'} onClick={() => patchFiles({ starred: true })}><Star size={14} /> Star</button>
            <button disabled={!selectedItems.length || busy} onClick={removeSelected}>{view === 'trash' ? <ArchiveRestore size={14} /> : <Trash2 size={14} />}{view === 'trash' ? 'Restore' : 'Trash'}</button>
          </div>
          <div className="explorer-view-actions">
            <button onClick={reload} aria-label="Refresh files"><RefreshCw size={14} className={loading ? 'spin' : ''} /></button>
            <SelectMenu value={sort} onValueChange={setSort} options={sortOptions} ariaLabel="Sort files" className="explorer-sort" />
            <button onClick={() => setAscending(value => !value)} aria-label={ascending ? 'Sort descending' : 'Sort ascending'}>{ascending ? <ArrowDownAZ size={15} /> : <ArrowUpAZ size={15} />}</button>
            <div className="view-toggle"><button className={display === 'list' ? 'active' : ''} onClick={() => setDisplay('list')} aria-label="List view"><LayoutList size={15} /></button><button className={display === 'grid' ? 'active' : ''} onClick={() => setDisplay('grid')} aria-label="Grid view"><Grid2X2 size={14} /></button></div>
          </div>
        </div>
        <div className="explorer-list-area">
          <div className="explorer-content-heading"><div><h2>{heading}</h2><span>{items.length} {items.length === 1 ? 'item' : 'items'}</span>{data.counts.hidden_by_policy > 0 && view !== 'trash' && <em className="policy-hidden-note">{data.counts.hidden_by_policy} more {data.counts.hidden_by_policy === 1 ? 'record is' : 'records are'} withheld by your role's clearance</em>}</div>{draggingItemKeys.length > 0 ? <strong className="explorer-drag-status"><Move size={12} /> {draggingItemKeys.length} {draggingItemKeys.length === 1 ? 'item' : 'items'} moving</strong> : selectedItems.length > 0 && <strong>{selectedItems.length} selected</strong>}</div>
          {loading ? <div className="explorer-loading"><LoaderCircle className="spin" /> Loading files…</div> : !items.length ? <div className="explorer-empty"><FolderOpen size={34} /><h3>{query ? 'No matches found' : view === 'trash' ? 'Trash is empty' : 'This folder is empty'}</h3><p>{query ? 'Try a different filename or record title.' : view === 'trash' ? 'Files moved to Trash will appear here.' : 'Upload a record or create a folder to get started.'}</p></div> : display === 'list' ? <div className="explorer-table" role="table">
          <div className="explorer-table-head" role="row"><label><input type="checkbox" checked={pageItems.length > 0 && pageItems.every(item => selected.has(itemKey(item)))} onChange={event => toggleAll(event.target.checked)} aria-label="Select this page" /><span>Name</span></label><span>Classification</span><span>Text extraction</span><span>Pages</span><span>Added</span><span></span></div>
          {pageItems.map(item => <div className={`explorer-row ${selected.has(itemKey(item)) ? 'selected' : ''} ${draggingItemKeys.includes(itemKey(item)) ? 'dragging-item' : ''} ${item.kind === 'folder' && dragTargetId === item.id ? 'drop-target' : ''}`} data-file-id={item.kind === 'file' ? item.id : undefined} data-folder-id={item.kind === 'folder' ? item.id : undefined} role="row" key={itemKey(item)} draggable={view !== 'trash'} onClick={event => selectFromItemSurface(event, item)} onDragStart={event => beginItemDrag(event, item)} onDragEnd={finishItemDrag} onDragEnter={event => item.kind === 'folder' && dragOverFolder(event, item.id)} onDragOver={event => item.kind === 'folder' && dragOverFolder(event, item.id)} onDragLeave={event => item.kind === 'folder' && leaveFolder(event, item.id)} onDrop={event => item.kind === 'folder' && dropItemsIntoFolder(event, item.id)} onDoubleClick={() => openItem(item)}>
            <div className="explorer-name-cell"><input type="checkbox" checked={selected.has(itemKey(item))} onChange={event => toggle(item, event.target.checked, event.shiftKey || event.nativeEvent.shiftKey)} aria-label={`Select ${item.name}`} /><FileGlyph item={item} /><button onClick={() => openItem(item)}><strong>{item.name}</strong><small>{item.kind === 'folder' ? `${item.item_count} items` : [item.doc_type?.replaceAll('_', ' '), item.source_unit].filter(Boolean).join(' · ')}</small></button></div>
            <span>{item.kind === 'folder' ? '—' : <ClassificationBadge value={item.classification} />}</span><span>{item.kind === 'folder' ? '—' : <OcrBadge status={item.ocr_status} />}</span><span>{item.kind === 'folder' ? '—' : item.page_count}</span><span>{formatDate(item.kind === 'folder' ? item.modified_at : item.upload_date)}</span>
            <div className="explorer-row-actions">{item.kind === 'file' && <><button disabled={busy} onClick={() => toggleStar(item)} aria-label={item.starred ? 'Unstar file' : 'Star file'}><Star size={14} fill={item.starred ? 'currentColor' : 'none'} /></button><a href={`/api/documents/${item.id}/file`} download={item.filename} aria-label={`Download ${item.name}`} title="Download"><Download size={14} /></a></>}<button aria-label="More file actions" onClick={() => { setSelected(new Set([itemKey(item)])); setDialog({ type: 'rename', kind: item.kind, item, initialName: item.name }) }}><MoreHorizontal size={15} /></button></div>
          </div>)}
        </div> : <div className="explorer-grid">{pageItems.map(item => <article className={`${selected.has(itemKey(item)) ? 'selected' : ''} ${draggingItemKeys.includes(itemKey(item)) ? 'dragging-item' : ''} ${item.kind === 'folder' && dragTargetId === item.id ? 'drop-target' : ''}`} data-file-id={item.kind === 'file' ? item.id : undefined} data-folder-id={item.kind === 'folder' ? item.id : undefined} key={itemKey(item)} draggable={view !== 'trash'} onClick={event => selectFromItemSurface(event, item)} onDragStart={event => beginItemDrag(event, item)} onDragEnd={finishItemDrag} onDragEnter={event => item.kind === 'folder' && dragOverFolder(event, item.id)} onDragOver={event => item.kind === 'folder' && dragOverFolder(event, item.id)} onDragLeave={event => item.kind === 'folder' && leaveFolder(event, item.id)} onDrop={event => item.kind === 'folder' && dropItemsIntoFolder(event, item.id)} onDoubleClick={() => openItem(item)}><label><input type="checkbox" checked={selected.has(itemKey(item))} onChange={event => toggle(item, event.target.checked, event.shiftKey || event.nativeEvent.shiftKey)} aria-label={`Select ${item.name}`} /></label><FileGlyph item={item}/>{item.kind === 'file' && <><button className="grid-download" onClick={() => downloadItem(item)} aria-label={`Download ${item.name}`} title="Download"><Download size={14} /></button><button className="grid-star" disabled={busy} onClick={() => toggleStar(item)} aria-label={item.starred ? 'Unstar file' : 'Star file'}><Star size={14} fill={item.starred ? 'currentColor' : 'none'} /></button></>}<button className="grid-open" onClick={() => openItem(item)}><strong>{item.name}</strong><small>{item.kind === 'folder' ? `${item.item_count} items` : `${item.extension.toUpperCase()} · ${formatSize(item.size_bytes)}`}</small></button></article>)}</div>}
          {oneSelected?.kind === 'file' && <aside className="explorer-details"><div><FileGlyph item={oneSelected} /><span><strong>{oneSelected.name}</strong><small>{oneSelected.filename}</small></span></div><dl><div><dt>Classification</dt><dd><ClassificationBadge value={oneSelected.classification} /></dd></div><div><dt>Text</dt><dd><OcrBadge status={oneSelected.ocr_status} /></dd></div><div><dt>Passages</dt><dd>{oneSelected.chunk_count} indexed</dd></div><div><dt>Type</dt><dd>{oneSelected.doc_type.replaceAll('_', ' ')} ({oneSelected.extension.toUpperCase()})</dd></div><div><dt>Size</dt><dd>{formatSize(oneSelected.size_bytes)}</dd></div><div><dt>Pages</dt><dd>{oneSelected.page_count}</dd></div><div><dt>Added</dt><dd>{formatDate(oneSelected.upload_date)}</dd></div></dl><div><button onClick={() => openItem(oneSelected)}><File size={14} /> Open</button><a href={`/api/documents/${oneSelected.id}/file`} download={oneSelected.filename}><Download size={14} /> Download</a></div></aside>}
        </div>
        {!loading && items.length > 0 && <footer className="explorer-pagination" aria-label="File pagination">
          <span>Showing {pageStart}–{pageEnd} of {items.length}</span>
          <div>
            <SelectMenu value={pageSize} onValueChange={setPageSize} options={pageSizeOptions} ariaLabel="Files per page" className="pagination-size-select" />
            <button onClick={() => setPage(current => current - 1)} disabled={page === 1} aria-label="Previous page"><ChevronLeft size={15} /></button>
            {pageNumbers.map(pageNumber => <button className={pageNumber === page ? 'active' : ''} onClick={() => setPage(pageNumber)} aria-current={pageNumber === page ? 'page' : undefined} aria-label={`Page ${pageNumber}`} key={pageNumber}>{pageNumber}</button>)}
            <button onClick={() => setPage(current => current + 1)} disabled={page === totalPages} aria-label="Next page"><ChevronRight size={15} /></button>
          </div>
        </footer>}
      </section>
    </div>
    <ExplorerDialog dialog={dialog} folders={allFolders} onClose={() => setDialog(null)} onSubmit={submitDialog} onCreateFolder={createDestinationFolder} busy={busy} />
  </div>
}
