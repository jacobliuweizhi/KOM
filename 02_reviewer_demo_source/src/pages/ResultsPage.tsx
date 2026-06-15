import ResultChart from '../components/ResultChart';
import MetricCard from '../components/MetricCard';
import { ablationResults, assessResults, imagingResults, ragResults, reliabilityResults, riskResults, seniorityResults, simResults } from '../data/studyResults';

export default function ResultsPage() {
  return (
    <div className="space-y-6">
      <section>
        <p className="section-title">Paper results dashboard</p>
        <h2 className="mt-2 text-3xl font-black text-ink">Reviewer-facing result summary</h2>
      </section>
      <section className="grid gap-4 md:grid-cols-3">
        {reliabilityResults.map(r => <MetricCard key={r.label} label={r.label} value={r.value} />)}
      </section>
      <section className="grid gap-5 xl:grid-cols-2">
        <div className="panel p-5">
          <h3 className="text-xl font-black text-ink">KOM-Treat ablation</h3>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <MetricCard label="Full KOM overall" value="8.46" />
            <MetricCard label="Full KOM safety" value="9.11" />
          </div>
          <ResultChart data={ablationResults} xKey="condition" bars={[{ key: 'overall', color: '#1f5673', name: 'Overall' }, { key: 'safety', color: '#2f8f83', name: 'Safety' }]} />
        </div>
        <div className="panel p-5">
          <h3 className="text-xl font-black text-ink">KOM-Sim clinician task</h3>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <MetricCard label="Clinician + KOM overall" value="7.34" />
            <MetricCard label="Clinician + KOM rule score" value="63.7" />
          </div>
          <ResultChart data={simResults} xKey="condition" bars={[{ key: 'overall', color: '#1f5673', name: 'Overall' }, { key: 'ruleScore', color: '#2f8f83', name: 'Rule score' }, { key: 'errorsPer100', color: '#b45309', name: 'Errors/100' }]} />
        </div>
      </section>
      <section className="panel p-5">
        <h3 className="text-xl font-black text-ink">Seniority strata</h3>
        <ResultChart data={seniorityResults} xKey="group" bars={[{ key: 'ruleBefore', color: '#94a3b8', name: 'Rule before' }, { key: 'ruleAfter', color: '#2f8f83', name: 'Rule after' }, { key: 'overallBefore', color: '#cbd5e1', name: 'Overall before' }, { key: 'overallAfter', color: '#1f5673', name: 'Overall after' }]} />
      </section>
      <section className="panel p-5">
        <h3 className="text-xl font-black text-ink">KOM-RAG vs baseline</h3>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <MetricCard label="Precision@10: KOM-RAG vs naive RAG baseline" value="0.676 vs 0.303" />
          <MetricCard label="MRR: KOM-RAG vs naive RAG baseline" value="0.748 vs 0.159" />
          <MetricCard label="nDCG@10: KOM-RAG vs naive RAG baseline" value="0.690 vs 0.237" />
        </div>
        <ResultChart data={ragResults} xKey="metric" bars={[{ key: 'graphRag', color: '#1f5673', name: 'KOM-RAG' }, { key: 'baseline', color: '#94a3b8', name: 'Baseline' }]} />
      </section>
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <div className="panel p-5"><h3 className="font-black text-ink">KOM-Assess support modules</h3><div className="mt-4 grid gap-2">{assessResults.map(x => <MetricCard key={x.label} label={x.label} value={x.value} />)}</div></div>
        <div className="panel p-5"><h3 className="font-black text-ink">KOM-Rad</h3><div className="mt-4 grid gap-2">{imagingResults.map(x => <MetricCard key={x.label} label={x.label} value={x.value} />)}</div></div>
        <div className="panel p-5"><h3 className="font-black text-ink">KOM-Risk</h3><div className="mt-4 grid gap-2">{riskResults.map(x => <MetricCard key={x.label} label={x.label} value={x.value} />)}</div></div>
      </section>
    </div>
  );
}
