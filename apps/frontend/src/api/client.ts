/**
 * API client for HobbyFi Copilot backend.
 *
 * Auth via stub headers (demo): x-vendor-id, x-vendor-user-id, x-vendor-role
 *
 * Base URL:
 *   - Dev: empty → relative /v1 (Vite proxy → localhost:8000)
 *   - Prod: set VITE_API_BASE_URL (e.g. https://api.example.com)
 */

// ── Config ────────────────────────────────────────────────

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') || ''

function url(path: string): string {
  if (path.startsWith('http')) return path
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`
}

// ── Auth Context ──────────────────────────────────────────

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
  _authHeaders = { ...headers }
}

export function getAuthHeaders(): AuthHeaders {
  return { ..._authHeaders }
}

// ── Errors ────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public body?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

function parseDetail(body: string, status: number): { message: string; parsed?: unknown } {
  let detail = `API error ${status}`
  let parsed: unknown
  try {
    parsed = JSON.parse(body)
    if (parsed && typeof parsed === 'object' && 'detail' in parsed) {
      const d = (parsed as { detail: unknown }).detail
      if (typeof d === 'string') detail = d
      else if (Array.isArray(d)) {
        detail = d
          .map((x) => (typeof x === 'object' && x && 'msg' in x ? String((x as { msg: string }).msg) : JSON.stringify(x)))
          .join('; ')
      } else detail = JSON.stringify(d)
    }
  } catch {
    if (body.trim()) detail = body.slice(0, 200)
  }
  return { message: detail, parsed }
}

// ── Fetch wrapper ─────────────────────────────────────────

async function apiFetch<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    ..._authHeaders,
    ...(options.headers as Record<string, string> | undefined),
  }

  let res: Response
  try {
    res = await fetch(url(path), { ...options, headers })
  } catch (err) {
    throw new ApiError(0, err instanceof Error ? err.message : 'Network error — is the API running?')
  }

  if (!res.ok) {
    const body = await res.text()
    const { message, parsed } = parseDetail(body, res.status)
    throw new ApiError(res.status, message, parsed)
  }

  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

// ── Health ────────────────────────────────────────────────

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
  content: Record<string, unknown>
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

export async function createSession(metadata: Record<string, unknown> = {}): Promise<SessionResponse> {
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

export type StreamEvent =
  | { event: 'status'; data: { phase: string } }
  | {
      event: 'result'
      data: {
        text?: string
        blocks?: unknown[]
        tool_traces?: unknown[]
        user_message_id?: string
        assistant_message_id?: string
      }
    }
  | { event: 'done'; data: { message_id?: string; session_id?: string } }
  | { event: string; data: Record<string, unknown> }

/**
 * SSE stream for a chat turn.
 * Yields status → result → done (backend Phase 1 pattern).
 */
export async function* sendMessageStream(
  sessionId: string,
  content: string,
): AsyncGenerator<StreamEvent> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
    ..._authHeaders,
  }

  let res: Response
  try {
    res = await fetch(url(`/v1/copilot/sessions/${sessionId}/messages:stream`), {
      method: 'POST',
      headers,
      body: JSON.stringify({ content }),
    })
  } catch (err) {
    throw new ApiError(0, err instanceof Error ? err.message : 'Network error during stream')
  }

  if (!res.ok) {
    const body = await res.text()
    const { message, parsed } = parseDetail(body, res.status)
    throw new ApiError(res.status, message, parsed)
  }

  if (!res.body) {
    throw new ApiError(0, 'Streaming not supported by this browser/proxy')
  }

  const reader = res.body.getReader()
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
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) data = line.slice(5).trim()
      }

      if (event && data) {
        try {
          yield { event, data: JSON.parse(data) } as StreamEvent
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
  payload: Record<string, unknown>
  preview: Record<string, unknown>
  status: string
  idempotency_key: string
  expires_at: string
  decided_by: string | null
  decided_at: string | null
  execution_result: Record<string, unknown> | null
  created_at: string
}

export interface ProposalListResponse {
  proposals: ProposalResponse[]
  count: number
}

export async function listProposals(status?: string): Promise<ProposalListResponse> {
  const q = status ? `?status=${encodeURIComponent(status)}` : ''
  return apiFetch<ProposalListResponse>(`/v1/copilot/proposals${q}`)
}

export async function getProposal(proposalId: string): Promise<ProposalResponse> {
  return apiFetch<ProposalResponse>(`/v1/copilot/proposals/${encodeURIComponent(proposalId)}`)
}

export async function decideProposal(
  proposalId: string,
  decision: 'approve' | 'reject',
  reason?: string,
): Promise<ProposalResponse> {
  return apiFetch<ProposalResponse>(
    `/v1/copilot/proposals/${encodeURIComponent(proposalId)}/decide`,
    {
      method: 'POST',
      body: JSON.stringify({ decision, reason: reason || null }),
    },
  )
}

// ── Audit ─────────────────────────────────────────────────

export interface AuditEventResponse {
  id: string
  vendor_id: string
  actor_id: string | null
  event_type: string
  entity_type: string | null
  entity_id: string | null
  metadata: Record<string, unknown>
  created_at: string
}

export interface AuditListResponse {
  events: AuditEventResponse[]
  count: number
}

export async function listAudit(limit = 100): Promise<AuditListResponse> {
  return apiFetch<AuditListResponse>(`/v1/copilot/audit?limit=${limit}`)
}

// ── Vendor context ────────────────────────────────────────

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

export async function reseedData(): Promise<Record<string, number>> {
  return apiFetch('/v1/admin/seed', { method: 'POST' })
}

export { API_BASE }
