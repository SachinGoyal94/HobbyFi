import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useStore } from '../store/useStore'
import ProposalCard from '../components/ProposalCard'
import { FileCheck2, Loader2, RefreshCw } from 'lucide-react'

const filterTabs: { label: string; value: string }[] = [
  { label: 'All', value: 'all' },
  { label: 'Pending', value: 'pending' },
  { label: 'Executed', value: 'executed' },
  { label: 'Rejected', value: 'rejected' },
  { label: 'Expired', value: 'expired' },
  { label: 'Failed', value: 'failed' },
]

export default function ProposalsPage() {
  const { proposals, proposalsLoading, fetchProposals, backendOnline } = useStore()
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    if (backendOnline) void fetchProposals()
  }, [backendOnline, fetchProposals])

  const filtered =
    filter === 'all' ? proposals : proposals.filter((p) => p.status === filter)

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text flex items-center gap-2">
            <FileCheck2 className="w-6 h-6 text-accent-amber" />
            Action Proposals
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Live from <code className="font-mono text-[11px] text-accent-cyan">GET /v1/copilot/proposals</code>.
            Approve runs server-side execution — the LLM never mutates data.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void fetchProposals()}
          disabled={!backendOnline || proposalsLoading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg glass-sm text-xs font-medium text-text-muted hover:text-text disabled:opacity-40"
        >
          {proposalsLoading ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <RefreshCw className="w-3.5 h-3.5" />
          )}
          Refresh
        </button>
      </div>

      <div className="flex gap-1 p-1 glass-sm w-fit flex-wrap">
        {filterTabs.map((tab) => {
          const isActive = filter === tab.value
          const count =
            tab.value === 'all'
              ? proposals.length
              : proposals.filter((p) => p.status === tab.value).length

          return (
            <button
              key={tab.value}
              type="button"
              onClick={() => setFilter(tab.value)}
              className={`
                px-3 py-1.5 rounded-lg text-xs font-medium transition-all
                ${
                  isActive
                    ? 'bg-accent-cyan/15 text-accent-cyan'
                    : 'text-text-muted hover:text-text hover:bg-white/[0.03]'
                }
              `}
            >
              {tab.label}
              {count > 0 && (
                <span
                  className={`ml-1.5 text-[9px] font-bold ${
                    isActive ? 'text-accent-cyan' : 'text-text-dim'
                  }`}
                >
                  {count}
                </span>
              )}
            </button>
          )
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <AnimatePresence mode="popLayout">
          {filtered.map((proposal) => (
            <ProposalCard key={proposal.id} proposal={proposal} />
          ))}
        </AnimatePresence>
      </div>

      {!proposalsLoading && filtered.length === 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center py-16"
        >
          <div className="w-12 h-12 rounded-2xl bg-white/5 flex items-center justify-center mx-auto mb-3">
            <FileCheck2 className="w-6 h-6 text-text-dim" />
          </div>
          <p className="text-sm text-text-muted">
            No {filter !== 'all' ? filter : ''} proposals from the API.
          </p>
          <p className="text-xs text-text-dim mt-1">
            Use the AI Copilot to draft a write action (e.g. extend Alice&apos;s trial).
          </p>
        </motion.div>
      )}
    </div>
  )
}
