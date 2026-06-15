import { useEffect, useState } from 'react';
import type { DemoCase } from '../data/demoCases';
import PrescriptionPanel from '../components/PrescriptionPanel';

const conditions = ['Clinician alone', 'Clinician + KOM', 'Clinician + KOM-R', 'KOM standalone'] as const;
type Condition = typeof conditions[number];

export default function SimPage({ selectedCase }: { selectedCase: DemoCase }) {
  const [condition, setCondition] = useState<Condition>(() => (localStorage.getItem('kom_sim_condition') as Condition) || 'Clinician + KOM');
  const [draft, setDraft] = useState(() => localStorage.getItem(`kom_sim_draft_${selectedCase.id}`) || '');
  useEffect(() => { localStorage.setItem('kom_sim_condition', condition); }, [condition]);
  useEffect(() => { localStorage.setItem(`kom_sim_draft_${selectedCase.id}`, draft); }, [draft, selectedCase.id]);
  return (
    <div className="space-y-6">
      <section>
        <p className="section-title">KOM-Sim</p>
        <h2 className="mt-2 text-3xl font-black text-ink">Standardized clinician prescription task</h2>
        <p className="mt-3 small-note">KOM-Sim represents repeated standardized prescription tasks: 26 physicians × 30 tasks = 780 physician-task prescription records.</p>
      </section>
      <div className="panel p-5">
        <div className="flex flex-wrap gap-2">
          {conditions.map(c => <button key={c} className={`focus-ring rounded-md px-4 py-2 text-sm font-bold ${condition === c ? 'bg-ink text-white' : 'border border-slate-300 bg-white text-ink'}`} onClick={() => setCondition(c)}>{c}</button>)}
        </div>
      </div>
      <section className="grid gap-5 xl:grid-cols-2">
        <div className="panel p-5">
          <h3 className="text-xl font-black text-ink">Physician task</h3>
          <p className="mt-3 small-note">{selectedCase.doctorTaskPrompt}</p>
          {condition !== 'KOM standalone' ? (
            <textarea data-testid="sim-textarea" className="mt-4 h-72 w-full rounded-lg border border-slate-300 p-4 text-base leading-7 focus-ring" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Write a concise prescription draft here..." />
          ) : <p className="mt-4 rounded-lg bg-slate-50 p-4 small-note">KOM standalone displays the benchmark system output without physician editing.</p>}
        </div>
        <div className="space-y-5">
          {(condition === 'Clinician + KOM' || condition === 'Clinician + KOM-R' || condition === 'KOM standalone') && <PrescriptionPanel selectedCase={selectedCase} />}
          {condition === 'Clinician + KOM-R' && (
            <div className="panel p-5">
              <h3 className="font-black text-ink">Rationale display</h3>
              <p className="mt-3 small-note">KOM-R adds recommendation-specific rationale, evidence hierarchy, and safety-gate explanation for reviewer inspection.</p>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
