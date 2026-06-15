import { Info } from 'lucide-react';
import { getTerm } from '../data/termDefinitions';

export default function TermTooltip({ termKey, label }: { termKey: string; label?: string }) {
  const term = getTerm(termKey);
  if (!term) return <span>{label || termKey}</span>;
  return (
    <span className="group relative inline-flex items-center gap-1 align-baseline">
      <span className="font-bold text-ink">{label || term.key}</span>
      <Info size={14} className="text-clinical" aria-label={`${term.key} definition`} />
      <span className="pointer-events-none absolute left-0 top-7 z-50 hidden w-80 rounded-lg border border-slate-200 bg-white p-3 text-left text-xs font-normal leading-5 text-slate-700 shadow-soft group-hover:block group-focus-within:block">
        <b>{term.english}</b><br />
        {term.chinese}<br />
        {term.shortDefinition}
      </span>
    </span>
  );
}
