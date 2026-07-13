/** Map backend API shapes → frontend models. */

import type { AuditEvent, ChatMessage, ChatMessageContent, Proposal, ToolTrace, UiBlock } from '../types'
import type { AuditEventResponse, MessageResponse, ProposalResponse } from '../api/client'

export function mapApiProposal(p: ProposalResponse): Proposal {
  const preview = p.preview || {}
  return {
    id: p.id,
    vendorId: p.vendor_id,
    sessionId: p.session_id || '',
    messageId: p.message_id || '',
    proposedBy: p.proposed_by,
    actionType: p.action_type,
    payload: p.payload || {},
    preview: {
      before: (preview.before as Record<string, unknown>) || {},
      after: (preview.after as Record<string, unknown>) || {},
      ...preview,
    },
    status: p.status,
    createdAt: p.created_at,
    expiresAt: p.expires_at,
    decidedBy: p.decided_by || undefined,
    decidedAt: p.decided_at || undefined,
    executionResult: p.execution_result || undefined,
  }
}

export function mapApiAuditEvent(e: AuditEventResponse): AuditEvent {
  return {
    id: e.id,
    vendorId: e.vendor_id,
    actorId: e.actor_id,
    eventType: e.event_type,
    entityType: e.entity_type || '',
    entityId: e.entity_id || '',
    metadata: e.metadata || {},
    createdAt: e.created_at,
  }
}

export function mapMessageContent(raw: Record<string, unknown>): ChatMessageContent {
  const toolTracesRaw = (raw.tool_traces ?? raw.toolTraces) as ToolTrace[] | undefined
  return {
    text: String(raw.text ?? ''),
    blocks: (raw.blocks as UiBlock[]) || [],
    toolTraces: Array.isArray(toolTracesRaw) ? toolTracesRaw : undefined,
    error: raw.error ? String(raw.error) : undefined,
  }
}

export function mapApiMessage(m: MessageResponse): ChatMessage | null {
  if (m.role !== 'user' && m.role !== 'assistant') return null
  const content =
    typeof m.content === 'object' && m.content !== null
      ? mapMessageContent(m.content as Record<string, unknown>)
      : { text: String(m.content ?? '') }

  return {
    id: m.id,
    role: m.role,
    content,
    createdAt: m.created_at,
  }
}

export function tempId(prefix: string): string {
  return `${prefix}_${crypto.randomUUID().replace(/-/g, '').slice(0, 12)}`
}
