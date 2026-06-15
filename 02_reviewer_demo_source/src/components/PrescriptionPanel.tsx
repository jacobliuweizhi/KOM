import type { DemoCase } from '../data/demoCases';
import { generatePrescription } from '../engine/prescriptionEngine';

export default function PrescriptionPanel({ selectedCase }: { selectedCase: DemoCase }) {
  const rx = generatePrescription(selectedCase);
  const rows = [
    ['Goals', rx.goals.join('; ')],
    ['Exercise / rehab', rx.exercise],
    ['Weight / nutrition', rx.weightNutrition],
    ['Medication', rx.medication],
    ['Behavior', rx.behavioral],
    ['Injection boundary', rx.injectionBoundary],
    ['Surgery boundary', rx.surgeryBoundary],
    ['Follow-up', rx.followUp]
  ];
  return (
    <div className="panel p-5">
      <p className="section-title">KOM-Rx</p>
      <h3 className="mt-2 text-xl font-black text-ink">Structured prescription</h3>
      <div className="mt-4 divide-y divide-slate-100">
        {rows.map(([k, v]) => (
          <div className="grid gap-3 py-3 md:grid-cols-[180px_1fr]" key={k}>
            <div className="font-bold text-slate-700">{k}</div>
            <div className="small-note">{v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
