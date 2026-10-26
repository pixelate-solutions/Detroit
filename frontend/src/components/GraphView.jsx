// Rendering and interaction patterns adapted from Memory Knowledge Graph 3D
// by Seth Rose (MIT). See THIRD_PARTY_LICENSES.md in this repository.
import { useEffect, useMemo, useRef, useState } from 'react'
import ForceGraph3D from '3d-force-graph'
import SpriteText from 'three-spritetext'
import { ChevronRight, Focus, LoaderCircle, Rotate3D, Search, X } from 'lucide-react'
import { api } from '../api'
import SelectMenu from './ui/SelectMenu'

const colors = {
  person: '#f2b84b', organization: '#ea715f', parcel: '#50a8c5', case_number: '#9e83d6',
  address: '#4fb896', ordinance: '#dd8a45', contract: '#768ce0', other: '#8e9ca4',
}

export default function GraphView({ onOpenDocument }) {
  const mountRef = useRef(null)
  const graphRef = useRef(null)
  const [raw, setRaw] = useState(null)
  const [selected, setSelected] = useState(null)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState('all')
  const [error, setError] = useState('')

  useEffect(() => { api('/api/graph').then(setRaw).catch(err => setError(err.message)) }, [])
  const types = useMemo(() => raw ? [...new Set(raw.entities.map(item => item.entityType))].sort() : [], [raw])
  const typeOptions = useMemo(() => [
    { value: 'all', label: 'All entity types' },
    ...types.map(type => ({ value: type, label: type.replaceAll('_', ' ') })),
  ], [types])
  const graphData = useMemo(() => {
    if (!raw) return { nodes: [], links: [] }
    const q = query.trim().toLowerCase()
    const directlyMatched = new Set(raw.entities.filter(entity => (!q || entity.name.toLowerCase().includes(q)) && (filter === 'all' || entity.entityType === filter)).map(entity => entity.name))
    const included = new Set(directlyMatched)
    if (q) raw.relations.forEach(link => { if (directlyMatched.has(link.from)) included.add(link.to); if (directlyMatched.has(link.to)) included.add(link.from) })
    const nodes = raw.entities.filter(entity => included.has(entity.name)).map(entity => ({
      ...entity, id: entity.name, color: colors[entity.entityType] || colors.other,
      val: 5 + Math.min(8, (entity.observations?.length || 0) + (entity.sourceDocuments?.length || 0)),
      directMatch: directlyMatched.has(entity.name),
    }))
    const names = new Set(nodes.map(node => node.id))
    const links = raw.relations.filter(link => names.has(link.from) && names.has(link.to)).map((link, index) => ({ ...link, id: index, source: link.from, target: link.to }))
    return { nodes, links }
  }, [raw, query, filter])

  useEffect(() => {
    if (!mountRef.current || !raw) return
    if (!graphRef.current) {
      const graph = ForceGraph3D({ controlType: 'orbit' })(mountRef.current)
        .backgroundColor('#071b24')
        .showNavInfo(false)
        .enableNodeDrag(false)
        .nodeLabel(node => `${node.name} · ${node.entityType}`)
        .nodeColor(node => node.color)
        .nodeVal(node => node.val)
        .nodeOpacity(.88)
        .linkColor(() => 'rgba(130, 183, 196, .42)')
        .linkWidth(1.1)
        .linkDirectionalParticles(1)
        .linkDirectionalParticleWidth(1.4)
        .linkDirectionalParticleSpeed(.003)
        .linkLabel(link => link.relationType.replaceAll('_', ' '))
        .nodeThreeObjectExtend(true)
        .nodeThreeObject(node => {
          const sprite = new SpriteText(node.name)
          sprite.color = node.directMatch ? '#ffffff' : '#b7c8ce'
          sprite.textHeight = node.directMatch ? 4.8 : 3.2
          sprite.backgroundColor = 'rgba(7,27,36,.78)'
          sprite.padding = 1.8
          sprite.borderRadius = 2
          sprite.position.y = -8
          return sprite
        })
        .onNodeClick(node => {
          if (!node) return
          setSelected(node)
          const distance = 90
          const focus = { x: node.x ?? 0, y: node.y ?? 0, z: node.z ?? 0 }
          const magnitude = Math.hypot(focus.x, focus.y, focus.z) || 1
          const ratio = 1 + distance / magnitude
          graph.cameraPosition(
            { x: focus.x * ratio, y: focus.y * ratio, z: focus.z * ratio },
            focus,
            900,
          )
        })
      graph.d3Force('charge').strength(-115)
      graphRef.current = graph
    }
    graphRef.current.graphData(graphData)
    window.setTimeout(() => graphRef.current?.zoomToFit(650, 95), 80)
    const resize = () => graphRef.current?.width(mountRef.current.clientWidth).height(mountRef.current.clientHeight)
    resize(); window.addEventListener('resize', resize)
    return () => window.removeEventListener('resize', resize)
  }, [raw, graphData])

  useEffect(() => () => { if (graphRef.current) { graphRef.current._destructor?.(); graphRef.current = null } }, [])

  return <div className="screen graph-screen">
    <div className="graph-heading"><div><p className="eyebrow">Cross-document discovery</p><h1>See the connections no single record reveals.</h1></div><div className="graph-counts"><span><strong>{raw?.entities.length || 0}</strong>entities</span><span><strong>{raw?.relations.length || 0}</strong>relationships</span></div></div>
    <div className="graph-shell">
      <div className="graph-controls"><label><Search size={16} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Find an entity…" />{query && <button onClick={() => setQuery('')}><X size={14} /></button>}</label><SelectMenu value={filter} onValueChange={setFilter} options={typeOptions} ariaLabel="Filter entity type" className="graph-type-select" /><button className="reset-camera" onClick={() => graphRef.current?.zoomToFit(700, 70)}><Focus size={15} /> Fit graph</button></div>
      <div ref={mountRef} className="graph-canvas">{!raw && !error && <div className="graph-loading"><LoaderCircle className="spin" /> Assembling local graph…</div>}{error && <div className="graph-loading">{error}</div>}</div>
      <div className="graph-hint"><Rotate3D size={16} /> Drag to orbit · scroll to zoom · select a node</div>
      <div className="graph-legend">{Object.entries(colors).slice(0, 7).map(([type, color]) => <span key={type}><i style={{ background: color }}></i>{type.replaceAll('_', ' ')}</span>)}</div>
      {selected && <aside className="node-panel"><button className="node-close" onClick={() => setSelected(null)}><X size={17} /></button><div className="node-type"><i style={{ background: selected.color }}></i>{selected.entityType.replaceAll('_', ' ')}</div><h2>{selected.name}</h2><section><span>Observations</span>{selected.observations?.map((item, index) => <p key={index}>{item}</p>)}</section><section><span>Found in {selected.sourceDocuments?.length || 0} records</span>{selected.sourceDocuments?.map(doc => <button key={doc.id} onClick={() => onOpenDocument(doc.id, 1, selected.name)}><div><small>{doc.doc_type.replaceAll('_', ' ')}</small><strong>{doc.title}</strong></div><ChevronRight size={15} /></button>)}</section></aside>}
    </div>
  </div>
}
