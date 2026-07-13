import { create } from 'zustand'
import type { AuditEvent, ChatMessage, Proposal, Role, Vendor, VendorUser } from '../types'
import {
  DEFAULT_OPERATOR,
  DEFAULT_VENDOR,
  canViewAuditRole,
  findOperator,
  findVendor,
  getOperators,
} from '../config/tenants'
import * as api from '../api/client'
import { mapApiAuditEvent, mapApiMessage, mapApiProposal, mapMessageContent, tempId } from '../lib/mappers'

interface StoreState {
  // Auth context (header stubs → backend)
  vendor: Vendor
  operator: VendorUser
  verifiedContext: api.VendorContextResponse | null

  // Backend connectivity
  backendOnline: boolean
  backendStatus: api.HealthResponse | null
  lastError: string | null

  // Data from API
  proposals: Proposal[]
  proposalsLoading: boolean
  auditEvents: AuditEvent[]
  auditLoading: boolean
  auditForbidden: boolean

  // Chat
  sessions: Record<string, ChatMessage[]>
  sessionOrder: string[]
  activeSessionId: string
  chatLoading: boolean

  // Actions
  clearError: () => void
  setRole: (role: Role) => void
  setVendor: (vendorId: string) => void
  checkBackend: () => Promise<void>
  refreshAll: () => Promise<void>
  fetchProposals: () => Promise<void>
  fetchAudit: () => Promise<void>
  newSession: () => Promise<string>
  switchSession: (id: string) => Promise<void>
  loadSessionMessages: (sessionId: string) => Promise<void>
  sendMessage: (text: string) => Promise<void>
  decideProposal: (id: string, decision: 'approve' | 'reject', reason?: string) => Promise<void>
  reseed: () => Promise<void>
}

function syncAuthHeaders(vendor: Vendor, operator: VendorUser) {
  api.setAuthHeaders({
    'x-vendor-id': vendor.id,
    'x-vendor-user-id': operator.id,
    'x-vendor-role': operator.role,
  })
}

function errMessage(err: unknown): string {
  if (err instanceof api.ApiError) return err.message
  if (err instanceof Error) return err.message
  return String(err)
}

