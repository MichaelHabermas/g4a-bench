import { Link, Route, Routes } from 'react-router-dom';
import { RunPickerPage } from './pages/RunPickerPage';
import { RunLayout } from './pages/RunLayout';
import { ScorecardPage } from './pages/ScorecardPage';
import { ComparePage } from './pages/ComparePage';
import { WorkbenchPage } from './pages/WorkbenchPage';
import { ChatFab } from './components/ChatFab';

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-stone-200 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <Link to="/" className="text-xl font-bold tracking-tight text-stone-900">
            Yardstick
          </Link>
          <p className="text-sm text-stone-500">Adversarial G4A measurement</p>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Routes>
          <Route path="/" element={<RunPickerPage />} />
          <Route path="/run/:cohort/:week/:runId" element={<RunLayout />}>
            <Route index element={<ScorecardPage />} />
            <Route path="scorecard" element={<ScorecardPage />} />
            <Route path="compare" element={<ComparePage />} />
            <Route path="workbench" element={<WorkbenchPage />} />
          </Route>
        </Routes>
      </main>
      <ChatFab />
    </div>
  );
}
