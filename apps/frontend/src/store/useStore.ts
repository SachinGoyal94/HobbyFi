import { create } from 'zustand'
import {
  type Vendor, type VendorUser, type Proposal, type AuditEvent, type ChatMessage,
  type Role,
  vendors, operatorsByVendor,
  newId,
} from '../data/mockData'
import * as api from '../api/client'

// ── Types ─────────────────────────────────────────────────
type TabId = 'dashboard' | 'copilot' | 'proposals' | 'users' | 'audit' | 'settings'

interface StoreState {
  // Auth context
  vendor: Vendor
  operator: VendorUser
  activeTab: TabId

  // Backend connectivity
  backendOnline: boolean
  backendStatus: api.HealthResponse | null

  // Data
  proposals: Proposal[]
  auditEvents: AuditEvent[]

  // Chat
  sessions: Record<string, ChatMessage[]>
  activeSessionId: string
  chatLoading: boolean

  // Actions
  setTab: (tab: TabId) => void
  setRole: (role: Role) => void
  setVendor: (vendorId: string) => void
  newSession: () => Promise<string>
  switchSession: (id: string) => void
  sendMessage: (text: string) => Promise<void>
  decideProposal: (id: string, decision: 'approve' | 'reject', reason?: string) => Promise<void>
  checkBackend: () => Promise<void>
  fetchProposals: () => Promise<void>
  fetchAudit: () => Promise<void>
}

// ── Sync auth headers whenever vendor/operator changes ────
function syncAuthHeaders(vendor: Vendor, operator: VendorUser) {
  api.setAuthHeaders({
    'x-vendor-id': vendor.id,
    'x-vendor-user-id': operator.id,
    'x-vendor-role': operator.role,
  })
}

