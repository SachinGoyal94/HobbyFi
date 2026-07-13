import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useStore } from '../store/useStore'
import ProposalCard from '../components/ProposalCard'
import { FileCheck2 } from 'lucide-react'

const filterTabs: { label: string; value: string }[] = [
  { label: 'All', value: 'all' },
  { label: 'Pending', value: 'pending' },
  { label: 'Executed', value: 'executed' },
  { label: 'Rejected', value: 'rejected' },
  { label: 'Expired', value: 'expired' },
]

export default function ProposalsPage() {
  const { vendor, proposals } = useStore()
  const [filter, setFilter] = useState('all')

  const vendorProposals = proposals.filter(p => p.vendorId === vendor.id)
  const filtered = filter === 'all'
    ? vendorProposals
    : vendorProposals.filter(p => p.status === filter)

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-text flex items-center gap-2">
          <FileCheck2 className="w-6 h-6 text-accent-amber" />
          Action Proposals
        </h1>
        <p className="text-sm text-text-muted mt-1">
          Review and approve AI-drafted membership changes. All proposals require human approval before execution.
        </p>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-1 p-1 glass-sm w-fit">
        {filterTabs.map(tab => {
          const isActive = filter === tab.value
          const count = tab.value === 'all'
            ? vendorProposals.length
            : vendorProposals.filter(p => p.status === tab.value).length

          return (
            <button
              key={tab.value}
              onClick={() => setFilter(tab.value)}
              className={`
                px-3 py-1.5 rounded-lg text-xs font-medium transition-all relative
                ${isActive
                  ? 'bg-accent-cyan/15 text-accent-cyan'
                  : 'text-text-muted hover:text-text hover:bg-white/[0.03]'
                }
              `}
            >
              {tab.label}
              {count > 0 && (
                <span className={`ml-1.5 text-[9px] font-bold ${isActive ? 'text-accent-cyan' : 'text-text-dim'}`}>
                  {count}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Proposal Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <AnimatePresence mode="popLayout">
          {filtered.map(proposal => (
            <ProposalCard key={proposal.id} proposal={proposal} />
          ))}
        </AnimatePresence>
      </div>

      {filtered.length === 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center py-16"
        >
          <div className="w-12 h-12 rounded-2xl bg-white/5 flex items-center justify-center mx-auto mb-3">
            <FileCheck2 className="w-6 h-6 text-text-dim" />
          </div>
          <p className="text-sm text-text-muted">No {filter !== 'all' ? filter : ''} proposals found.</p>
          <p className="text-xs text-text-dim mt-1">Use the AI Copilot to draft new proposals.</p>
        </motion.div>
      )}
    </div>
  )
}
