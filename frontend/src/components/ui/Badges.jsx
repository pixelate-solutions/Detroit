import { Lock, ScanText, FileCheck2, ShieldCheck, Eye } from 'lucide-react'

export function BrandMark({ className = '', size = 40 }) {
  return <svg className={className} width={size} height={size} viewBox="0 0 48 48" aria-hidden="true" focusable="false">
    <rect width="48" height="48" rx="11" fill="#0d2233" />
    <path d="M24 8.5 37 13v10.2c0 8.3-5.5 14.6-13 16.8-7.5-2.2-13-8.5-13-16.8V13l13-4.5Z" fill="none" stroke="#e8eef3" strokeWidth="2.2" strokeLinejoin="round" />
    <path d="M18.5 19.5h11M18.5 24h11M18.5 28.5h7" stroke="#e8eef3" strokeWidth="2.2" strokeLinecap="round" />
    <circle cx="31.5" cy="30.5" r="3.2" fill="#d6453d" />
  </svg>
}

const classificationMeta = {
  public: { label: 'Public', icon: Eye },
  internal: { label: 'Internal', icon: ShieldCheck },
  restricted: { label: 'Restricted', icon: Lock },
  confidential: { label: 'Confidential', icon: Lock },
}

export function ClassificationBadge({ value, compact = false }) {
  const meta = classificationMeta[value] || { label: value || 'Unclassified', icon: ShieldCheck }
  const Icon = meta.icon
  return <span className={`class-badge class-${value}`} title={`Classification: ${meta.label}`}>
    <Icon size={compact ? 10 : 11} aria-hidden="true" />{meta.label}
  </span>
}

export function OcrBadge({ status }) {
  const ocr = status === 'ocr'
  const Icon = ocr ? ScanText : FileCheck2
  return <span className={`ocr-badge ${ocr ? 'is-ocr' : ''}`} title={ocr ? 'Scanned image: text recovered with local Tesseract OCR' : 'Native PDF text layer extracted'}>
    <Icon size={12} aria-hidden="true" />{ocr ? 'OCR applied' : 'Text layer'}
  </span>
}

export function TypeBadge({ type }) {
  return <span className={`type-badge type-${type}`}>{(type || 'other').replaceAll('_', ' ')}</span>
}

export const classificationOrder = ['public', 'internal', 'restricted', 'confidential']