// ── Store ─────────────────────────────────────────────────
export const useStore = create<StoreState>((set, get) => {
  // Initialize auth headers
  syncAuthHeaders(vendors[0], operatorsByVendor.v_acme[0])

  return {
    vendor: vendors[0],
    operator: operatorsByVendor.v_acme[0],
    activeTab: 'dashboard',

    backendOnline: false,
    backendStatus: null,


    
    // API backed data (Proposals, Audit, Chat)
    proposals: [],
    auditEvents: [],
    sessions: {},
    activeSessionId: '',
    chatLoading: false,

    // ── Tab Navigation ──────────────────────────────────────
    setTab: (tab) => set({ activeTab: tab }),

    // ── Check Backend Health ────────────────────────────────
    checkBackend: async () => {
      try {
        const health = await api.checkHealth()
        set({ backendOnline: true, backendStatus: health })
        // Auto-fetch real data when backend comes online
        const s = get()
        s.fetchProposals()
        s.fetchAudit()
      } catch {
        set({ backendOnline: false, backendStatus: null })
      }
    },

    // ── Switch Role ─────────────────────────────────────────
    setRole: (role) => {
      const { vendor } = get()
      const ops = operatorsByVendor[vendor.id] || []
      const op = ops.find(o => o.role === role) || {
        id: `vu_${vendor.id}_${role}`,
        email: `${role}@${vendor.id}.com`,
        role,
        displayName: `${role.charAt(0).toUpperCase() + role.slice(1)} (Simulated)`,
      }
      syncAuthHeaders(vendor, op)
      set({ operator: op })

      // Re-fetch data with new auth
      if (get().backendOnline) {
        get().fetchProposals()
        get().fetchAudit()
      }
    },

    // ── Switch Vendor ───────────────────────────────────────
    setVendor: (vendorId) => {
      const v = vendors.find(v => v.id === vendorId) || vendors[0]
      const ops = operatorsByVendor[vendorId] || []
      const op = ops[0] || { id: `vu_${vendorId}_owner`, email: `owner@${vendorId}.com`, role: 'owner' as Role, displayName: 'Default Owner' }
      syncAuthHeaders(v, op)
      set({ vendor: v, operator: op })

      // Re-fetch data with new auth
      if (get().backendOnline) {
        get().fetchProposals()
        get().fetchAudit()
      }
    },

    // ── Fetch Proposals from Backend ────────────────────────
    fetchProposals: async () => {
      if (!get().backendOnline) return
      try {
        const { proposals } = await api.listProposals()
        set({
          proposals: proposals.map(mapApiProposal),
        })
      } catch (err) {
        console.warn('[HobbyFi] Failed to fetch proposals:', err)
      }
    },

    // ── Fetch Audit from Backend ────────────────────────────
    fetchAudit: async () => {
      if (!get().backendOnline) return
      try {
        const { events } = await api.listAudit(200)
        set({
          auditEvents: events.map(mapApiAuditEvent),
        })
      } catch (err) {
        console.warn('[HobbyFi] Failed to fetch audit:', err)
      }
    },

    // ── Chat Session Management ─────────────────────────────
    newSession: async () => {
      if (!get().backendOnline) throw new Error('Backend is offline')
      
      const session = await api.createSession()
      const welcomeMsg: ChatMessage = {
        id: newId('m'),
        role: 'assistant',
        content: { text: 'New session opened. How can I help you manage your memberships today?' },
        createdAt: session.created_at,
      }
      set(s => ({
        activeSessionId: session.id,
        sessions: { ...s.sessions, [session.id]: [welcomeMsg] },
      }))
      return session.id
    },

    switchSession: (id) => {
      if (get().sessions[id]) set({ activeSessionId: id })
    },

    // ── Send Copilot Message ────────────────────────────────
    sendMessage: async (text) => {
      let { activeSessionId, sessions, backendOnline } = get()

      // Auto-create session if none exists
      if (!activeSessionId) {
        try {
          activeSessionId = await get().newSession()
          sessions = get().sessions
        } catch (err) {
          activeSessionId = newId('cs')
        }
      }

      const history = sessions[activeSessionId] || []
      const userMsg: ChatMessage = {
        id: newId('m'),
        role: 'user',
        content: { text },
        createdAt: new Date().toISOString(),
      }

      const botId = newId('m')
      const botMsg: ChatMessage = {
        id: botId,
        role: 'assistant',
        content: { text: '' },
        createdAt: new Date().toISOString(),
        streaming: true,
        currentPhase: 'routing',
      }

      set({
        activeSessionId,
        chatLoading: true,
        sessions: { ...sessions, [activeSessionId]: [...history, userMsg, botMsg] },
      })

      if (!backendOnline) {
        set(s => {
          const msgs = [...s.sessions[activeSessionId]]
          const idx = msgs.findIndex(m => m.id === botId)
          if (idx !== -1) {
            msgs[idx] = {
              ...msgs[idx],
              content: { text: '', error: 'Backend is offline. Please start the API server.' },
              streaming: false,
              currentPhase: undefined,
            }
          }
          return { chatLoading: false, sessions: { ...s.sessions, [activeSessionId]: msgs } }
        })
        return
      }

      try {
        const stream = api.sendMessageStream(activeSessionId, text)

        for await (const { event, data } of stream) {
          if (event === 'status') {
            updateBotPhase(set, activeSessionId, botId, data.phase)
          } else if (event === 'result') {
            // Build content from backend response
            const content: ChatMessage['content'] = {
              text: data.text || '',
              blocks: data.blocks || [],
            }
            set(s => {
              const msgs = [...s.sessions[activeSessionId]]
              const idx = msgs.findIndex(m => m.id === botId)
              if (idx !== -1) {
                msgs[idx] = {
                  ...msgs[idx],
                  id: data.assistant_message_id || botId,
                  content,
                  streaming: false,
                  currentPhase: undefined,
                }
              }
              // Update user msg ID from backend
              const userIdx = msgs.findIndex(m => m.id === userMsg.id)
              if (userIdx !== -1 && data.user_message_id) {
                msgs[userIdx] = { ...msgs[userIdx], id: data.user_message_id }
              }
              return { sessions: { ...s.sessions, [activeSessionId]: msgs } }
            })
          } else if (event === 'done') {
            // Refresh proposals (copilot may have created new ones)
            get().fetchProposals()
            get().fetchAudit()
          }
        }
        set({ chatLoading: false })
      } catch (err: any) {
        console.warn('[HobbyFi] SSE failed:', err)
        set(s => {
          const msgs = [...s.sessions[activeSessionId]]
          const idx = msgs.findIndex(m => m.id === botId)
          if (idx !== -1) {
            msgs[idx] = {
              ...msgs[idx],
              content: { text: '', error: err.message || 'API Error' },
              streaming: false,
              currentPhase: undefined,
            }
          }
          return { chatLoading: false, sessions: { ...s.sessions, [activeSessionId]: msgs } }
        })
      }
    },

    // ── Decide Proposal ─────────────────────────────────────
    decideProposal: async (id, decision, reason) => {
      if (!get().backendOnline) throw new Error('Backend is offline')

      try {
        await api.decideProposal(id, decision, reason)
        await Promise.all([get().fetchProposals(), get().fetchAudit()])
      } catch (err) {
        console.error('[HobbyFi] Proposal decision failed:', err)
        throw err
      }
    },
  }
})

// ── Map API Response → Frontend Model ─────────────────────
function mapApiProposal(p: api.ProposalResponse): Proposal {
  return {
    id: p.id,
    vendorId: p.vendor_id,
    sessionId: p.session_id || '',
    messageId: p.message_id || '',
    proposedBy: p.proposed_by,
    actionType: p.action_type as any,
    payload: p.payload,
    preview: {
      before: p.preview?.before || {},
      after: p.preview?.after || {},
      ...p.preview,
    },
    status: p.status as any,
    createdAt: p.created_at,
    expiresAt: p.expires_at,
    decidedBy: p.decided_by || undefined,
    decidedAt: p.decided_at || undefined,
    executionResult: p.execution_result || undefined,
  }
}

function mapApiAuditEvent(e: api.AuditEventResponse): AuditEvent {
  return {
    id: e.id,
    vendorId: e.vendor_id,
    actorId: e.actor_id || null,
    eventType: e.event_type,
    entityType: e.entity_type || '',
    entityId: e.entity_id || '',
    metadata: e.metadata,
    createdAt: e.created_at,
  }
}

// ── Helpers ───────────────────────────────────────────────
function updateBotPhase(set: any, sessionId: string, botId: string, phase: string) {
  set((s: StoreState) => {
    const msgs = [...s.sessions[sessionId]]
    const idx = msgs.findIndex(m => m.id === botId)
    if (idx !== -1) msgs[idx] = { ...msgs[idx], currentPhase: phase }
    return { sessions: { ...s.sessions, [sessionId]: msgs } }
  })
}
