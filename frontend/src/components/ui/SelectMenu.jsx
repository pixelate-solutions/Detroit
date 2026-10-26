import { useEffect, useRef, useState } from 'react'
import { Check, ChevronDown } from 'lucide-react'

export default function SelectMenu({ value, onValueChange, options, ariaLabel, className = '' }) {
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(Math.max(0, options.findIndex(option => option.value === value)))
  const rootRef = useRef(null)
  const selected = options.find(option => option.value === value) || options[0]

  useEffect(() => {
    function close(event) { if (!rootRef.current?.contains(event.target)) setOpen(false) }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [])
  useEffect(() => { setActiveIndex(Math.max(0, options.findIndex(option => option.value === value))) }, [value, options.length])

  function choose(option) { onValueChange(option.value); setOpen(false) }
  function onKeyDown(event) {
    if (event.key === 'Escape') { setOpen(false); return }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      if (open) choose(options[activeIndex]); else setOpen(true)
      return
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault(); setOpen(true)
      const direction = event.key === 'ArrowDown' ? 1 : -1
      setActiveIndex(index => (index + direction + options.length) % options.length)
    }
  }

  return <div className={`ui-select ${className}`} ref={rootRef}>
    <button type="button" className="ui-select-trigger" aria-label={ariaLabel} aria-haspopup="listbox" aria-expanded={open} onClick={() => setOpen(current => !current)} onKeyDown={onKeyDown}>
      <span>{selected?.label}</span><ChevronDown size={15} className={open ? 'open' : ''} />
    </button>
    {open && <div className="ui-select-content" role="listbox" aria-label={ariaLabel}>
      {options.map((option, index) => <button type="button" role="option" aria-selected={option.value === value} className={index === activeIndex ? 'active' : ''} key={option.value} onPointerMove={() => setActiveIndex(index)} onClick={() => choose(option)}>
        <Check size={14} className={option.value === value ? '' : 'invisible'} /><span>{option.label}</span>
      </button>)}
    </div>}
  </div>
}
