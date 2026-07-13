/** Shared frontend domain types — aligned with backend schemas. */

export type Role = 'owner' | 'admin' | 'support' | 'viewer'

export type ProposalStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'executed'
  | 'expired'
  | 'failed'
  | 'cancelled'

export type ProposalAction =
  | 'extend_trial'
  | 'change_plan'
  | 'suspend_user'
  | 'update_membership_dates'

export interface Vendor {
  id: string
  name: string
  timezone: string
}

export interface VendorUser {
  id: string
  email: string
  role: Role
  displayName: string
}

export interface ToolTrace {
  tool: string
  args?: Record<string, unknown>
  result?: unknown
  [key: string]: unknown
}

export interface UiBlock {
  type: 'kpi' | 'table' | 'proposal_card' | string
  [key: string]: unknown
}

export interface ChatMessageContent {
  text: string
  blocks?: UiBlock[]
  toolTraces?: ToolTrace[]
  error?: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: ChatMessageContent
  createdAt: string
  streaming?: boolean
  currentPhase?: string
}

export interface Proposal {
  id: string
  vendorId: string
  sessionId: string
  messageId: string
  proposedBy: string
  actionType: ProposalAction | string
  payload: Record<string, unknown>
  preview: {
    before: Record<string, unknown>
    after: Record<string, unknown>
    [key: string]: unknown
  }
  status: ProposalStatus | string
  expiresAt: string
  createdAt: string
  decidedBy?: string
  decidedAt?: string
  executionResult?: Record<string, unknown>
}

export interface AuditEvent {
  id: string
  vendorId: string
  actorId: string | null
  eventType: string
  entityType: string
  entityId: string
  metadata: Record<string, unknown>
  createdAt: string
}

export type TabId = 'copilot' | 'proposals' | 'audit' | 'settings'
