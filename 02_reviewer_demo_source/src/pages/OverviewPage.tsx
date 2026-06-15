import MetricCard from '../components/MetricCard';
import ReviewerTour from '../components/ReviewerTour';
import TermTooltip from '../components/TermTooltip';
import { komSystemContent, workflowR0R8 } from '../data/komContent';

export default function OverviewPage() {
  return (
    <div className="space-y-6">
      <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="py-10">
          <p className="section-title">Reviewer-facing clinical research interface</p>
          <h2 className="mt-4 max-w-4xl text-5xl font-black leading-tight text-ink">
            <TermTooltip termKey="KOM" label="KOM" /> precision assessment and management workflow for standardized knee osteoarthritis treatment planning.
          </h2>
          <p className="mt-5 max-w-3xl text-lg leading-8 text-muted">
            {komSystemContent.positioning} The local file shows how standardized KOA case information is converted into <TermTooltip termKey="KOM-Assess" />, evidence-routed <TermTooltip termKey="KOM-Treat" />, <TermTooltip termKey="KOM-Safe" />, <TermTooltip termKey="KOM-Score" />, and <TermTooltip termKey="KOM-Sim" /> outputs for physician-facing validation.
          </p>
          <div className="mt-5 rounded-lg border border-slate-200 bg-white p-4 text-sm leading-7 text-muted">
            <strong className="text-ink">Boundary statement:</strong> {komSystemContent.reviewerDataBoundary}
          </div>
        </div>
        <div className="panel p-5">
          <p className="section-title">Study summary</p>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <MetricCard label="Standardized KOA cases" value="120" />
            <MetricCard label="Clinicians" value="26" />
            <MetricCard label="Tasks per physician" value="30" />
            <MetricCard label="Physician-task prescription records" value="780" />
            <MetricCard label="Evidence units" value="3,266" />
            <MetricCard label="OAK-Net imaging samples" value="8,611" />
            <MetricCard label="KOM-Risk longitudinal samples" value="7,855-9,014" />
          </div>
          <p className="mt-4 rounded-lg border border-amber-100 bg-amber-50 p-3 text-sm font-semibold text-amber-900">
            780 refers to physician-task prescription records, not independent physicians or independent cases.
          </p>
        </div>
      </section>

      <section className="panel p-5">
        <p className="section-title">Manuscript workflow map</p>
        <div className="mt-4 grid gap-3 md:grid-cols-4">
          {workflowR0R8.map(([code, title, detail], idx) => (
            <div key={code} className="relative rounded-lg border border-slate-200 bg-slate-50 p-4">
              <div className="text-xs font-black text-clinical">{code}</div>
              <div className="mt-2 text-base font-black text-ink">{title}</div>
              <p className="mt-2 text-xs leading-5 text-muted">{detail}</p>
              {idx < workflowR0R8.length - 1 ? <div className="absolute right-[-18px] top-1/2 hidden text-2xl font-black text-slate-300 md:block">→</div> : null}
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[
          ['KOM-Assess', 'Physician-side structured patient portrait, imaging support, and longitudinal risk context.'],
          ['KOM-Treat', 'Treatment recommendation generation and component ablation across Full KOM, KOM without RAG, KOM without MDT, and Direct LLM.'],
          ['KOM-Sim', 'Clinician-in-the-loop standardized prescription simulation using 26 physicians and 30 tasks each.'],
          ['KOM-Score', 'Multi-source evaluation, reliability statistics, and safety-critical error definitions.']
        ].map(([title, body]) => (
          <div className="panel p-5" key={title}>
            <h3 className="text-lg font-black text-ink">{title}</h3>
            <p className="mt-3 small-note">{body}</p>
          </div>
        ))}
      </section>
      <ReviewerTour />
    </div>
  );
}
