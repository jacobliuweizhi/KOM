import CaseSelector from '../components/CaseSelector';
import EvidenceCard from '../components/EvidenceCard';
import ExportPanel from '../components/ExportPanel';
import PrescriptionPanel from '../components/PrescriptionPanel';
import SafetyAlert from '../components/SafetyAlert';
import TermTooltip from '../components/TermTooltip';
import type { DemoCase } from '../data/demoCases';
import { structuredProfile } from '../engine/profileEngine';
import { retrievalSummary } from '../engine/ragEngine';
import { buildMdtAdvice } from '../engine/mdtEngine';
import { safetyAudit } from '../engine/safetyEngine';
import { caseDisplayId, deidentificationNote } from '../engine/privacyEngine';

export default function CaseWorkspacePage({ cases, selectedCase, onSelectCase, workflowRun, runWorkflow, reviewerMode }: {
  cases: DemoCase[];
  selectedCase: DemoCase;
  onSelectCase: (id: string) => void;
  workflowRun: boolean;
  runWorkflow: () => void;
  reviewerMode: boolean;
}) {
  const profile = structuredProfile(selectedCase);
  const retrieval = retrievalSummary(selectedCase);
  const mdt = buildMdtAdvice(selectedCase);
  const safe = safetyAudit(selectedCase);
  const steps = ['Case input', 'KOM-Profile', 'KOM-Rad', 'KOM-Risk', 'KOM-RAG', 'KOM-MDT', 'KOM-Rx', 'KOM-Safe'];
  return (
    <div className="space-y-6">
      <section>
        <p className="section-title">Select standardized case</p>
        <h2 className="mt-2 text-3xl font-black text-ink">Case workspace</h2>
        <div className="mt-4"><CaseSelector cases={cases} selectedId={selectedCase.id} onSelect={onSelectCase} /></div>
      </section>
      <section className="panel p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="section-title">Full workflow</p>
            <h3 className="mt-2 text-xl font-black text-ink">{caseDisplayId(selectedCase)}: {profile.severityLabel}</h3>
            <p className="mt-1 text-xs text-muted">{deidentificationNote}</p>
          </div>
          <button data-testid="run-workflow" className="focus-ring rounded-md bg-ink px-5 py-3 font-bold text-white" onClick={runWorkflow}>Run full KOM workflow</button>
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-4 xl:grid-cols-8">
          {steps.map((s, idx) => (
            <div key={s} className={`rounded-md border p-3 ${workflowRun ? 'border-emerald-200 bg-emerald-50' : 'border-slate-200 bg-slate-50'}`}>
              <div className="text-xs font-black text-clinical">0{idx + 1}</div>
              <div className="mt-1 font-bold text-ink">{s.startsWith('KOM') ? <TermTooltip termKey={s} /> : s}</div>
              <div className="mt-1 text-xs text-muted">{workflowRun ? 'Completed' : 'Ready'}</div>
            </div>
          ))}
        </div>
      </section>
      {(workflowRun || reviewerMode) && (
        <>
          <section className="grid gap-5 xl:grid-cols-2">
            <div className="panel p-5">
              <p className="section-title">KOM-Assess</p>
              <h3 className="mt-2 text-xl font-black text-ink">Structured patient portrait</h3>
              <div className="mt-4 divide-y divide-slate-100">
                {profile.profileRows.map(([k, v]) => <div key={k} className="grid grid-cols-[150px_1fr] gap-3 py-2 text-sm"><b>{k}</b><span className="text-muted">{v}</span></div>)}
              </div>
            </div>
            <div className="panel p-5">
              <p className="section-title">KOM-RAG</p>
              <h3 className="mt-2 text-xl font-black text-ink">Evidence retrieval</h3>
              <p className="mt-2 small-note">Query: {retrieval.query}</p>
              <div className="mt-4 grid gap-3">
                {retrieval.topEvidence.slice(0, 3).map((item) => <EvidenceCard item={item} key={item.id} />)}
              </div>
            </div>
          </section>
          <section className="panel p-5">
            <p className="section-title">KOM-MDT</p>
            <h3 className="mt-2 text-xl font-black text-ink">Specialty agent reasoning</h3>
            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              {mdt.map((a) => <div className="rounded-lg border border-slate-200 bg-slate-50 p-4" key={a.agent}><b>{a.agent}</b><p className="mt-2 text-sm leading-6 text-muted">{a.advice}</p><p className="mt-2 text-xs text-clinical">{a.evidenceIds.join(', ')}</p></div>)}
            </div>
          </section>
          <PrescriptionPanel selectedCase={selectedCase} />
          <SafetyAlert status={safe.status} alerts={safe.alerts} />
          <ExportPanel selectedCase={selectedCase} />
        </>
      )}
    </div>
  );
}
