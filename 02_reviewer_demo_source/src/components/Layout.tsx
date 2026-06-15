import { useState, type ReactNode } from 'react';
import Header from './Header';
import Sidebar, { type PageKey } from './Sidebar';
import type { DemoCase } from '../data/demoCases';
import EvidenceDrawer from './EvidenceDrawer';
import AuditDrawer from './AuditDrawer';
import { komCases } from '../data/komCases';
import { exportContentAuditJSON, exportCurrentCaseJSON, exportReviewerSummaryMarkdown, exportTrialWideCSV } from '../utils/exportKOM';

const mobilePages: { key: PageKey; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'workspace', label: 'Case workspace' },
  { key: 'assess', label: 'KOM-Assess' },
  { key: 'treat', label: 'KOM-Treat' },
  { key: 'sim', label: 'KOM-Sim' },
  { key: 'score', label: 'KOM-Score' },
  { key: 'results', label: 'Results' },
  { key: 'methods', label: 'Methods' },
  { key: 'glossary', label: 'Glossary' }
];

export default function Layout({ children, page, setPage, selectedCase, resetDemo }: {
  children: ReactNode;
  page: PageKey;
  setPage: (p: PageKey) => void;
  selectedCase: DemoCase;
  resetDemo: () => void;
}) {
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [auditOpen, setAuditOpen] = useState(false);
  const pageLabel = mobilePages.find((item) => item.key === page)?.label || page;

  return (
    <div className="min-h-screen bg-paper">
      <Header
        selectedCase={selectedCase}
        pageLabel={pageLabel}
        openEvidence={() => setEvidenceOpen(true)}
        openAudit={() => setAuditOpen(true)}
        exportCaseJSON={() => exportCurrentCaseJSON(selectedCase)}
        exportTrialCSV={() => exportTrialWideCSV(komCases)}
        exportReviewerSummary={() => exportReviewerSummaryMarkdown(selectedCase)}
        exportAuditJSON={exportContentAuditJSON}
        resetDemo={resetDemo}
      />
      <div className="border-b border-slate-200 bg-white p-3 lg:hidden">
        <label className="text-xs font-bold uppercase tracking-wide text-clinical" htmlFor="mobile-page-nav">Page</label>
        <select
          id="mobile-page-nav"
          className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-bold text-ink focus-ring"
          value={page}
          onChange={(event) => setPage(event.target.value as PageKey)}
        >
          {mobilePages.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
        </select>
      </div>
      <div className="mx-auto flex max-w-[1600px]">
        <Sidebar page={page} setPage={setPage} />
        <main className="min-w-0 flex-1 p-5 lg:p-8">
          {children}
        </main>
      </div>
      <EvidenceDrawer open={evidenceOpen} onClose={() => setEvidenceOpen(false)} />
      <AuditDrawer open={auditOpen} onClose={() => setAuditOpen(false)} />
    </div>
  );
}
