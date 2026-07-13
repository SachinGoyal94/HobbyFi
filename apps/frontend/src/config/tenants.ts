/**
 * Demo tenant / operator identities — MUST match backend seed IDs in
 * apps/copilot-api/app/domain/seed.py exactly.
 *
 * These are not mock business data. They only populate auth headers
 * (x-vendor-id, x-vendor-user-id, x-vendor-role) until Phase 4 JWT/SSO.
 */

import type { Role, Vendor, VendorUser } from '../types'

export const vendors: Vendor[] = [
  { id: 'v_acme', name: 'Acme Sports', timezone: 'Asia/Kolkata' },
  { id: 'v_beta', name: 'Beta Games Co', timezone: 'UTC' },
]

/** Seeded operators per vendor. Only roles that exist in the DB. */
export const operatorsByVendor: Record<string, VendorUser[]> = {
  v_acme: [
    {
      id: 'vu_admin',
      email: 'admin@acme.example',
      role: 'admin',
      displayName: 'Acme Admin',
    },
    {
      id: 'vu_support',
      email: 'support@acme.example',
      role: 'support',
      displayName: 'Acme Support',
    },
    {
      id: 'vu_viewer',
      email: 'viewer@acme.example',
      role: 'viewer',
      displayName: 'Acme Viewer',
    },
  ],
  v_beta: [
    {
      id: 'vu_beta_admin',
      email: 'admin@beta.example',
      role: 'admin',
      displayName: 'Beta Admin',
    },
    {
      id: 'vu_beta_support',
      email: 'support@beta.example',
      role: 'support',
      displayName: 'Beta Support',
    },
    {
      id: 'vu_beta_viewer',
      email: 'viewer@beta.example',
      role: 'viewer',
      displayName: 'Beta Viewer',
    },
  ],
}

/** Roles that can be selected in the sandbox UI (must exist in seed). */
export const SELECTABLE_ROLES: {
  role: Role
  desc: string
  canPropose: boolean
  canApprove: boolean
  canAudit: boolean
}[] = [
  {
    role: 'admin',
    desc: 'Read, propose writes, approve/reject, view audit',
    canPropose: true,
    canApprove: true,
    canAudit: true,
  },
  {
    role: 'support',
    desc: 'Read + approve/reject; cannot create write proposals (tool RBAC)',
    canPropose: false,
    canApprove: true,
    canAudit: false,
  },
  {
    role: 'viewer',
    desc: 'Read-only — cannot propose or approve',
    canPropose: false,
    canApprove: false,
    canAudit: false,
  },
]

export const DEFAULT_VENDOR = vendors[0]
export const DEFAULT_OPERATOR = operatorsByVendor.v_acme[0]

export function getOperators(vendorId: string): VendorUser[] {
  return operatorsByVendor[vendorId] ?? []
}

export function findOperator(vendorId: string, role: Role): VendorUser | undefined {
  return getOperators(vendorId).find((o) => o.role === role)
}

export function findVendor(vendorId: string): Vendor {
  return vendors.find((v) => v.id === vendorId) ?? DEFAULT_VENDOR
}

/** Backend: approve/reject allowed for owner | admin | support */
export function canApproveRole(role: Role): boolean {
  return role === 'owner' || role === 'admin' || role === 'support'
}

/** Backend audit route requires owner | admin */
export function canViewAuditRole(role: Role): boolean {
  return role === 'owner' || role === 'admin'
}