export const useStore = create<StoreState>((set, get) => {
  syncAuthHeaders(DEFAULT_VENDOR, DEFAULT_OPERATOR)

  return {
    vendor: DEFAULT_VENDOR,
    operator: DEFAULT_OPERATOR,
    verifiedContext: null,

    backendOnline: false,
    backendStatus: null,
    lastError: null,

    proposals: [],
    proposalsLoading: false,
    auditEvents: [],
    auditLoading: false,
    auditForbidden: false,

    sessions: {},
    sessionOrder: [],
    activeSessionId: '',
    chatLoading: false,

    clearError: () => set({ lastError: null }),

    checkBackend: async () => {
      try {
        const health = await api.checkHealth()
        set({ backendOnline: true, backendStatus: health, lastError: null })
        await get().refreshAll()
      } catch (err) {
        set({
          backendOnline: false,
          backendStatus: null,
          verifiedContext: null,
          lastError: errMessage(err),
        })
      }
    },

    refreshAll: async () => {
      if (!get().backendOnline) return
      try {
        const me = await api.whoami()
        set({ verifiedContext: me })
      } catch (err) {
        // Auth headers invalid for current identity
        set({ verifiedContext: null, lastError: errMessage(err) })
        return
      }
      await Promise.all([get().fetchProposals(), get().fetchAudit()])
    },

    setRole: (role) => {
      const { vendor } = get()
      const op = findOperator(vendor.id, role)
      if (!op) {
        set({
          lastError: `No seeded user with role "${role}" for ${vendor.id}. Use admin, support, or viewer.`,
        })
        return
      }
      syncAuthHeaders(vendor, op)
      // Clear chat sessions when identity changes (scoped per operator on server)
      set({
        operator: op,
        sessions: {},
        sessionOrder: [],
        activeSessionId: '',
        lastError: null,
        verifiedContext: null,
      })
      if (get().backendOnline) void get().refreshAll()
    },

    setVendor: (vendorId) => {
      const v = findVendor(vendorId)
      const ops = getOperators(vendorId)
      const op = ops[0] ?? DEFAULT_OPERATOR
      syncAuthHeaders(v, op)
      set({
        vendor: v,
        operator: op,
        sessions: {},
        sessionOrder: [],
        activeSessionId: '',
        lastError: null,
        verifiedContext: null,
        proposals: [],
        auditEvents: [],
      })
      if (get().backendOnline) void get().refreshAll()
    },

    fetchProposals: async () => {
      if (!get().backendOnline) return
      set({ proposalsLoading: true })
      try {
        const { proposals } = await api.listProposals()
        set({
          proposals: proposals.map(mapApiProposal),
          proposalsLoading: false,
          lastError: null,
        })
      } catch (err) {
        set({ proposalsLoading: false, lastError: errMessage(err) })
      }
    },

    fetchAudit: async () => {
      if (!get().backendOnline) return
      const { operator } = get()
      if (!canViewAuditRole(operator.role)) {
        set({ auditEvents: [], auditForbidden: true, auditLoading: false })
        return
      }
      set({ auditLoading: true, auditForbidden: false })
      try {
        const { events } = await api.listAudit(200)
        set({
          auditEvents: events.map(mapApiAuditEvent),
          auditLoading: false,
          auditForbidden: false,
          lastError: null,
        })
      } catch (err) {
        const status = err instanceof api.ApiError ? err.status : 0
        set({
          auditLoading: false,
          auditForbidden: status === 403,
          auditEvents: status === 403 ? [] : get().auditEvents,
          lastError: status === 403 ? null : errMessage(err),
        })
      }
    },

    newSession: async () => {
      if (!get().backendOnline) throw new Error('Backend is offline')
      const session = await api.createSession()
      const welcome: ChatMessage = {
        id: tempId('m'),
        role: 'assistant',
        content: {
          text:
            'Session ready. Ask about users, trials, revenue, or propose a membership change. ' +
            'Writes create pending proposals — nothing mutates until you approve.',
        },
        createdAt: session.created_at,
      }
      set((s) => ({
        activeSessionId: session.id,
        sessions: { ...s.sessions, [session.id]: [welcome] },
        sessionOrder: [session.id, ...s.sessionOrder.filter((id) => id !== session.id)],
        lastError: null,
      }))
      return session.id
    },

    loadSessionMessages: async (sessionId) => {
      if (!get().backendOnline) return
      try {
        const { messages } = await api.listMessages(sessionId)
        const mapped = messages
          .map(mapApiMessage)
          .filter((m): m is ChatMessage => m !== null)
        set((s) => ({
          sessions: { ...s.sessions, [sessionId]: mapped },
        }))
      } catch (err) {
        set({ lastError: errMessage(err) })
      }
    },

    switchSession: async (id) => {
      set({ activeSessionId: id })
      if (!get().sessions[id]?.length && get().backendOnline) {
        await get().loadSessionMessages(id)
      }
    },

    sendMessage: async (text) => {
      let { activeSessionId, sessions, backendOnline } = get()

      if (!backendOnline) {
        set({ lastError: 'Backend is offline. Start the API and click Reconnect.' })
        return
      }

      if (!activeSessionId) {
        try {
          activeSessionId = await get().newSession()
          sessions = get().sessions
        } catch (err) {
          set({ lastError: errMessage(err) })
          return
        }
      }

      const history = sessions[activeSessionId] || []
      const userTempId = tempId('m')
      const botTempId = tempId('m')

      const userMsg: ChatMessage = {
        id: userTempId,
        role: 'user',
        content: { text },
        createdAt: new Date().toISOString(),
      }
      const botMsg: ChatMessage = {
        id: botTempId,
        role: 'assistant',
        content: { text: '' },
        createdAt: new Date().toISOString(),
        streaming: true,
        currentPhase: 'routing',
      }

      set({
        activeSessionId,
        chatLoading: true,
        lastError: null,
        sessions: {
          ...get().sessions,
          [activeSessionId]: [...history, userMsg, botMsg],
        },
      })

      const patchBot = (patch: Partial<ChatMessage>) => {
        set((s) => {
          const msgs = [...(s.sessions[activeSessionId] || [])]
          const idx = msgs.findIndex((m) => m.id === botTempId || m.id === patch.id)
          // Prefer finding by botTempId first, then by current streaming bot
          const byTemp = msgs.findIndex((m) => m.id === botTempId)
          const i = byTemp !== -1 ? byTemp : idx
          if (i !== -1) msgs[i] = { ...msgs[i], ...patch }
          return { sessions: { ...s.sessions, [activeSessionId]: msgs } }
        })
      }

      const patchUserId = (realId: string) => {
        set((s) => {
          const msgs = [...(s.sessions[activeSessionId] || [])]
          const i = msgs.findIndex((m) => m.id === userTempId)
          if (i !== -1) msgs[i] = { ...msgs[i], id: realId }
          return { sessions: { ...s.sessions, [activeSessionId]: msgs } }
        })
      }

      try {
        const stream = api.sendMessageStream(activeSessionId, text)

        for await (const { event, data } of stream) {
          if (event === 'status') {
            patchBot({ currentPhase: String((data as { phase?: string }).phase || 'running') })
          } else if (event === 'result') {
            const d = data as {
              text?: string
              blocks?: unknown[]
              tool_traces?: unknown[]
              user_message_id?: string
              assistant_message_id?: string
            }
            const content = mapMessageContent({
              text: d.text || '',
              blocks: d.blocks || [],
              tool_traces: d.tool_traces || [],
            })
            patchBot({
              id: d.assistant_message_id || botTempId,
              content,
              streaming: false,
              currentPhase: undefined,
            })
            if (d.user_message_id) patchUserId(d.user_message_id)
          } else if (event === 'done') {
            void get().fetchProposals()
            void get().fetchAudit()
          }
        }
        set({ chatLoading: false })
      } catch (err) {
        // Fallback: non-stream POST if SSE fails (some proxies break streams)
        try {
          const turn = await api.sendMessage(activeSessionId, text)
          const content = mapMessageContent(
            (turn.assistant_message.content || {}) as Record<string, unknown>,
          )
          set((s) => {
            const msgs = [...(s.sessions[activeSessionId] || [])]
            const botIdx = msgs.findIndex((m) => m.id === botTempId)
            const userIdx = msgs.findIndex((m) => m.id === userTempId)
            if (userIdx !== -1) {
              msgs[userIdx] = {
                ...msgs[userIdx],
                id: turn.user_message.id,
                createdAt: turn.user_message.created_at,
              }
            }
            if (botIdx !== -1) {
              msgs[botIdx] = {
                id: turn.assistant_message.id,
                role: 'assistant',
                content,
                createdAt: turn.assistant_message.created_at,
                streaming: false,
              }
            }
            return {
              chatLoading: false,
              sessions: { ...s.sessions, [activeSessionId]: msgs },
            }
          })
          void get().fetchProposals()
          void get().fetchAudit()
        } catch (fallbackErr) {
          patchBot({
            content: {
              text: '',
              error: errMessage(fallbackErr),
            },
            streaming: false,
            currentPhase: undefined,
          })
          set({ chatLoading: false, lastError: errMessage(fallbackErr) })
        }
      }
    },

    decideProposal: async (id, decision, reason) => {
      if (!get().backendOnline) throw new Error('Backend is offline')
      try {
        await api.decideProposal(id, decision, reason)
        await Promise.all([get().fetchProposals(), get().fetchAudit()])
        set({ lastError: null })
      } catch (err) {
        set({ lastError: errMessage(err) })
        throw err
      }
    },

    reseed: async () => {
      if (!get().backendOnline) throw new Error('Backend is offline')
      await api.reseedData()
      set({ sessions: {}, sessionOrder: [], activeSessionId: '' })
      await get().refreshAll()
    },
  }
})
