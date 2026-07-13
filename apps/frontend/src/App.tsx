import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import CopilotPage from './pages/CopilotPage'
import ProposalsPage from './pages/ProposalsPage'
import AuditPage from './pages/AuditPage'
import SettingsPage from './pages/SettingsPage'
import { useStore } from './store/useStore'

export default function App() {
  const { backendOnline, backendStatus, checkBackend } = useStore()

  // Check backend on mount + periodically
  useEffect(() => {
    checkBackend()
    const interval = setInterval(checkBackend, 30_000) // re-check every 30s
    return () => clearInterval(interval)
  }, [checkBackend])

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <Sidebar />

      {/* Main content area */}
      <main className="flex-1 ml-[260px] min-h-screen">
        {/* Top bar */}
        <header className="h-16 border-b border-line bg-bg/60 backdrop-blur-md flex items-center justify-between px-8 sticky top-0 z-10">
          <div className="flex items-center gap-2 text-xs font-mono text-text-dim">
            <span className={`w-1.5 h-1.5 rounded-full ${
              backendOnline ? 'bg-accent-green animate-pulse-slow' : 'bg-accent-amber animate-pulse-slow'
            }`} />
            <span>
              {backendOnline
                ? `LIVE — ${backendStatus?.app || 'Backend'} v${backendStatus?.version || '?'}`
                : 'BACKEND OFFLINE'
              }
            </span>
          </div>

          {backendOnline && backendStatus && (
            <div className="flex items-center gap-3 text-[10px] font-mono text-text-dim">
              <span>Model: <span className="text-accent-cyan">{backendStatus.gemini_model}</span></span>
              <span className={`w-1.5 h-1.5 rounded-full ${backendStatus.gemini_configured ? 'bg-accent-green' : 'bg-accent-red'}`} />
              <span>{backendStatus.database}</span>
            </div>
          )}
        </header>

        {/* Page content */}
        <div className="p-8">
          <Routes>
            <Route path="/" element={<Navigate to="/copilot" replace />} />
            <Route path="/copilot" element={<CopilotPage />} />
            <Route path="/proposals" element={<ProposalsPage />} />
            <Route path="/audit" element={<AuditPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </main>
    </div>
  )
}