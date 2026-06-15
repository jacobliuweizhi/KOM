import { ClipboardCheck, Download, FileJson, RotateCcw, ScrollText } from 'lucide-react';
import type { DemoCase } from '../data/demoCases';
import { caseDisplayId } from '../engine/privacyEngine';
import { komSystemContent } from '../data/komContent';

export default function Header({ selectedCase, pageLabel, openEvidence, openAudit, exportCaseJSON, exportTrialCSV, exportReviewerSummary, exportAuditJSON, resetDemo }: {
  selectedCase: DemoCase;
  pageLabel: string;
  openEvidence: () => void;
  openAudit: () => void;
  exportCaseJSON: () => void;
  exportTrialCSV: () => void;
  exportReviewerSummary: () => void;
  exportAuditJSON: () => void;
  resetDemo: () => void;
}) {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-4 px-5 py-3">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-md bg-ink text-sm font-black text-white">KOM</div>
          <div>
            <h1 className="text-base font-black text-ink">{komSystemContent.name}</h1>
            <p className="text-xs text-muted">{komSystemContent.studyType}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700">Case: {caseDisplayId(selectedCase)}</span>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700">Module: {pageLabel}</span>
          <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-teal">{komSystemContent.dataStatus}</span>
          <button className="focus-ring inline-flex items-center gap-1 rounded-md border border-slate-300 px-3 py-2 text-xs font-bold text-ink" onClick={openEvidence}><ClipboardCheck size={15} /> Evidence</button>
          <button className="focus-ring inline-flex items-center gap-1 rounded-md border border-slate-300 px-3 py-2 text-xs font-bold text-ink" onClick={openAudit}><ScrollText size={15} /> Audit</button>
          <button className="focus-ring inline-flex items-center gap-1 rounded-md border border-slate-300 px-3 py-2 text-xs font-bold text-ink" onClick={exportCaseJSON}><FileJson size={15} /> Case JSON</button>
          <button className="focus-ring inline-flex items-center gap-1 rounded-md border border-slate-300 px-3 py-2 text-xs font-bold text-ink" onClick={exportTrialCSV}><Download size={15} /> Trial CSV</button>
          <button className="focus-ring inline-flex items-center gap-1 rounded-md border border-slate-300 px-3 py-2 text-xs font-bold text-ink" onClick={exportReviewerSummary}><Download size={15} /> Summary</button>
          <button className="focus-ring inline-flex items-center gap-1 rounded-md border border-slate-300 px-3 py-2 text-xs font-bold text-ink" onClick={exportAuditJSON}><Download size={15} /> Audit JSON</button>
          <button className="focus-ring inline-flex items-center gap-2 rounded-md border border-slate-300 px-3 py-2 text-xs font-bold text-ink" onClick={resetDemo}>
            <RotateCcw size={16} /> Reset
          </button>
        </div>
      </div>
    </header>
  );
}
