import { useState, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useStore } from '../store/useStore'
import ChatMessage from '../components/ChatMessage'
import { Send, Plus, MessageSquare, Sparkles, WifiOff } from 'lucide-react'

const SUGGESTIONS = [
  "What's today's revenue?",
  'List active trials',
  'Tell me about Alice',
  "Extend Alice's trial by 7 days",
]

export default function CopilotPage() {
  const {
    sessions,
    activeSessionId,
    chatLoading,
    sendMessage,
    newSession,
    backendOnline,
    operator,
  } = useStore()
  const messages = sessions[activeSessionId] || []
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    const text = input.trim()
    if (!text || chatLoading || !backendOnline) return
    setInput('')
    await sendMessage(text)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void handleSend()
    }
  }

  const handleNewSession = async () => {
    if (!backendOnline) return
    try {
      await newSession()
    } catch {
      /* lastError set in store */
    }
  }

  return (
    <div className="h-[calc(100vh-64px)] flex flex-col animate-fade-in -m-8">
      <div className="flex items-center justify-between px-6 py-3 border-b border-line">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-accent-purple/30 to-accent-cyan/30 flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-accent-cyan" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-text">AI Copilot</h1>
            <p className="text-[10px] font-mono text-text-dim">
              {activeSessionId
                ? `Session ${activeSessionId}`
                : 'No session — send a message to create one'}
              {' · '}
              <span className="text-text-muted">{operator.role}</span>
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => void handleNewSession()}
          disabled={!backendOnline}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg glass-sm text-xs font-medium text-text-muted hover:text-text hover:bg-panel-hover transition-all disabled:opacity-40"
        >
          <Plus className="w-3.5 h-3.5" />
          New Session
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
        {!backendOnline && (
          <div className="flex flex-col items-center justify-center py-16 text-center space-y-3">
            <WifiOff className="w-10 h-10 text-accent-amber" />
            <p className="text-sm font-semibold text-text">Backend offline</p>
            <p className="text-xs text-text-muted max-w-sm">
              Start the API on port 8000 (or set VITE_API_BASE_URL), then reconnect from Settings.
              The UI will not invent answers offline.
            </p>
          </div>
        )}

        {backendOnline &&
          (messages.length === 0 ||
            (messages.length === 1 && messages[0].role === 'assistant' && !messages[0].content.error)) && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="flex flex-col items-center justify-center py-12 space-y-6"
          >
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-accent-cyan/20 to-accent-purple/20 flex items-center justify-center">
              <MessageSquare className="w-8 h-8 text-accent-cyan" />
            </div>
            <div className="text-center space-y-2">
              <h2 className="text-lg font-bold text-text">Ask the live backend</h2>
              <p className="text-sm text-text-muted max-w-md">
                Queries run through the CrewAI pipeline against your vendor-scoped data. Write
                actions only create proposals — approve them on the Proposals page.
              </p>
            </div>
            <div className="flex flex-wrap gap-2 justify-center max-w-lg">
              {SUGGESTIONS.map((s, i) => (
                <motion.button
                  key={s}
                  type="button"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.25 + i * 0.06 }}
                  onClick={() => {
                    setInput(s)
                    inputRef.current?.focus()
                  }}
                  className="px-3 py-2 glass-sm text-xs text-text-muted hover:text-text hover:bg-panel-hover transition-all"
                >
                  {s}
                </motion.button>
              ))}
            </div>
          </motion.div>
        )}

        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="px-6 pb-5 pt-2">
        <div className="glass glow-border flex items-center gap-3 px-4 py-3">
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              backendOnline ? 'Ask the copilot…' : 'Connect the API to send messages'
            }
            disabled={chatLoading || !backendOnline}
            className="flex-1 bg-transparent text-sm text-text placeholder:text-text-dim outline-none disabled:opacity-50"
          />
          <button
            type="button"
            onClick={() => void handleSend()}
            disabled={!input.trim() || chatLoading || !backendOnline}
            className={`
              w-9 h-9 rounded-xl flex items-center justify-center transition-all
              ${
                input.trim() && !chatLoading && backendOnline
                  ? 'bg-accent-cyan text-white hover:bg-accent-cyan/90 shadow-glow active:scale-95'
                  : 'bg-white/5 text-text-dim cursor-not-allowed'
              }
            `}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <p className="text-[9px] text-text-dim text-center mt-2 font-mono">
          Live API · SSE stream · propose → approve → execute
        </p>
      </div>
    </div>
  )
}
