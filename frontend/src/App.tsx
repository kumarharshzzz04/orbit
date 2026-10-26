// ORBIT Frontend - Main App Component
// Routing and layout composition

import { Routes, Route, Navigate } from 'react-router-dom';
import { AppShell } from '@/components/layout/AppShell';
import { Overview } from '@/pages/Overview';
import { Missions } from '@/pages/Missions';
import { MissionDetail } from '@/pages/MissionDetail';
import { Hypotheses } from '@/pages/Hypotheses';
import { Experiments } from '@/pages/Experiments';
import { ExperimentDetail } from '@/pages/ExperimentDetail';
import { Registry } from '@/pages/Registry';
import { Live } from '@/pages/Live';
import { Research } from '@/pages/Research';
import { SettingsPage } from '@/pages/Settings';

export function App() {
  return (
    <Routes>
      <Route path="/" element={<AppShell />}>
        <Route index element={<Overview />} />
        <Route path="missions" element={<Missions />} />
        <Route path="missions/new" element={<Missions />} />
        <Route path="missions/:missionId" element={<MissionDetail />} />
        <Route path="missions/:missionId/edit" element={<Missions />} />
        <Route path="hypotheses" element={<Hypotheses />} />
        <Route path="hypotheses/new" element={<Hypotheses />} />
        <Route path="hypotheses/:hypothesisId" element={<div>Hypothesis Detail - TODO</div>} />
        <Route path="hypotheses/:hypothesisId/edit" element={<div>Edit Hypothesis - TODO</div>} />
        <Route path="experiments" element={<Experiments />} />
        <Route path="experiments/new" element={<Experiments />} />
        <Route path="experiments/:experimentId" element={<ExperimentDetail />} />
        <Route path="experiments/:experimentId/promote" element={<ExperimentDetail />} />
        <Route path="registry" element={<Registry />} />
        <Route path="live" element={<Live />} />
        <Route path="research" element={<Research />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      {/* Redirect any unmatched routes to overview */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}