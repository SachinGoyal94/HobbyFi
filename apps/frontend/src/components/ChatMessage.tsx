import { motion } from 'framer-motion'
import { Bot, User, ChevronDown, ChevronRight, AlertTriangle } from 'lucide-react'
import { useState } from 'react'
import type { ChatMessage as ChatMessageType } from '../data/mockData'
import DataTable from './DataTable'
import StatusBadge from './StatusBadge'
import { useStore } from '../store/useStore'

interface ChatMessageProps {
  message: ChatMessageType
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user'
  const { content, streaming, currentPhase } = message

  if (streaming) {
    return <StreamingIndicator phase={currentPhase || 'routing'} />
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}
    >
      {/* Avatar */}
      <div className={`
        w-8 h-8 rounded-xl flex-shrink-0 flex items-center justify-center
        ${isUser
          ? 'bg-accent-cyan/15 text-accent-cyan'
          : 'bg-gradient-to-br from-accent-purple/30 to-accent-cyan/30 text-white'
        }
      `}>
        {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
      </div>

      {/* Message body */}
      <div className={`flex-1 max-w-[85%] space-y-2 ${isUser ? 'flex flex-col items-end' : ''}`}>
        {/* Text content */}
        {(content.text || content.error) && (
          <div className={`
            inline-block px-4 py-3 text-sm leading-relaxed
            ${isUser
              ? 'glass-sm bg-accent-cyan/5 border-accent-cyan/10 text-text rounded-2xl rounded-tr-md'
              : content.error
                ? 'glass-sm border-accent-red/20 bg-accent-red/5 text-text rounded-2xl rounded-tl-md'
                : 'glass-sm text-text rounded-2xl rounded-tl-md'
            }
          `}>
            {content.error && (
              <div className="flex items-center gap-1.5 mb-2 text-accent-red text-[10px] font-semibold uppercase tracking-wider">
                <AlertTriangle className="w-3 h-3" />
                {content.error}
              </div>
            )}
            <MessageText text={content.text} />
          </div>
        )}

        {/* Rich blocks */}
        {content.blocks?.map((block, i) => (
          <RichBlock key={i} block={block} />
        ))}

        {/* Tool traces */}
        {content.toolTraces && content.toolTraces.length > 0 && (
          <ToolTraces traces={content.toolTraces} />
        )}
      </div>
    </motion.div>
  )
}

// ── Streaming Indicator ───────────────────────────────────
function StreamingIndicator({ phase }: { phase: string }) {
  const phaseLabels: Record<string, string> = {
    routing: 'Classifying intent…',
    analyzing: 'Running tools…',
    composing: 'Composing response…',
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex gap-3"
    >
      <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-accent-purple/30 to-accent-cyan/30 flex items-center justify-center animate-pulse-slow">
        <Bot className="w-4 h-4 text-white" />
      </div>
      <div className="glass-sm px-4 py-3 flex items-center gap-3">
        <div className="flex gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan animate-bounce-subtle" style={{ animationDelay: '0s' }} />
          <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan animate-bounce-subtle" style={{ animationDelay: '0.15s' }} />
          <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan animate-bounce-subtle" style={{ animationDelay: '0.3s' }} />
        </div>
        <span className="text-xs text-text-muted font-medium">{phaseLabels[phase] || phase}</span>
        <StatusBadge status={phase} size="sm" />
      </div>
    </motion.div>
  )
}

// ── Markdown-light text renderer ──────────────────────────
function MessageText({ text }: { text: string }) {
  // Very simple markdown: **bold**, `code`
  const parts = text.split(/(\*\*.*?\*\*|`.*?`|\n)/g)
  return (
    <span>
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return <strong key={i} className="font-semibold text-text">{part.slice(2, -2)}</strong>
        }
        if (part.startsWith('`') && part.endsWith('`')) {
          return <code key={i} className="font-mono text-accent-cyan bg-accent-cyan/10 px-1 py-0.5 rounded text-[11px]">{part.slice(1, -1)}</code>
        }
        if (part === '\n') return <br key={i} />
        return <span key={i}>{part}</span>
      })}
    </span>
  )
}

