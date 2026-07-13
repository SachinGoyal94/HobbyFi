interface StatusBadgeProps {
  status: string
  size?: 'sm' | 'md'
}

const statusStyles: Record<string, string> = {
  active: 'bg-accent-green/15 text-accent-green border-accent-green/20',
  pending: 'bg-accent-amber/15 text-accent-amber border-accent-amber/20',
  executed: 'bg-accent-cyan/15 text-accent-cyan border-accent-cyan/20',
  approved: 'bg-accent-green/15 text-accent-green border-accent-green/20',
  rejected: 'bg-accent-red/15 text-accent-red border-accent-red/20',
  expired: 'bg-white/5 text-text-dim border-white/10',
  failed: 'bg-accent-red/15 text-accent-red border-accent-red/20',
  suspended: 'bg-accent-amber/15 text-accent-amber border-accent-amber/20',
  churned: 'bg-white/5 text-text-dim border-white/10',
  deleted: 'bg-accent-red/10 text-accent-red border-accent-red/20',
  cancelled: 'bg-white/5 text-text-dim border-white/10',

  // Plan types
  free: 'bg-white/5 text-text-muted border-white/10',
  trial: 'bg-accent-amber/15 text-accent-amber border-accent-amber/20',
  basic: 'bg-accent-cyan/15 text-accent-cyan border-accent-cyan/20',
  pro: 'bg-accent-purple/15 text-accent-purple border-accent-purple/20',
}

export default function StatusBadge({ status, size = 'sm' }: StatusBadgeProps) {
  const key = status.toLowerCase()
  const styles = statusStyles[key] || 'bg-white/5 text-text-muted border-white/10'

  return (
    <span className={`
      inline-flex items-center gap-1 font-semibold uppercase tracking-wider border rounded-md
      ${size === 'sm' ? 'text-[9px] px-1.5 py-0.5' : 'text-[10px] px-2 py-1'}
      ${styles}
    `}>
      {key === 'pending' && (
        <span className="w-1.5 h-1.5 rounded-full bg-accent-amber animate-pulse-slow" />
      )}
      {status}
    </span>
  )
}
