import type { EvidenceItem } from '../data/evidenceLibrary';
import ModuleBadge from './ModuleBadge';

export default function EvidenceCard({ item }: { item: EvidenceItem }) {
  return (
    <article className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <ModuleBadge label={item.id} tone="blue" />
        <ModuleBadge label={item.evidenceLevel} tone={item.evidenceLevel === 'Guideline' ? 'teal' : item.evidenceLevel === 'Safety rule' ? 'amber' : 'blue'} />
        {item.guidelineAnchor ? <ModuleBadge label="Guideline anchor" tone="teal" /> : null}
      </div>
      <h4 className="mt-3 text-base font-bold text-ink">{item.title}</h4>
      <p className="mt-2 text-sm leading-6 text-muted">{item.summary}</p>
      <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{item.category} · {item.year}</p>
    </article>
  );
}
