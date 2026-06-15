import { errorDefinitions, scoringDimensions } from '../data/rubrics';
import MetricCard from '../components/MetricCard';
import TermTooltip from '../components/TermTooltip';

export default function ScorePage() {
  return (
    <div className="space-y-6">
      <section>
        <p className="section-title">KOM-Score</p>
        <h2 className="mt-2 text-3xl font-black text-ink"><TermTooltip termKey="KOM-Score" />: evaluation anchors, reliability, and error taxonomy</h2>
      </section>
      <section className="panel p-5">
        <p className="section-title">Formula</p>
        <h3 className="mt-2 text-xl font-black text-ink"><TermTooltip termKey="safety-critical error rate" /></h3>
        <p className="mt-3 rounded-lg bg-slate-50 p-4 font-mono text-sm text-ink">Safety-critical error rate = number of safety-critical errors / number of prescription records × 100.</p>
      </section>
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {scoringDimensions.map(d => <MetricCard key={d.key} label={d.label} value="0-10" note={d.text} />)}
      </section>
      <section className="grid gap-4 lg:grid-cols-3">
        {errorDefinitions.map(e => (
          <div className="panel p-5" key={e.label}>
            <h3 className="text-lg font-black text-ink">{e.label}</h3>
            <p className="mt-3 text-sm leading-6 text-muted">{e.english}</p>
            <p className="mt-3 text-sm leading-6 text-slate-700">{e.chinese}</p>
          </div>
        ))}
      </section>
      <section className="panel p-5">
        <h3 className="text-xl font-black text-ink">Scoring sources</h3>
        <p className="mt-3 small-note">KOM-Score combines senior physician evaluation anchors, deterministic rule scoring, specialty evaluator scoring, ICC reliability reporting, and error-level review.</p>
      </section>
    </div>
  );
}
