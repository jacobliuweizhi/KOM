import { useEffect, useMemo, useState } from 'react';
import Layout from './components/Layout';
import type { PageKey } from './components/Sidebar';
import { demoCases } from './data/demoCases';
import OverviewPage from './pages/OverviewPage';
import CaseWorkspacePage from './pages/CaseWorkspacePage';
import AssessPage from './pages/AssessPage';
import TreatPage from './pages/TreatPage';
import SimPage from './pages/SimPage';
import ScorePage from './pages/ScorePage';
import ResultsPage from './pages/ResultsPage';
import MethodsPage from './pages/MethodsPage';
import GlossaryPage from './pages/GlossaryPage';

const pageFromHash = (): PageKey => {
  const key = window.location.hash.replace('#', '') as PageKey;
  return ['overview', 'workspace', 'assess', 'treat', 'sim', 'score', 'results', 'methods', 'glossary'].includes(key) ? key : 'overview';
};

export default function App() {
  const [page, setPageState] = useState<PageKey>(pageFromHash);
  const [selectedId, setSelectedId] = useState(() => localStorage.getItem('kom_selected_case') || demoCases[0].id);
  const [workflowRun, setWorkflowRun] = useState(() => localStorage.getItem('kom_workflow_run') === 'true');
  const [reviewerMode, setReviewerMode] = useState(() => localStorage.getItem('kom_reviewer_mode') === 'true');
  const selectedCase = useMemo(() => demoCases.find(c => c.id === selectedId) || demoCases[0], [selectedId]);
  useEffect(() => { localStorage.setItem('kom_selected_case', selectedId); }, [selectedId]);
  useEffect(() => { localStorage.setItem('kom_workflow_run', String(workflowRun)); }, [workflowRun]);
  useEffect(() => { localStorage.setItem('kom_reviewer_mode', String(reviewerMode)); }, [reviewerMode]);
  const setPage = (p: PageKey) => {
    window.location.hash = p;
    setPageState(p);
  };
  const resetDemo = () => {
    localStorage.clear();
    setSelectedId(demoCases[0].id);
    setWorkflowRun(false);
    setReviewerMode(false);
    setPage('overview');
  };
  const onSelectCase = (id: string) => {
    setSelectedId(id);
    setWorkflowRun(false);
  };
  return (
    <Layout page={page} setPage={setPage} selectedCase={selectedCase} resetDemo={resetDemo}>
      {page === 'overview' && <OverviewPage />}
      {page === 'workspace' && <CaseWorkspacePage cases={demoCases} selectedCase={selectedCase} onSelectCase={onSelectCase} workflowRun={workflowRun} runWorkflow={() => setWorkflowRun(true)} reviewerMode={reviewerMode} />}
      {page === 'assess' && <AssessPage selectedCase={selectedCase} />}
      {page === 'treat' && <TreatPage selectedCase={selectedCase} />}
      {page === 'sim' && <SimPage selectedCase={selectedCase} />}
      {page === 'score' && <ScorePage />}
      {page === 'results' && <ResultsPage />}
      {page === 'methods' && <MethodsPage />}
      {page === 'glossary' && <GlossaryPage />}
    </Layout>
  );
}
