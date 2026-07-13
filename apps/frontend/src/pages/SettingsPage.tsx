import { motion } from 'framer-motion'
import { useStore } from '../store/useStore'
import { vendors, type Role } from '../data/mockData'
import { Settings, Shield, Building2, UserCircle, Info, Wifi, WifiOff, RefreshCw } from 'lucide-react'

const roles: { role: Role; desc: string }[] = [
  { role: 'owner', desc: 'Full access — read, write, approve, admin' },
  { role: 'admin', desc: 'Read, write, approve — no billing' },
  { role: 'support', desc: 'Read, write, approve — limited scope' },
  { role: 'viewer', desc: 'Read-only — cannot propose or approve' },
]

export default function SettingsPage() {
  const { vendor, operator, setRole, setVendor, backendOnline, backendStatus, checkBackend } = useStore()

  return (
    <div className="space-y-8 animate-fade-in max-w-2xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-text flex items-center gap-2">
          <Settings className="w-6 h-6 text-text-muted" />
          Sandbox Settings
        </h1>
        <p className="text-sm text-text-muted mt-1">
          Switch roles and tenants to test the RBAC and multi-tenancy security model.
        </p>
      </div>

      {/* Info banner */}
      <div className="glass-sm p-4 flex items-start gap-3 border-l-2 border-l-accent-cyan">
        <Info className="w-4 h-4 text-accent-cyan flex-shrink-0 mt-0.5" />
        <div className="text-xs text-text-muted space-y-1">
          <p>This is a <strong className="text-text">simulation playground</strong>. Changing roles and tenants affects RBAC gates on proposals and copilot write actions.</p>
          <p>In production (Phase 4), auth context comes from JWT/SSO — not header stubs.</p>
        </div>
      </div>

      {/* Backend Connection */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className={`glass p-6 space-y-4 border-l-2 ${
          backendOnline ? 'border-l-accent-green' : 'border-l-accent-amber'
        }`}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {backendOnline
              ? <Wifi className="w-4 h-4 text-accent-green" />
              : <WifiOff className="w-4 h-4 text-accent-amber" />
            }
            <h2 className="text-sm font-semibold text-text">Backend Connection</h2>
          </div>
          <button
            onClick={() => checkBackend()}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg glass-sm text-xs font-medium text-text-muted hover:text-text transition-all"
          >
            <RefreshCw className="w-3 h-3" />
            Reconnect
          </button>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="glass-sm p-3">
            <p className="text-[9px] font-mono uppercase tracking-wider text-text-dim">Status</p>
            <p className={`text-sm font-bold mt-0.5 ${
              backendOnline ? 'text-accent-green' : 'text-accent-amber'
            }`}>
              {backendOnline ? 'Connected' : 'Offline'}
            </p>
          </div>
          <div className="glass-sm p-3">
            <p className="text-[9px] font-mono uppercase tracking-wider text-text-dim">Mode</p>
            <p className="text-sm font-bold mt-0.5 text-text">
              Strict API
            </p>
          </div>
          {backendStatus && (
            <>
              <div className="glass-sm p-3">
                <p className="text-[9px] font-mono uppercase tracking-wider text-text-dim">AI Model</p>
                <p className="text-xs font-mono mt-0.5 text-accent-cyan">{backendStatus.gemini_model}</p>
              </div>
              <div className="glass-sm p-3">
                <p className="text-[9px] font-mono uppercase tracking-wider text-text-dim">Database</p>
                <p className="text-xs font-mono mt-0.5 text-text-muted">{backendStatus.database}</p>
              </div>
            </>
          )}
        </div>

        {!backendOnline && (
          <p className="text-[10px] text-accent-amber">
            Backend is unreachable at localhost:8000. Start it with: <code className="font-mono bg-accent-amber/10 px-1 py-0.5 rounded">uvicorn app.main:app --reload</code>
          </p>
        )}
      </motion.div>

      {/* Role Selector */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass p-6 space-y-4"
      >
        <div className="flex items-center gap-2">
          <Shield className="w-4 h-4 text-accent-purple" />
          <h2 className="text-sm font-semibold text-text">Active Role</h2>
        </div>

        <div className="grid grid-cols-2 gap-2">
          {roles.map(({ role, desc }) => (
            <button
              key={role}
              onClick={() => setRole(role)}
              className={`
                p-3 rounded-xl text-left transition-all border
                ${operator.role === role
                  ? 'bg-accent-cyan/10 border-accent-cyan/30 shadow-glow'
                  : 'bg-white/[0.02] border-line hover:border-line-strong hover:bg-white/[0.04]'
                }
              `}
            >
              <p className={`text-xs font-bold uppercase tracking-wider ${operator.role === role ? 'text-accent-cyan' : 'text-text'}`}>
                {role}
              </p>
              <p className="text-[10px] text-text-dim mt-0.5">{desc}</p>
            </button>
          ))}
        </div>

        <div className="glass-sm p-3 flex items-center gap-2 text-xs">
          <UserCircle className="w-4 h-4 text-text-dim" />
          <span className="text-text-muted">
            Logged in as <span className="font-mono text-accent-cyan">{operator.id}</span> ({operator.email})
          </span>
        </div>
      </motion.div>

      {/* Vendor/Tenant Selector */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="glass p-6 space-y-4"
      >
        <div className="flex items-center gap-2">
          <Building2 className="w-4 h-4 text-accent-amber" />
          <h2 className="text-sm font-semibold text-text">Active Tenant</h2>
        </div>

        <div className="space-y-2">
          {vendors.map(v => (
            <button
              key={v.id}
              onClick={() => setVendor(v.id)}
              className={`
                w-full p-3 rounded-xl text-left transition-all border flex items-center gap-3
                ${vendor.id === v.id
                  ? 'bg-accent-amber/10 border-accent-amber/30 shadow-glow-amber'
                  : 'bg-white/[0.02] border-line hover:border-line-strong hover:bg-white/[0.04]'
                }
              `}
            >
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold ${
                vendor.id === v.id ? 'bg-accent-amber/20 text-accent-amber' : 'bg-white/5 text-text-dim'
              }`}>
                {v.name.charAt(0)}
              </div>
              <div>
                <p className={`text-xs font-semibold ${vendor.id === v.id ? 'text-accent-amber' : 'text-text'}`}>
                  {v.name}
                </p>
                <p className="text-[10px] text-text-dim font-mono">{v.id} · {v.timezone}</p>
              </div>
            </button>
          ))}
        </div>

        <p className="text-[10px] text-text-dim italic">
          Switching tenants changes the data scope. Cross-vendor queries return 404 (not 403).
        </p>
      </motion.div>
    </div>
  )
}
