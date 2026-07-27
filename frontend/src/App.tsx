import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { LibraryPage } from './pages/LibraryPage'
import { ActivityDetailPage } from './pages/ActivityDetailPage'
import { AnalyzePage } from './pages/AnalyzePage'
import { MemoryPage } from './pages/MemoryPage'
import { IngestPage } from './pages/IngestPage'

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<LibraryPage />} />
        <Route path="/activities/:id" element={<ActivityDetailPage />} />
        <Route path="/analyze" element={<AnalyzePage />} />
        <Route path="/memory" element={<MemoryPage />} />
        <Route path="/ingest" element={<IngestPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  )
}