// ── Rich Block Renderer ───────────────────────────────────
function RichBlock({ block }: { block: any }) {
  if (block.type === 'kpi') {
    return (
      <div className="glass-sm p-3 inline-flex items-center gap-3 min-w-[160px]">
        <div
          className="w-2 h-8 rounded-full"
          style={{ backgroundColor: block.color }}
        />
        <div>
          <p className="text-lg font-bold text-text">{block.value}</p>
          <p className="text-[10px] text-text-dim uppercase tracking-wider font-medium">{block.title}</p>
        </div>
      </div>
    )
  }

  if (block.type === 'table') {
    return <DataTable title={block.title} columns={block.columns} rows={block.rows} compact />
  }

  if (block.type === 'proposal_card') {
    return <InlineProposalCard block={block} />
  }

  return null
}

// ── Inline Proposal Card ──────────────────────────────────
function InlineProposalCard({ block }: { block: any }) {
  const decideProposal = useStore(s => s.decideProposal)
  const proposal = useStore(s => s.proposals.find(p => p.id === block.proposal_id))
  const status = proposal?.status || block.status

  const actionLabels: Record<string, string> = {
    extend_trial: '📅 Extend Trial',
    change_plan: '🔄 Change Plan',
    suspend_user: '🚫 Suspend User',
    update_membership_dates: '📆 Update Dates',
  }

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className={`glass-sm p-4 space-y-3 border-l-2 ${
        status === 'pending' ? 'border-l-accent-amber' :
        status === 'executed' ? 'border-l-accent-green' :
        'border-l-accent-red'
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold text-text">{actionLabels[block.action_type] || block.action_type}</span>
        <StatusBadge status={status} />
      </div>

      {/* Preview diff */}
      {block.preview && (
        <div className="flex gap-4 text-[11px]">
          <div className="space-y-1">
            <p className="text-text-dim font-mono uppercase text-[9px]">Before</p>
            {Object.entries(block.preview.before || {}).map(([k, v]) => (
              <p key={k} className="text-accent-red font-mono">
                <span className="text-text-dim">{k}:</span> {String(v)}
              </p>
            ))}
          </div>
          <div className="w-px bg-line self-stretch" />
          <div className="space-y-1">
            <p className="text-text-dim font-mono uppercase text-[9px]">After</p>
            {Object.entries(block.preview.after || {}).map(([k, v]) => (
              <p key={k} className="text-accent-green font-mono">
                <span className="text-text-dim">{k}:</span> {String(v)}
              </p>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      {status === 'pending' && (
        <div className="flex gap-2 pt-1">
          <button
            onClick={() => decideProposal(block.proposal_id, 'approve')}
            className="flex-1 py-1.5 rounded-lg bg-accent-green/15 text-accent-green text-xs font-semibold hover:bg-accent-green/25 transition-colors"
          >
            ✓ Approve
          </button>
          <button
            onClick={() => decideProposal(block.proposal_id, 'reject')}
            className="flex-1 py-1.5 rounded-lg bg-accent-red/15 text-accent-red text-xs font-semibold hover:bg-accent-red/25 transition-colors"
          >
            ✗ Reject
          </button>
        </div>
      )}

      <p className="text-[9px] font-mono text-text-dim">{block.proposal_id}</p>
    </motion.div>
  )
}

// ── Tool Traces ───────────────────────────────────────────
function ToolTraces({ traces }: { traces: any[] }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="mt-1">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-[10px] text-text-dim hover:text-text-muted transition-colors font-mono"
      >
        {open ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        {traces.length} tool call{traces.length > 1 ? 's' : ''}
      </button>
      {open && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="mt-1 space-y-1"
        >
          {traces.map((trace, i) => (
            <div key={i} className="glass-sm px-3 py-2 font-mono text-[10px] text-text-dim space-y-0.5">
              <span className="text-accent-cyan font-semibold">{trace.tool}</span>
              <span className="text-text-dim ml-1">({JSON.stringify(trace.args)})</span>
            </div>
          ))}
        </motion.div>
      )}
    </div>
  )
}
