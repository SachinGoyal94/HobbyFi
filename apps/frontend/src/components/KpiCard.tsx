import { motion } from 'framer-motion'
import type { LucideIcon } from 'lucide-react'

interface KpiCardProps {
  icon: LucideIcon
  label: string
  value: string
  accent: string       // Tailwind color class e.g. 'accent-cyan'
  subtitle?: string
  pulse?: boolean
  delay?: number
}

const accentMap: Record<string, { bg: string; text: string; glow: string }> = {
  'accent-cyan': { bg: 'bg-accent-cyan/10', text: 'text-accent-cyan', glow: 'shadow-glow' },
  'accent-purple': { bg: 'bg-accent-purple/10', text: 'text-accent-purple', glow: 'shadow-glow-purple' },
  'accent-green': { bg: 'bg-accent-green/10', text: 'text-accent-green', glow: '' },
  'accent-amber': { bg: 'bg-accent-amber/10', text: 'text-accent-amber', glow: 'shadow-glow-amber' },
  'accent-red': { bg: 'bg-accent-red/10', text: 'text-accent-red', glow: '' },
}

export default function KpiCard({ icon: Icon, label, value, accent, subtitle, pulse, delay = 0 }: KpiCardProps) {
  const colors = accentMap[accent] || accentMap['accent-cyan']

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: delay * 0.1 }}
      className="glass glass-hover p-5 flex flex-col gap-3 relative overflow-hidden group"
    >
      {/* Ambient corner glow */}
      <div className={`absolute -top-8 -right-8 w-24 h-24 rounded-full ${colors.bg} blur-2xl opacity-50 group-hover:opacity-80 transition-opacity`} />

      <div className="flex items-center justify-between relative">
        <div className={`w-10 h-10 rounded-xl ${colors.bg} flex items-center justify-center`}>
          <Icon className={`w-5 h-5 ${colors.text}`} />
        </div>
        {pulse && (
          <span className={`w-2 h-2 rounded-full ${colors.text.replace('text-', 'bg-')} animate-pulse-slow`} />
        )}
      </div>

      <div className="relative">
        <p className="text-2xl font-bold text-text tracking-tight">{value}</p>
        <p className="text-xs text-text-muted mt-0.5">{label}</p>
        {subtitle && (
          <p className={`text-[10px] mt-1 font-medium ${colors.text}`}>{subtitle}</p>
        )}
      </div>
    </motion.div>
  )
}
