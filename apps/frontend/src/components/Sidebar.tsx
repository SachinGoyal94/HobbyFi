import { motion } from 'framer-motion'
import { useNavigate, useLocation } from 'react-router-dom'
import { useStore } from '../store/useStore'
import {
  Bot, FileCheck2, ScrollText,
  Settings, Zap,
} from 'lucide-react'

const navItems = [
  { id: 'copilot', label: 'AI Copilot', icon: Bot, path: '/copilot' },
  { id: 'proposals', label: 'Proposals', icon: FileCheck2, path: '/proposals' },
  { id: 'audit', label: 'Audit Log', icon: ScrollText, path: '/audit' },
  { id: 'settings', label: 'Settings', icon: Settings, path: '/settings' },
] as const

const roleColors: Record<string, string> = {
  owner: 'bg-accent-cyan/20 text-accent-cyan',
  admin: 'bg-accent-purple/20 text-accent-purple',
  support: 'bg-accent-amber/20 text-accent-amber',
  viewer: 'bg-accent-green/20 text-accent-green',
}

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { vendor, operator, proposals } = useStore()
  const pendingCount = proposals.filter(p => p.status === 'pending' && p.vendorId === vendor.id).length

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-[260px] z-20 flex flex-col border-r border-line bg-[#060a13]/90 backdrop-blur-xl">
      {/* Logo */}
      <div className="h-16 flex items-center gap-3 px-6 border-b border-line">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent-cyan to-accent-purple flex items-center justify-center">
          <Zap className="w-4 h-4 text-white" />
        </div>
        <span className="text-lg font-bold tracking-tight text-text">HobbyFi</span>
        <span className="text-[10px] font-mono font-medium text-accent-cyan bg-accent-cyan/10 px-1.5 py-0.5 rounded-md ml-auto">v1</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-3 space-y-0.5 overflow-y-auto">
        {navItems.map(item => {
          const isActive = location.pathname === item.path
          const Icon = item.icon

          return (
            <motion.button
              key={item.id}
              onClick={() => navigate(item.path)}
              whileTap={{ scale: 0.98 }}
              className={`
                w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium
                transition-all duration-150 group relative
                ${isActive
                  ? 'bg-accent-cyan/10 text-accent-cyan'
                  : 'text-text-muted hover:text-text hover:bg-white/[0.03]'
                }
              `}
            >
              {/* Active indicator bar */}
              {isActive && (
                <motion.div
                  layoutId="sidebar-active"
                  className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-accent-cyan"
                  transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                />
              )}

              <Icon className={`w-[18px] h-[18px] ${isActive ? 'text-accent-cyan' : 'text-text-dim group-hover:text-text-muted'}`} />
              <span>{item.label}</span>

              {/* Pending proposals badge */}
              {item.id === 'proposals' && pendingCount > 0 && (
                <span className="ml-auto text-[10px] font-bold bg-accent-amber text-black w-5 h-5 rounded-full flex items-center justify-center animate-pulse-slow">
                  {pendingCount}
                </span>
              )}
            </motion.button>
          )
        })}
      </nav>

      {/* Bottom: Vendor + Operator Info */}
      <div className="border-t border-line p-4 space-y-3">
        {/* Vendor Selector */}
        <div className="glass-sm p-2.5 space-y-1">
          <p className="text-[10px] font-mono uppercase tracking-wider text-text-dim">Tenant</p>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-accent-purple/20 flex items-center justify-center text-accent-purple text-[10px] font-bold">
              {vendor.name.charAt(0)}
            </div>
            <span className="text-xs font-semibold text-text truncate flex-1">{vendor.name}</span>
          </div>
        </div>

        {/* Operator */}
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-accent-cyan/30 to-accent-purple/30 flex items-center justify-center text-sm font-bold text-text">
            {operator.displayName.charAt(0)}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-text truncate">{operator.displayName}</p>
            <span className={`inline-block text-[9px] font-bold uppercase px-1.5 py-0.5 rounded-md mt-0.5 ${roleColors[operator.role]}`}>
              {operator.role}
            </span>
          </div>
        </div>
      </div>
    </aside>
  )
}
