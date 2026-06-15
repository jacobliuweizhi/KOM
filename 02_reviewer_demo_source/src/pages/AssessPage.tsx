import type { DemoCase } from '../data/demoCases';
import MetricCard from '../components/MetricCard';
import { structuredProfile } from '../engine/profileEngine';
import { caseDisplayId } from '../engine/privacyEngine';

export default function AssessPage({ selectedCase }: { selectedCase: DemoCase }) {
  const profile = structuredProfile(selectedCase);
  const risks = [
    { label: 'Structural progression', value: Math.min(92, 35 + selectedCase.klGrade * 12 + (selectedCase.bmi >= 30 ? 10 : 0)) },
    { label: 'Surgery need', value: Math.min(90, selectedCase.klGrade * 15 + selectedCase.painNRS * 3) },
    { label: 'Symptom/function worsening', value: Math.min(88, selectedCase.painNRS * 8 + (selectedCase.riskFlags.includes('fall_risk') ? 10 : 0)) }
  ];
  return (
    <div className="space-y-6">
      <section>
        <p className="section-title">KOM-Assess</p>
        <h2 className="mt-2 text-3xl font-black text-ink">Assessment support for {caseDisplayId(selectedCase)}</h2>
        <p className="mt-3 small-note">KOM-Assess organizes physician-side profile, radiographic support, phenotype explanation, staging, and longitudinal risk context.</p>
      </section>
      <section className="grid gap-5 xl:grid-cols-[1fr_1fr_1fr]">
        <div className="panel p-5">
          <h3 className="text-xl font-black text-ink">KOM-Profile</h3>
          <div className="mt-4 space-y-2">
            {profile.profileRows.map(([k, v]) => <MetricCard key={k} label={k} value={v} />)}
          </div>
        </div>
        <div className="panel p-5">
          <h3 className="text-xl font-black text-ink">KOM-Rad</h3>
          <div className="mt-4 grid gap-3">
            <MetricCard label="KL grade" value={`KL ${selectedCase.klGrade}`} />
            <MetricCard label="Joint-space narrowing" value={selectedCase.jsn} />
            <MetricCard label="Osteophyte" value={selectedCase.osteophyte} />
            <MetricCard label="Sclerosis" value={selectedCase.sclerosis} />
            <MetricCard label="Uncertainty boundary" value="Physician review required" note="Imaging support is displayed separately from interview-derived fields." />
          </div>
        </div>
        <div className="panel p-5">
          <h3 className="text-xl font-black text-ink">KOM-Risk</h3>
          <div className="mt-4 space-y-5">
            {risks.map(r => <div key={r.label}><div className="flex justify-between text-sm font-bold"><span>{r.label}</span><span>{r.value}%</span></div><div className="mt-2 h-3 rounded-full bg-slate-100"><div className="h-3 rounded-full bg-clinical" style={{ width: `${r.value}%` }} /></div></div>)}
          </div>
        </div>
      </section>
      <section className="panel p-5">
        <h3 className="text-xl font-black text-ink">Phenotype and staging explanation</h3>
        <p className="mt-3 small-note"><b>Phenotype:</b> {profile.phenotype}</p>
        <p className="mt-2 small-note"><b>Quadrant:</b> {profile.quadrantExplanation}</p>
        <p className="mt-2 small-note"><b>Key risks:</b> {profile.keyRisks.join(', ')}</p>
      </section>
    </div>
  );
}
