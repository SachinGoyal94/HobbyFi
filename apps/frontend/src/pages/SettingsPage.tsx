import { useState } from 'react'
import { motion } from 'framer-motion'
import { useStore } from '../store/useStore'
import { SELECTABLE_ROLES, vendors } from '../config/tenants'
import type { Role } from '../types'
import {
  Settings,
  Shield,
  Building2,
  UserCircle,
  Info,
  Wifi,
  WifiOff,
  RefreshCw,
  Database,
  Loader2,
} from 'lucide-react'
import { API_BASE } from '../api/client'

export default function SettingsPage() {
  const {
    vendor,
    operator,
    setRole,
    setVendor,
    backendOnline,
    backendStatus,
    checkBackend,
    verifiedContext,
    reseed,
  } = useStore()
  const [reseeding, setReseeding] = useState(false)
  const [reseedMsg, setReseedMsg] = useState<string | null>(null)

  const handleReseed = async () => {
    setReseeding(true)
    setReseedMsg(null)
    try {
      await reseed()
      setReseedMsg('Demo data reseeded successfully.')
    } catch (err) {
      setReseedMsg(err instanceof Error ? err.message : 'Reseed failed')
    } finally {
      setReseeding(false)
    }
  }

  return (
    <div className="space-y-8 animate-fade-in max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-text flex items-center gap-2">
          <Settings className="w-6 h-6 text-text-muted" />
          Demo Settings
        </h1>
        <p className="text-sm text-text-muted mt-1">
          Switch seeded tenants and roles. Headers map 1:1 to backend{' '}
          <code className="font-mono text-[11px]">VendorUser</code> rows — no synthetic IDs.
        </p>
      </div>

      <div className="glass-sm p-4 flex items-start gap-3 border-l-2 border-l-accent-cyan">
        <Info className="w-4 h-4 text-accent-cyan flex-shrink-0 mt-0.5" />
        <div className="text-xs text-text-muted space-y-1">
          <p>
            All screens load from the API when online. Identity is header-based for the demo
            (Phase 0–3). Production will use JWT/SSO with the same{' '}
            <code className="font-mono">VendorContext</code> shape.
          </p>
        </div>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className={`glass p-6 space-y-4 border-l-2 ${
          backendOnline ? 'border-l-accent-green' : 'border-l-accent-amber'
        }`}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {backendOnline ? (
              <Wifi className="w-4 h-4 text-accent-green" />
            ) : (
              <WifiOff className="w-4 h-4 text-accent-amber" />
            )}
            <h2 className="text-sm font-semibold text-text">Backend Connection</h2>
          </div>
          <button
            type="button"
            onClick={() => void checkBackend()}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg glass-sm text-xs font-medium text-text-muted hover:text-text transition-all"
          >
            <RefreshCw className="w-3 h-3" />
            Reconnect
          </button>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="glass-sm p-3">
            <p className="text-[9px] font-mono uppercase tracking-wider text-text-dim">Status</p>
            <p
              className={`text-sm font-bold mt-0.5 ${
                backendOnline ? 'text-accent-green' : 'text-accent-amber'
              }`}
            >
              {backendOnline ? 'Connected' : 'Offline'}
            </p>
          </div>
          <div className="glass-sm p-3">
            <p className="text-[9px] font-mono uppercase tracking-wider text-text-dim">API base</p>
            <p className="text-xs font-mono mt-0.5 text-text-muted truncate">
              {API_BASE || '/v1 (same origin / Vite proxy)'}
            </p>
          </div>
          {backendStatus && (
            <>
              <div className="glass-sm p-3">
                <p className="text-[9px] font-mono uppercase tracking-wider text-text-dim">
                  AI Model
                </p>
                <p className="text-xs font-mono mt-0.5 text-accent-cyan">
                  {backendStatus.gemini_model}
                </p>
              </div>
              <div className="glass-sm p-3">
                <p className="text-[9px] font-mono uppercase tracking-wider text-text-dim">
                  Database
                </p>
                <p className="text-xs font-mono mt-0.5 text-text-muted">
                  {backendStatus.database}
                </p>
              </div>
            </>
          )}
        </div>

        {verifiedContext && (
          <div className="glass-sm p-3 text-[11px] font-mono text-text-muted space-y-0.5">
            <p className="text-[9px] uppercase tracking-wider text-text-dim mb-1">
              GET /v1/copilot/me
            </p>
            <p>
              {verifiedContext.vendor_id} · {verifiedContext.vendor_user_id} ·{' '}
              <span className="text-accent-cyan">{verifiedContext.role}</span>
            </p>
            <p className="text-text-dim">
              {verifiedContext.email} · {verifiedContext.timezone}
            </p>
          </div>
        )}

        {!backendOnline && (
          <p className="text-[10px] text-accent-amber">
            Unreachable. Dev: run{' '}
            <code className="font-mono bg-accent-amber/10 px-1 py-0.5 rounded">
              uvicorn app.main:app --reload --port 8000
            </code>{' '}
            and open the UI via Vite so /v1 is proxied.
          </p>
        )}
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass p-6 space-y-4"
      >
        <div className="flex items-center gap-2">
          <Shield className="w-4 h-4 text-accent-purple" />
          <h2 className="text-sm font-semibold text-text">Active Role</h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {SELECTABLE_ROLES.map(({ role, desc, canPropose, canApprove, canAudit }) => (
            <button
              key={role}
              type="button"
              onClick={() => setRole(role as Role)}
              className={`
                p-3 rounded-xl text-left transition-all border
                ${
                  operator.role === role
                    ? 'bg-accent-cyan/10 border-accent-cyan/30 shadow-glow'
                    : 'bg-white/[0.02] border-line hover:border-line-strong hover:bg-white/[0.04]'
                }
              `}
            >
              <p
                className={`text-xs font-bold uppercase tracking-wider ${
                  operator.role === role ? 'text-accent-cyan' : 'text-text'
                }`}
              >
                {role}
              </p>
              <p className="text-[10px] text-text-dim mt-0.5">{desc}</p>
              <p className="text-[9px] font-mono text-text-dim mt-2 space-x-1">
                <span className={canPropose ? 'text-accent-green' : 'text-text-dim'}>propose</span>
                <span>·</span>
                <span className={canApprove ? 'text-accent-green' : 'text-text-dim'}>approve</span>
                <span>·</span>
                <span className={canAudit ? 'text-accent-green' : 'text-text-dim'}>audit</span>
              </p>
            </button>
          ))}
        </div>

        <div className="glass-sm p-3 flex items-center gap-2 text-xs">
          <UserCircle className="w-4 h-4 text-text-dim" />
          <span className="text-text-muted">
            Headers:{' '}
            <span className="font-mono text-accent-cyan">{operator.id}</span> · {operator.email}
          </span>
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="glass p-6 space-y-4"
      >
        <div className="flex items-center gap-2">
          <Building2 className="w-4 h-4 text-accent-amber" />
          <h2 className="text-sm font-semibold text-text">Active Tenant</h2>
        </div>

        <div className="space-y-2">
          {vendors.map((v) => (
            <button
              key={v.id}
              type="button"
              onClick={() => setVendor(v.id)}
              className={`
                w-full p-3 rounded-xl text-left transition-all border flex items-center gap-3
                ${
                  vendor.id === v.id
                    ? 'bg-accent-amber/10 border-accent-amber/30 shadow-glow-amber'
                    : 'bg-white/[0.02] border-line hover:border-line-strong hover:bg-white/[0.04]'
                }
              `}
            >
              <div
                className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold ${
                  vendor.id === v.id
                    ? 'bg-accent-amber/20 text-accent-amber'
                    : 'bg-white/5 text-text-dim'
                }`}
              >
                {v.name.charAt(0)}
              </div>
              <div>
                <p
                  className={`text-xs font-semibold ${
                    vendor.id === v.id ? 'text-accent-amber' : 'text-text'
                  }`}
                >
                  {v.name}
                </p>
                <p className="text-[10px] text-text-dim font-mono">
                  {v.id} · {v.timezone}
                </p>
              </div>
            </button>
          ))}
        </div>

        <p className="text-[10px] text-text-dim italic">
          Cross-tenant access returns 404 (not 403) from the API.
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="glass p-6 space-y-3"
      >
        <div className="flex items-center gap-2">
          <Database className="w-4 h-4 text-text-muted" />
          <h2 className="text-sm font-semibold text-text">Demo data</h2>
        </div>
        <p className="text-xs text-text-muted">
          Calls <code className="font-mono text-[11px]">POST /v1/admin/seed</code> (owner/admin).
          Idempotent re-seed of mock vendors, users, memberships, and revenue.
        </p>
        <button
          type="button"
          onClick={() => void handleReseed()}
          disabled={!backendOnline || reseeding || !['owner', 'admin'].includes(operator.role)}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 text-xs font-semibold text-text hover:bg-white/10 disabled:opacity-40"
        >
          {reseeding ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Database className="w-3.5 h-3.5" />
          )}
          Reseed demo data
        </button>
        {reseedMsg && <p className="text-[11px] text-text-muted">{reseedMsg}</p>}
      </motion.div>
    </div>
  )
}
