import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useStore } from '../store/useStore'
import type { AuditEvent } from '../data/mockData'
import { ScrollText, ChevronDown, ChevronRight, Filter } from 'lucide-react'

const eventTypeColors: Record<string, { dot: string; badge: string }> = {
  'proposal.create': { dot: 'bg-accent-amber', badge: 'bg-accent-amber/15 text-accent-amber' },
  'proposal.decide': { dot: 'bg-accent-purple', badge: 'bg-accent-purple/15 text-accent-purple' },
  'proposal.execute': { dot: 'bg-accent-green', badge: 'bg-accent-green/15 text-accent-green' },
  'copilot.turn': { dot: 'bg-accent-cyan', badge: 'bg-accent-cyan/15 text-accent-cyan' },
  'auth.role_switch': { dot: 'bg-text-dim', badge: 'bg-white/5 text-text-dim' },
}

export default function AuditPage() {
  const { vendor, auditEvents } = useStore()
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const vendorEvents = auditEvents.filter(e => e.vendorId === vendor.id)
  const filtered = typeFilter === 'all'
    ? vendorEvents
    : vendorEvents.filter(e => e.eventType === typeFilter)

  const eventTypes = ['all', ...new Set(vendorEvents.map(e => e.eventType))]

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-text flex items-center gap-2">
          <ScrollText className="w-6 h-6 text-accent-purple" />
          Audit Log
        </h1>
        <p className="text-sm text-text-muted mt-1">
          Immutable record of every tool call, proposal, and decision for {vendor.name}.
        </p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2">
        <Filter className="w-3.5 h-3.5 text-text-dim" />
        <div className="flex gap-1 flex-wrap">
          {eventTypes.map(type => (
            <button
              key={type}
              onClick={() => setTypeFilter(type)}
              className={`
                px-2.5 py-1 rounded-lg text-[10px] font-semibold uppercase tracking-wider transition-all
                ${typeFilter === type
                  ? 'bg-accent-cyan/15 text-accent-cyan'
                  : 'text-text-dim hover:text-text-muted hover:bg-white/[0.03]'
                }
              `}
            >
              {type === 'all' ? 'All' : type.replace('.', ' · ')}
            </button>
          ))}
        </div>
      </div>

      {/* Count */}
      <p className="text-xs text-text-dim font-mono">{filtered.length} event{filtered.length !== 1 ? 's' : ''}</p>

      {/* Event List */}
      <div className="space-y-1">
        <AnimatePresence>
          {filtered.map((event, i) => (
            <AuditEventRow
              key={event.id}
              event={event}
              index={i}
              expanded={expandedId === event.id}
              onToggle={() => setExpandedId(expandedId === event.id ? null : event.id)}
            />
          ))}
        </AnimatePresence>
      </div>

      {filtered.length === 0 && (
        <div className="text-center py-16">
          <ScrollText className="w-8 h-8 text-text-dim mx-auto mb-3" />
          <p className="text-sm text-text-muted">No audit events found.</p>
        </div>
      )}
    </div>
  )
}

function AuditEventRow({ event, index, expanded, onToggle }: {
  event: AuditEvent
  index: number
  expanded: boolean
  onToggle: () => void
}) {
  const colors = eventTypeColors[event.eventType] || { dot: 'bg-text-dim', badge: 'bg-white/5 text-text-dim' }

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.03 }}
      className="glass glass-hover overflow-hidden"
    >
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-4 px-5 py-3.5 text-left transition-all"
      >
        {/* Timeline dot */}
        <div className={`w-2.5 h-2.5 rounded-full ${colors.dot} flex-shrink-0`} />

        {/* Event type badge */}
        <span className={`text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md flex-shrink-0 ${colors.badge}`}>
          {event.eventType.replace('.', ' · ')}
        </span>

        {/* Entity */}
        <div className="flex-1 min-w-0">
          <span className="text-xs text-text-muted">
            {event.entityType && (
              <span className="font-mono text-text-dim">{event.entityId}</span>
            )}
            {event.actorId && (
              <span className="ml-2 text-text-dim">
                by <span className="font-mono text-text-muted">{event.actorId}</span>
              </span>
            )}
          </span>
        </div>

        {/* Timestamp */}
        <span className="text-[10px] font-mono text-text-dim flex-shrink-0">
          {formatTimestamp(event.createdAt)}
        </span>

        {/* Expand chevron */}
        {expanded
          ? <ChevronDown className="w-3.5 h-3.5 text-text-dim flex-shrink-0" />
          : <ChevronRight className="w-3.5 h-3.5 text-text-dim flex-shrink-0" />
        }
      </button>

      {/* Expanded metadata */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="border-t border-line overflow-hidden"
          >
            <div className="px-5 py-3">
              <p className="text-[9px] font-mono uppercase tracking-wider text-text-dim mb-2">Metadata</p>
              <pre className="text-[11px] font-mono text-text-muted bg-black/20 rounded-lg p-3 overflow-x-auto">
                {JSON.stringify(event.metadata, null, 2)}
              </pre>
              <div className="flex gap-4 mt-2 text-[10px] text-text-dim font-mono">
                <span>ID: {event.id}</span>
                <span>Vendor: {event.vendorId}</span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffMins = Math.floor(diffMs / 60_000)
    if (diffMins < 1) return 'just now'
    if (diffMins < 60) return `${diffMins}m ago`
    const diffHrs = Math.floor(diffMins / 60)
    if (diffHrs < 24) return `${diffHrs}h ago`
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch {
    return iso
  }
}
