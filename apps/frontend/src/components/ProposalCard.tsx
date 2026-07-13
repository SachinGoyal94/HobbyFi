import { useState } from 'react'
import { motion } from 'framer-motion'
import StatusBadge from './StatusBadge'
import type { Proposal } from '../types'
import { useStore } from '../store/useStore'
import { canApproveRole } from '../config/tenants'
import { Clock, User, ArrowRight, CheckCircle2, XCircle, Loader2 } from 'lucide-react'

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
  const decideProposal = useStore((s) => s.decideProposal)
  const operator = useStore((s) => s.operator)
  const backendOnline = useStore((s) => s.backendOnline)
  const [busy, setBusy] = useState(false)

  const info = actionLabels[proposal.actionType] || {
    label: proposal.actionType,
    icon: '📋',
  }
  const isPending = proposal.status === 'pending'
  const canDecide = isPending && canApproveRole(operator.role) && backendOnline

  const onDecide = async (decision: 'approve' | 'reject') => {
    if (busy) return
    setBusy(true)
    try {
      await decideProposal(proposal.id, decision)
    } catch {
      /* store lastError */
    } finally {
      setBusy(false)
    }
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.2 }}
      className={`glass p-5 space-y-4 border-l-2 transition-all ${
        isPending
          ? 'border-l-accent-amber'
          : proposal.status === 'executed'
            ? 'border-l-accent-green'
            : proposal.status === 'rejected'
              ? 'border-l-accent-red'
              : 'border-l-line-strong'
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-lg">{info.icon}</span>
          <div>
            <h3 className="text-sm font-bold text-text">{info.label}</h3>
            <p className="text-[10px] font-mono text-text-dim">{proposal.id}</p>
          </div>
        </div>
        <StatusBadge status={String(proposal.status)} size="md" />
      </div>

      <div className="flex items-center gap-2 text-xs text-text-muted">
        <User className="w-3.5 h-3.5 text-text-dim" />
        <span>
          Target:{' '}
          <span className="font-mono text-accent-cyan">
            {String(proposal.payload.user_id ?? '—')}
          </span>
        </span>
        {proposal.payload.game_slug != null && (
          <span className="text-text-dim">· {String(proposal.payload.game_slug)}</span>
        )}
      </div>

      <div className="flex gap-0 rounded-xl overflow-hidden border border-line">
        <div className="flex-1 p-3 bg-accent-red/[0.03]">
          <p className="text-[9px] font-mono uppercase tracking-wider text-text-dim mb-1.5">
            Before
          </p>
          {Object.entries(proposal.preview.before || {}).map(([k, v]) => (
            <p key={k} className="text-[11px] font-mono text-text-muted">
              <span className="text-text-dim">{k}:</span>{' '}
              <span className="text-accent-red">{formatValue(v)}</span>
            </p>
          ))}
          {Object.keys(proposal.preview.before || {}).length === 0 && (
            <p className="text-[11px] text-text-dim">—</p>
          )}
        </div>
        <div className="w-8 flex items-center justify-center bg-line/30">
          <ArrowRight className="w-3.5 h-3.5 text-text-dim" />
        </div>
        <div className="flex-1 p-3 bg-accent-green/[0.03]">
          <p className="text-[9px] font-mono uppercase tracking-wider text-text-dim mb-1.5">
            After
          </p>
          {Object.entries(proposal.preview.after || {}).map(([k, v]) => (
            <p key={k} className="text-[11px] font-mono text-text-muted">
              <span className="text-text-dim">{k}:</span>{' '}
              <span className="text-accent-green">{formatValue(v)}</span>
            </p>
          ))}
          {Object.keys(proposal.preview.after || {}).length === 0 && (
            <p className="text-[11px] text-text-dim">—</p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-4 text-[10px] text-text-dim flex-wrap">
        <span className="flex items-center gap-1">
          <Clock className="w-3 h-3" /> {formatTimeAgo(proposal.createdAt)}
        </span>
        <span>
          by <span className="font-mono text-text-muted">{proposal.proposedBy}</span>
        </span>
        {proposal.decidedBy && (
          <span>
            decided by{' '}
            <span className="font-mono text-text-muted">{proposal.decidedBy}</span>
          </span>
        )}
        {isPending && proposal.expiresAt && (
          <span className="text-accent-amber">
            expires {formatTimeAgo(proposal.expiresAt).replace('ago', '').trim() || 'soon'}
          </span>
        )}
      </div>

      {proposal.executionResult && (
        <div className="glass-sm p-2.5 flex items-start gap-2 text-xs">
          <CheckCircle2 className="w-3.5 h-3.5 text-accent-green flex-shrink-0 mt-0.5" />
          <pre className="text-[10px] font-mono text-text-muted overflow-x-auto">
            {JSON.stringify(proposal.executionResult, null, 0)}
          </pre>
        </div>
      )}

      {canDecide && (
        <div className="flex gap-2 pt-1">
          <button
            type="button"
            disabled={busy}
            onClick={() => void onDecide('approve')}
            className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl bg-accent-green/15 text-accent-green text-xs font-semibold hover:bg-accent-green/25 transition-all active:scale-[0.98] disabled:opacity-50"
          >
            {busy ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <CheckCircle2 className="w-3.5 h-3.5" />
            )}
            Approve & Execute
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => void onDecide('reject')}
            className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl bg-accent-red/15 text-accent-red text-xs font-semibold hover:bg-accent-red/25 transition-all active:scale-[0.98] disabled:opacity-50"
          >
            <XCircle className="w-3.5 h-3.5" />
            Reject
          </button>
        </div>
      )}

      {isPending && !canApproveRole(operator.role) && (
        <p className="text-[10px] text-accent-amber italic">
          Role &apos;{operator.role}&apos; cannot approve. Requires owner, admin, or support.
        </p>
      )}
    </motion.div>
  )
}

function formatValue(v: unknown): string {
  if (typeof v === 'string' && v.includes('T')) {
    try {
      return new Date(v).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    } catch {
      /* fall through */
    }
  }
  return String(v)
}

function formatTimeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const abs = Math.abs(diff)
  const mins = Math.floor(abs / 60_000)
  const suffix = diff >= 0 ? 'ago' : 'left'
  if (mins < 1) return diff >= 0 ? 'just now' : 'soon'
  if (mins < 60) return `${mins}m ${suffix}`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ${suffix}`
  return `${Math.floor(hrs / 24)}d ${suffix}`
}
