import EvidenceCard from '../components/EvidenceCard';
import PrescriptionPanel from '../components/PrescriptionPanel';
import SafetyAlert from '../components/SafetyAlert';
import TermTooltip from '../components/TermTooltip';
import type { DemoCase } from '../data/demoCases';
import { buildMdtAdvice } from '../engine/mdtEngine';
import { retrievalSummary } from '../engine/ragEngine';
import { safetyAudit } from '../engine/safetyEngine';

export default function TreatPage({ selectedCase }: { selectedCase: DemoCase }) {
  const retrieval = retrievalSummary(selectedCase);
  const mdt = buildMdtAdvice(selectedCase);
  const safe = safetyAudit(selectedCase);
  return (
    <div className="space-y-6">
      <section>
        <p className="section-title">KOM-Treat</p>
        <h2 className="mt-2 text-3xl font-black text-ink"><TermTooltip termKey="KOM-Treat" />: guideline-first evidence routing and multidisciplinary prescription support</h2>
      </section>
      <section className="grid gap-4 lg:grid-cols-[0.95fr_1.05fr]">
        <div className="panel p-5">
          <p className="section-title">KOM-KB and retrieval comparison</p>
          <h3 className="mt-2 text-xl font-black text-ink"><TermTooltip termKey="KOM-RAG" /> versus <TermTooltip termKey="naive RAG baseline" /></h3>
          <p className="mt-3 small-note">The same local evidence library and case query are used. KOM-RAG ranks evidence with guideline anchors, evidence hierarchy, specialty routing, safety labels, graph links, and arbitration; the naive baseline uses only single-stage vector-like top-k retrieval.</p>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <div className="rounded-md bg-slate-50 p-3"><b>Precision@10</b><p className="text-sm text-muted">0.676 vs 0.303</p></div>
            <div className="rounded-md bg-slate-50 p-3"><b>MRR</b><p className="text-sm text-muted">0.748 vs 0.159</p></div>
            <div className="rounded-md bg-slate-50 p-3"><b>nDCG@10</b><p className="text-sm text-muted">0.690 vs 0.237</p></div>
          </div>
        </div>
        <div className="panel p-5">
          <p className="section-title">What is the naive RAG baseline?</p>
          <p className="mt-3 small-note">The naive RAG baseline uses the same evidence library and query but retrieves the top-k evidence units by vector similarity only. It does not use guideline anchors, evidence hierarchy, specialty routing, safety labels, graph links, or evidence arbitration.</p>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <div><b className="text-ink">KOM-RAG IDs</b><p className="mt-1 text-xs text-muted">{retrieval.topEvidence.slice(0, 5).map(e => e.id).join(', ')}</p></div>
            <div><b className="text-ink">Naive baseline IDs</b><p className="mt-1 text-xs text-muted">{retrieval.naiveEvidence.slice(0, 5).map(e => e.id).join(', ')}</p></div>
          </div>
        </div>
      </section>
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {retrieval.topEvidence.slice(0, 8).map((item) => <EvidenceCard item={item} key={item.id} />)}
      </section>
      <section className="panel p-5">
        <p className="section-title">KOM-MDT</p>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          {mdt.map((a) => <div className="rounded-lg border border-slate-200 bg-slate-50 p-4" key={a.agent}><h3 className="font-black text-ink">{a.agent}</h3><p className="mt-1 text-xs font-bold text-clinical">{a.focus}</p><p className="mt-3 text-sm leading-6 text-muted">{a.advice}</p></div>)}
        </div>
      </section>
      <PrescriptionPanel selectedCase={selectedCase} />
      <SafetyAlert status={safe.status} alerts={safe.alerts} />
    </div>
  );
}
