/**
 * API client for HobbyFi Copilot backend.
 *
 * Auth is via stub headers (Phase 0):
 *   x-vendor-id, x-vendor-user-id, x-vendor-role
 *
 * Vite proxy forwards /v1 → http://localhost:8000
 */

// ── Auth Context (injected per-request) ───────────────────
export interface AuthHeaders {
  'x-vendor-id': string
  'x-vendor-user-id': string
  'x-vendor-role': string
}

let _authHeaders: AuthHeaders = {
  'x-vendor-id': 'v_acme',
  'x-vendor-user-id': 'vu_admin',
  'x-vendor-role': 'admin',
}

export function setAuthHeaders(headers: AuthHeaders) {
  _authHeaders = headers
}

export function getAuthHeaders(): AuthHeaders {
  return { ..._authHeaders }
}

// ── Fetch wrapper with auth ───────────────────────────────
async function apiFetch<T = any>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ..._authHeaders,
    ...(options.headers as Record<string, string> || {}),
  }

  const res = await fetch(path, { ...options, headers })

  if (!res.ok) {
    const body = await res.text()
    let detail = `API error ${res.status}`
    try {
      const json = JSON.parse(body)
      detail = json.detail || detail
    } catch { /* text fallback */ }
    throw new ApiError(res.status, detail)
  }

  return res.json()
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

// ── Health ─────────────────────────────────────────────────
export interface HealthResponse {
  status: string
  app: string
  env: string
  version: string
  gemini_model: string
  gemini_configured: boolean
  database: string
}

export async function checkHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>('/v1/health')
}

// ── Sessions ──────────────────────────────────────────────
export interface SessionResponse {
  id: string
  vendor_id: string
  vendor_user_id: string
  created_at: string
}

export interface MessageResponse {
  id: string
  session_id: string
  role: 'user' | 'assistant' | 'tool' | 'system'
  content: Record<string, any>
  created_at: string
}

export interface TurnResponse {
  session_id: string
  user_message: MessageResponse
  assistant_message: MessageResponse
}

export interface MessageListResponse {
  session_id: string
  messages: MessageResponse[]
}

export async function createSession(metadata: Record<string, any> = {}): Promise<SessionResponse> {
  return apiFetch<SessionResponse>('/v1/copilot/sessions', {
    method: 'POST',
    body: JSON.stringify({ metadata }),
  })
}

export async function getSession(sessionId: string): Promise<SessionResponse> {
  return apiFetch<SessionResponse>(`/v1/copilot/sessions/${sessionId}`)
}

export async function listMessages(sessionId: string): Promise<MessageListResponse> {
  return apiFetch<MessageListResponse>(`/v1/copilot/sessions/${sessionId}/messages`)
}

export async function sendMessage(sessionId: string, content: string): Promise<TurnResponse> {
  return apiFetch<TurnResponse>(`/v1/copilot/sessions/${sessionId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  })
}

/**
 * Send a message via SSE streaming.
 * Returns an async generator that yields events:
 *   { event: 'status', data: { phase: 'routing' | 'running' } }
 *   { event: 'result', data: { text, blocks, user_message_id, assistant_message_id } }
 *   { event: 'done', data: { message_id, session_id } }
 */
export async function* sendMessageStream(
  sessionId: string,
  content: string,
): AsyncGenerator<{ event: string; data: any }> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ..._authHeaders,
  }

  const res = await fetch(`/v1/copilot/sessions/${sessionId}/messages:stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ content }),
  })

  if (!res.ok) {
    const body = await res.text()
    let detail = `SSE error ${res.status}`
    try { detail = JSON.parse(body).detail || detail } catch { /* ok */ }
    throw new ApiError(res.status, detail)
  }

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''

    for (const part of parts) {
      const lines = part.trim().split('\n')
      let event = ''
      let data = ''

      for (const line of lines) {
        if (line.startsWith('event: ')) event = line.slice(7)
        else if (line.startsWith('data: ')) data = line.slice(6)
      }

      if (event && data) {
        try {
          yield { event, data: JSON.parse(data) }
        } catch {
          yield { event, data: {} }
        }
      }
    }
  }
}

// ── Proposals ─────────────────────────────────────────────
export interface ProposalResponse {
  id: string
  vendor_id: string
  session_id: string | null
  message_id: string | null
  proposed_by: string
  action_type: string
  payload: Record<string, any>
  preview: Record<string, any>
  status: string
  idempotency_key: string
  expires_at: string
  decided_by: string | null
  decided_at: string | null
  execution_result: Record<string, any> | null
  created_at: string
}

export interface ProposalListResponse {
  proposals: ProposalResponse[]
  count: number
}

export async function listProposals(status?: string): Promise<ProposalListResponse> {
  const q = status ? `?status=${status}` : ''
  return apiFetch<ProposalListResponse>(`/v1/copilot/proposals${q}`)
}

export async function getProposal(proposalId: string): Promise<ProposalResponse> {
  return apiFetch<ProposalResponse>(`/v1/copilot/proposals/${proposalId}`)
}

export async function decideProposal(
  proposalId: string,
  decision: 'approve' | 'reject',
  reason?: string,
): Promise<ProposalResponse> {
  return apiFetch<ProposalResponse>(`/v1/copilot/proposals/${proposalId}/decide`, {
    method: 'POST',
    body: JSON.stringify({ decision, reason: reason || null }),
  })
}

// ── Audit ─────────────────────────────────────────────────
export interface AuditEventResponse {
  id: string
  vendor_id: string
  actor_id: string | null
  event_type: string
  entity_type: string | null
  entity_id: string | null
  metadata: Record<string, any>
  created_at: string
}

export interface AuditListResponse {
  events: AuditEventResponse[]
  count: number
}

export async function listAudit(limit = 100): Promise<AuditListResponse> {
  return apiFetch<AuditListResponse>(`/v1/copilot/audit?limit=${limit}`)
}

// ── Vendor Context (whoami) ───────────────────────────────
export interface VendorContextResponse {
  vendor_id: string
  vendor_user_id: string
  email: string
  role: string
  timezone: string
  vendor_name: string
}

export async function whoami(): Promise<VendorContextResponse> {
  return apiFetch<VendorContextResponse>('/v1/copilot/me')
}

// ── Admin ─────────────────────────────────────────────────
export async function reseedData(): Promise<any> {
  return apiFetch('/v1/admin/seed', { method: 'POST' })
}
