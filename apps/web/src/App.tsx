import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from './layout/AppShell';
import { HomePage } from './pages/HomePage';
import { WeekHubPage } from './pages/WeekHubPage';
import { RunLayout } from './pages/RunLayout';
import { RunOverviewPage } from './pages/RunOverviewPage';
import { ScorecardPage } from './pages/ScorecardPage';
import { ComparePage } from './pages/ComparePage';
import { WorkbenchPage } from './pages/WorkbenchPage';
import { DecisionTrailPage } from './pages/DecisionTrailPage';
import { RunPlanPage } from './pages/RunPlanPage';
import { ChatFab } from './components/ChatFab';

export default function App() {
  return (
    <>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/cohorts/:cohort/week/:week" element={<WeekHubPage />} />
          <Route path="/run/:cohort/:week/:runId" element={<RunLayout />}>
            <Route index element={<Navigate to="overview" replace />} />
            <Route path="overview" element={<RunOverviewPage />} />
            <Route path="scorecard" element={<ScorecardPage />} />
            <Route path="compare" element={<ComparePage />} />
            <Route path="decisions" element={<DecisionTrailPage />} />
            <Route path="workbench" element={<WorkbenchPage />} />
            <Route path="plan" element={<RunPlanPage />} />
          </Route>
        </Route>
      </Routes>
      <ChatFab />
    </>
  );
}
