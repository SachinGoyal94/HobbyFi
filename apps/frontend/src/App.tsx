import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import CopilotPage from './pages/CopilotPage'
import ProposalsPage from './pages/ProposalsPage'
import AuditPage from './pages/AuditPage'
import SettingsPage from './pages/SettingsPage'
import { useStore } from './store/useStore'
import { X } from 'lucide-react'

export default function App() {
  const {
    backendOnline,
    backendStatus,
    checkBackend,
    lastError,
    clearError,
    verifiedContext,
  } = useStore()

  useEffect(() => {
    checkBackend()
    const interval = setInterval(checkBackend, 30_000)
    return () => clearInterval(interval)
  }, [checkBackend])

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <main className="flex-1 ml-[260px] min-h-screen">
        <header className="h-16 border-b border-line bg-bg/60 backdrop-blur-md flex items-center justify-between px-8 sticky top-0 z-10">
          <div className="flex items-center gap-3 text-xs font-mono text-text-dim">
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                backendOnline ? 'bg-accent-green animate-pulse-slow' : 'bg-accent-amber animate-pulse-slow'
              }`}
            />
            <span>
              {backendOnline
                ? `API LIVE — ${backendStatus?.app || 'Backend'} v${backendStatus?.version || '?'}`
                : 'API OFFLINE'}
            </span>
            {verifiedContext && (
              <span className="hidden sm:inline text-text-muted">
                · {verifiedContext.vendor_name || verifiedContext.vendor_id}
                {' / '}
                <span className="text-accent-cyan">{verifiedContext.role}</span>
              </span>
            )}
          </div>

          {backendOnline && backendStatus && (
            <div className="flex items-center gap-3 text-[10px] font-mono text-text-dim">
              <span>
                Model:{' '}
                <span className="text-accent-cyan">{backendStatus.gemini_model}</span>
              </span>
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  backendStatus.gemini_configured ? 'bg-accent-green' : 'bg-accent-red'
                }`}
                title={
                  backendStatus.gemini_configured
                    ? 'Gemini API key configured'
                    : 'GEMINI_API_KEY missing'
                }
              />
              <span>{backendStatus.database}</span>
              <span className="text-text-dim/70">{backendStatus.env}</span>
            </div>
          )}
        </header>

        {lastError && (
          <div className="mx-8 mt-4 px-4 py-3 rounded-xl border border-accent-red/30 bg-accent-red/10 flex items-start gap-3">
            <p className="flex-1 text-xs text-accent-red font-medium">{lastError}</p>
            <button
              type="button"
              onClick={clearError}
              className="text-accent-red/70 hover:text-accent-red"
              aria-label="Dismiss error"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

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
