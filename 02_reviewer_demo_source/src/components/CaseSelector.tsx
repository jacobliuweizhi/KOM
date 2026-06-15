import type { DemoCase } from '../data/demoCases';
import { caseDisplayId } from '../engine/privacyEngine';
import ModuleBadge from './ModuleBadge';

export default function CaseSelector({ cases, selectedId, onSelect }: { cases: DemoCase[]; selectedId: string; onSelect: (id: string) => void }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {cases.map((c) => (
        <button
          key={c.id}
          data-testid={`case-card-${c.id}`}
          onClick={() => onSelect(c.id)}
          className={`focus-ring rounded-lg border bg-white p-4 text-left transition ${selectedId === c.id ? 'border-clinical ring-2 ring-clinical/20' : 'border-slate-200 hover:border-clinical/50'}`}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="font-black text-ink">{caseDisplayId(c)}</span>
            <ModuleBadge label={c.quadrant} tone={c.quadrant === 'Q4' ? 'red' : c.quadrant === 'Q3' ? 'amber' : 'blue'} />
          </div>
          <p className="mt-2 text-sm leading-5 text-muted">{c.age}y {c.sex}, BMI {c.bmi}, KL {c.klGrade}, NRS {c.painNRS}</p>
          <p className="mt-2 text-xs font-semibold text-slate-500">{c.functionalGoal}</p>
        </button>
      ))}
    </div>
  );
}
