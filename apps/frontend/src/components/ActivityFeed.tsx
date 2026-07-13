import type { AuditEvent } from '../data/mockData'

interface ActivityFeedProps {
  events: AuditEvent[]
  limit?: number
}

const eventColors: Record<string, string> = {
  'proposal.create': 'bg-accent-amber',
  'proposal.decide': 'bg-accent-purple',
  'proposal.execute': 'bg-accent-green',
  'copilot.turn': 'bg-accent-cyan',
  'auth.role_switch': 'bg-text-dim',
}

const eventLabels: Record<string, string> = {
  'proposal.create': 'Proposal Created',
  'proposal.decide': 'Proposal Decided',
  'proposal.execute': 'Proposal Executed',
  'copilot.turn': 'Copilot Turn',
  'auth.role_switch': 'Role Switch',
}

export default function ActivityFeed({ events, limit = 8 }: ActivityFeedProps) {
  const displayed = events.slice(0, limit)

  return (
    <div className="space-y-0">
      {displayed.map((ev, i) => {
        const dotColor = eventColors[ev.eventType] || 'bg-text-dim'
        const label = eventLabels[ev.eventType] || ev.eventType
        const time = formatTime(ev.createdAt)

        return (
          <div key={ev.id} className="flex gap-3 group">
            {/* Timeline line + dot */}
            <div className="flex flex-col items-center">
              <div className={`w-2 h-2 rounded-full ${dotColor} mt-1.5 flex-shrink-0 group-hover:scale-125 transition-transform`} />
              {i < displayed.length - 1 && (
                <div className="w-px flex-1 bg-line min-h-[28px]" />
              )}
            </div>

            {/* Content */}
            <div className="pb-4 flex-1 min-w-0">
              <div className="flex items-baseline gap-2">
                <span className="text-xs font-semibold text-text">{label}</span>
                <span className="text-[10px] text-text-dim font-mono">{time}</span>
              </div>
              <p className="text-[11px] text-text-muted mt-0.5 truncate">
                {ev.entityType && <span className="font-mono text-text-dim">{ev.entityId}</span>}
                {ev.actorId && <span className="ml-2">by <span className="font-mono">{ev.actorId}</span></span>}
              </p>
            </div>
          </div>
        )
      })}

      {events.length === 0 && (
        <p className="text-xs text-text-dim py-4 text-center">No events recorded yet.</p>
      )}
    </div>
  )
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffMins = Math.floor(diffMs / 60_000)
    if (diffMins < 60) return `${diffMins}m ago`
    const diffHrs = Math.floor(diffMins / 60)
    if (diffHrs < 24) return `${diffHrs}h ago`
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  } catch {
    return iso
  }
}
