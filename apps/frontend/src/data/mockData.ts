// ═══════════════════════════════════════════════════════════════
// HobbyFi Mock Data — Mirrors backend seed data exactly
// ═══════════════════════════════════════════════════════════════

export type Role = 'owner' | 'admin' | 'support' | 'viewer'
export type ProposalStatus = 'pending' | 'approved' | 'rejected' | 'executed' | 'expired' | 'failed'
export type ProposalAction = 'extend_trial' | 'change_plan' | 'suspend_user' | 'update_membership_dates'
export type UserStatus = 'active' | 'suspended' | 'churned' | 'deleted'
export type MembershipStatus = 'active' | 'expired' | 'cancelled'
export type PlanType = 'free' | 'trial' | 'basic' | 'pro'

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

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: {
    text: string
    blocks?: any[]
    toolTraces?: any[]
    error?: string
  }
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
  actionType: ProposalAction
  payload: Record<string, any>
  preview: {
    before: Record<string, any>
    after: Record<string, any>
    [key: string]: any
  }
  status: ProposalStatus
  expiresAt: string
  createdAt: string
  decidedBy?: string
  decidedAt?: string
  executionResult?: Record<string, any>
}

export interface AuditEvent {
  id: string
  vendorId: string
  actorId: string | null
  eventType: string
  entityType: string
  entityId: string
  metadata: Record<string, any>
  createdAt: string
}

// ── Seed: Vendors ─────────────────────────────────────────
export const vendors: Vendor[] = [
  { id: 'v_acme', name: 'Acme Sports Club', timezone: 'Asia/Kolkata' },
  { id: 'v_beta', name: 'Beta Games Arena', timezone: 'America/New_York' },
]

// ── Seed: Vendor Operators ────────────────────────────────
export const operatorsByVendor: Record<string, VendorUser[]> = {
  v_acme: [
    { id: 'vu_admin', email: 'owner@acmesports.com', role: 'admin', displayName: 'Sachin Goyal' },
    { id: 'vu_support', email: 'support@acmesports.com', role: 'support', displayName: 'Support Lead' },
    { id: 'vu_viewer', email: 'viewer@acmesports.com', role: 'viewer', displayName: 'Audit Guest' },
  ],
  v_beta: [
    { id: 'vu_beta_admin', email: 'admin@betagames.com', role: 'admin', displayName: 'Beta Admin' },
  ],
}

// -- Removed unused mock arrays --

// ── Helper: Generate IDs ──────────────────────────────────
export function newId(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).substring(2, 11)}`
}
