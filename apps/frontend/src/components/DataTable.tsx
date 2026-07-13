import { motion } from 'framer-motion'

interface DataTableProps {
  title?: string
  columns: string[]
  rows: (string | number)[][]
  compact?: boolean
}

export default function DataTable({ title, columns, rows, compact = false }: DataTableProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="glass-sm overflow-hidden"
    >
      {title && (
        <div className="px-4 py-2.5 border-b border-line">
          <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider">{title}</h4>
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-line">
              {columns.map((col, i) => (
                <th
                  key={i}
                  className={`text-left text-[10px] font-semibold uppercase tracking-wider text-text-dim
                    ${compact ? 'px-3 py-2' : 'px-4 py-3'}
                  `}
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => (
              <tr
                key={ri}
                className="border-b border-line/50 last:border-0 hover:bg-white/[0.02] transition-colors"
              >
                {row.map((cell, ci) => (
                  <td
                    key={ci}
                    className={`text-xs text-text font-medium
                      ${compact ? 'px-3 py-2' : 'px-4 py-3'}
                      ${ci === 0 ? 'font-mono text-accent-cyan' : ''}
                    `}
                  >
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </motion.div>
  )
}
