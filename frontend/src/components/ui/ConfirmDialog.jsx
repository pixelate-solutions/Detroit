import { useEffect, useId, useRef } from 'react'
import { AlertTriangle, LoaderCircle, X } from 'lucide-react'

export default function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Continue',
  cancelLabel = 'Cancel',
  destructive = false,
  busy = false,
  onConfirm,
  onCancel,
}) {
  const titleId = useId()
  const descriptionId = useId()
  const cancelRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const previousFocus = document.activeElement
    const timer = window.setTimeout(() => cancelRef.current?.focus(), 0)
    function onKeyDown(event) {
      if (event.key === 'Escape' && !busy) onCancel()
      if (event.key === 'Tab') {
        const dialog = cancelRef.current?.closest('[role="alertdialog"]')
        const controls = [...(dialog?.querySelectorAll('button:not(:disabled)') || [])]
        if (!controls.length) return
        const first = controls[0]
        const last = controls[controls.length - 1]
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault(); last.focus()
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault(); first.focus()
        }
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => {
      window.clearTimeout(timer)
      window.removeEventListener('keydown', onKeyDown)
      previousFocus?.focus?.()
    }
  }, [open, busy, onCancel])

  if (!open) return null

  return <div className="dialog-backdrop confirm-dialog-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget && !busy) onCancel() }}>
    <section className={`confirm-dialog ${destructive ? 'destructive' : ''}`} role="alertdialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={descriptionId}>
      <button className="dialog-close" onClick={onCancel} disabled={busy} aria-label="Close confirmation"><X size={17} /></button>
      <div className="confirm-dialog-icon"><AlertTriangle size={20} /></div>
      <div className="confirm-dialog-copy">
        <h2 id={titleId}>{title}</h2>
        <p id={descriptionId}>{description}</p>
      </div>
      <div className="confirm-dialog-actions">
        <button ref={cancelRef} type="button" onClick={onCancel} disabled={busy}>{cancelLabel}</button>
        <button type="button" className={destructive ? 'destructive-button' : 'primary-button'} onClick={onConfirm} disabled={busy}>
          {busy && <LoaderCircle className="spin" size={15} />}{busy ? 'Working…' : confirmLabel}
        </button>
      </div>
    </section>
  </div>
}
