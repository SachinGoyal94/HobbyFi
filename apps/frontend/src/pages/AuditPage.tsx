import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useStore } from '../store/useStore'
import type { AuditEvent } from '../types'
import { ScrollText, ChevronDown, ChevronRight, Filter, ShieldOff, Loader2, RefreshCw } from 'lucide-react'

const eventTypeColors: Record<string, { dot: string; badge: string }> = {
  'proposal.create': { dot: 'bg-accent-amber', badge: 'bg-accent-amber/15 text-accent-amber' },
  'proposal.approve': { dot: 'bg-accent-purple', badge: 'bg-accent-purple/15 text-accent-purple' },
  'proposal.reject': { dot: 'bg-accent-red', badge: 'bg-accent-red/15 text-accent-red' },
  'proposal.executed': { dot: 'bg-accent-green', badge: 'bg-accent-green/15 text-accent-green' },
  'proposal.failed': { dot: 'bg-accent-red', badge: 'bg-accent-red/15 text-accent-red' },
  'proposal.expired': { dot: 'bg-text-dim', badge: 'bg-white/5 text-text-dim' },
  'copilot.turn': { dot: 'bg-accent-cyan', badge: 'bg-accent-cyan/15 text-accent-cyan' },
}

export default function AuditPage() {
  const {
    vendor,
    operator,
    auditEvents,
    auditLoading,
    auditForbidden,
    fetchAudit,
    backendOnline,
  } = useStore()
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  useEffect(() => {
    if (backendOnline) void fetchAudit()
  }, [backendOnline, fetchAudit, operator.id])

  const filtered =
    typeFilter === 'all'
      ? auditEvents
      : auditEvents.filter((e) => e.eventType === typeFilter)

  const eventTypes = ['all', ...new Set(auditEvents.map((e) => e.eventType))]

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text flex items-center gap-2">
            <ScrollText className="w-6 h-6 text-accent-purple" />
            Audit Log
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Live from <code className="font-mono text-[11px] text-accent-cyan">GET /v1/copilot/audit</code>
            {' '}(owner/admin only) for {vendor.name}.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void fetchAudit()}
          disabled={!backendOnline || auditLoading || auditForbidden}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg glass-sm text-xs font-medium text-text-muted hover:text-text disabled:opacity-40"
        >
          {auditLoading ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <RefreshCw className="w-3.5 h-3.5" />
          )}
          Refresh
        </button>
      </div>

      {auditForbidden && (
        <div className="glass-sm p-6 flex items-start gap-3 border-l-2 border-l-accent-amber">
          <ShieldOff className="w-5 h-5 text-accent-amber flex-shrink-0" />
          <div>
            <p className="text-sm font-semibold text-text">Audit restricted</p>
            <p className="text-xs text-text-muted mt-1">
              Role <span className="font-mono text-accent-cyan">{operator.role}</span> cannot
              read the audit log. Switch to <strong className="text-text">admin</strong> in
              Settings (backend enforces owner/admin).
            </p>
          </div>
        </div>
      )}

      {!auditForbidden && (
        <>
          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-text-dim" />
            <div className="flex gap-1 flex-wrap">
              {eventTypes.map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => setTypeFilter(type)}
                  className={`
                    px-2.5 py-1 rounded-lg text-[10px] font-semibold uppercase tracking-wider transition-all
                    ${
                      typeFilter === type
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

          <p className="text-xs text-text-dim font-mono">
            {filtered.length} event{filtered.length !== 1 ? 's' : ''}
          </p>

          <div className="space-y-1">
            <AnimatePresence>
              {filtered.map((event, i) => (
                <AuditEventRow
                  key={event.id}
                  event={event}
                  index={i}
                  expanded={expandedId === event.id}
                  onToggle={() =>
                    setExpandedId(expandedId === event.id ? null : event.id)
                  }
                />
              ))}
            </AnimatePresence>
          </div>

          {!auditLoading && filtered.length === 0 && (
            <div className="text-center py-16">
              <ScrollText className="w-8 h-8 text-text-dim mx-auto mb-3" />
              <p className="text-sm text-text-muted">No audit events from the API yet.</p>
              <p className="text-xs text-text-dim mt-1">Send a copilot message or decide a proposal.</p>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function AuditEventRow({
  event,
  index,
  expanded,
  onToggle,
}: {
  event: AuditEvent
  index: number
  expanded: boolean
  onToggle: () => void
}) {
  const colors =
    eventTypeColors[event.eventType] || {
      dot: 'bg-text-dim',
      badge: 'bg-white/5 text-text-dim',
    }

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: Math.min(index * 0.02, 0.3) }}
      className="glass glass-hover overflow-hidden"
    >
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center gap-4 px-5 py-3.5 text-left transition-all"
      >
        <div className={`w-2.5 h-2.5 rounded-full ${colors.dot} flex-shrink-0`} />
        <span
          className={`text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md flex-shrink-0 ${colors.badge}`}
        >
          {event.eventType.replace('.', ' · ')}
        </span>
        <div className="flex-1 min-w-0">
          <span className="text-xs text-text-muted">
            {event.entityId && (
              <span className="font-mono text-text-dim">{event.entityId}</span>
            )}
            {event.actorId && (
              <span className="ml-2 text-text-dim">
                by <span className="font-mono text-text-muted">{event.actorId}</span>
              </span>
            )}
          </span>
        </div>
        <span className="text-[10px] font-mono text-text-dim flex-shrink-0">
          {formatTimestamp(event.createdAt)}
        </span>
        {expanded ? (
          <ChevronDown className="w-3.5 h-3.5 text-text-dim flex-shrink-0" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5 text-text-dim flex-shrink-0" />
        )}
      </button>

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
              <p className="text-[9px] font-mono uppercase tracking-wider text-text-dim mb-2">
                Metadata
              </p>
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
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}
