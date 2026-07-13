import { motion } from 'framer-motion'
import StatusBadge from './StatusBadge'
import type { Proposal } from '../data/mockData'
import { useStore } from '../store/useStore'
import { Clock, User, ArrowRight, CheckCircle2, XCircle } from 'lucide-react'

interface ProposalCardProps {
  proposal: Proposal
}

const actionLabels: Record<string, { label: string; icon: string }> = {
  extend_trial: { label: 'Extend Trial', icon: '📅' },
  change_plan: { label: 'Change Plan', icon: '🔄' },
  suspend_user: { label: 'Suspend User', icon: '🚫' },
  update_membership_dates: { label: 'Update Dates', icon: '📆' },
}

export default function ProposalCard({ proposal }: ProposalCardProps) {
  const decideProposal = useStore(s => s.decideProposal)
  const operator = useStore(s => s.operator)
  const info = actionLabels[proposal.actionType] || { label: proposal.actionType, icon: '📋' }
  const isPending = proposal.status === 'pending'
  const canDecide = isPending && ['owner', 'admin', 'support'].includes(operator.role)

  const timeAgo = formatTimeAgo(proposal.createdAt)

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.2 }}
      className={`glass p-5 space-y-4 border-l-2 transition-all ${
        isPending ? 'border-l-accent-amber' :
        proposal.status === 'executed' ? 'border-l-accent-green' :
        proposal.status === 'rejected' ? 'border-l-accent-red' :
        'border-l-line-strong'
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-lg">{info.icon}</span>
          <div>
            <h3 className="text-sm font-bold text-text">{info.label}</h3>
            <p className="text-[10px] font-mono text-text-dim">{proposal.id}</p>
          </div>
        </div>
        <StatusBadge status={proposal.status} size="md" />
      </div>

      {/* Target user */}
      <div className="flex items-center gap-2 text-xs text-text-muted">
        <User className="w-3.5 h-3.5 text-text-dim" />
        <span>Target: <span className="font-mono text-accent-cyan">{proposal.payload.user_id}</span></span>
        {proposal.payload.game_slug && (
          <span className="text-text-dim">· {proposal.payload.game_slug}</span>
        )}
      </div>

      {/* Before / After diff */}
      <div className="flex gap-0 rounded-xl overflow-hidden border border-line">
        <div className="flex-1 p-3 bg-accent-red/[0.03]">
          <p className="text-[9px] font-mono uppercase tracking-wider text-text-dim mb-1.5">Before</p>
          {Object.entries(proposal.preview.before || {}).map(([k, v]) => (
            <p key={k} className="text-[11px] font-mono text-text-muted">
              <span className="text-text-dim">{k}:</span>{' '}
              <span className="text-accent-red">{formatValue(v)}</span>
            </p>
          ))}
        </div>
        <div className="w-8 flex items-center justify-center bg-line/30">
          <ArrowRight className="w-3.5 h-3.5 text-text-dim" />
        </div>
        <div className="flex-1 p-3 bg-accent-green/[0.03]">
          <p className="text-[9px] font-mono uppercase tracking-wider text-text-dim mb-1.5">After</p>
          {Object.entries(proposal.preview.after || {}).map(([k, v]) => (
            <p key={k} className="text-[11px] font-mono text-text-muted">
              <span className="text-text-dim">{k}:</span>{' '}
              <span className="text-accent-green">{formatValue(v)}</span>
            </p>
          ))}
        </div>
      </div>

      {/* Metadata row */}
      <div className="flex items-center gap-4 text-[10px] text-text-dim">
        <span className="flex items-center gap-1">
          <Clock className="w-3 h-3" /> {timeAgo}
        </span>
        <span>by <span className="font-mono text-text-muted">{proposal.proposedBy}</span></span>
        {proposal.decidedBy && (
          <span>decided by <span className="font-mono text-text-muted">{proposal.decidedBy}</span></span>
        )}
      </div>

      {/* Execution result */}
      {proposal.executionResult && (
        <div className="glass-sm p-2.5 flex items-center gap-2 text-xs">
          <CheckCircle2 className="w-3.5 h-3.5 text-accent-green" />
          <span className="text-accent-green font-medium">{proposal.executionResult.message || 'Executed successfully'}</span>
        </div>
      )}

      {/* Action buttons */}
      {canDecide && (
        <div className="flex gap-2 pt-1">
          <button
            onClick={() => decideProposal(proposal.id, 'approve')}
            className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl bg-accent-green/15 text-accent-green text-xs font-semibold hover:bg-accent-green/25 transition-all active:scale-[0.98]"
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            Approve & Execute
          </button>
          <button
            onClick={() => decideProposal(proposal.id, 'reject')}
            className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl bg-accent-red/15 text-accent-red text-xs font-semibold hover:bg-accent-red/25 transition-all active:scale-[0.98]"
          >
            <XCircle className="w-3.5 h-3.5" />
            Reject
          </button>
        </div>
      )}

      {isPending && !canDecide && (
        <p className="text-[10px] text-accent-amber italic">
          Role '{operator.role}' cannot approve. Requires owner, admin, or support.
        </p>
      )}
    </motion.div>
  )
}

function formatValue(v: any): string {
  if (typeof v === 'string' && v.includes('T')) {
    try { return new Date(v).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) } catch { /* fall through */ }
  }
  return String(v)
}

function formatTimeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}
