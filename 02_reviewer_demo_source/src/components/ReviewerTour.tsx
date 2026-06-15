const steps = [
  'Select case',
  'Run KOM-Assess',
  'Run KOM-Treat',
  'Compare clinician conditions',
  'Review study-level results'
];

export default function ReviewerTour() {
  return (
    <div className="panel p-4">
      <p className="section-title">Reviewer tour</p>
      <div className="mt-3 grid gap-2 md:grid-cols-5">
        {steps.map((step, idx) => (
          <div key={step} className="rounded-md border border-slate-200 bg-slate-50 p-3">
            <div className="text-xs font-black text-clinical">Step {idx + 1}</div>
            <div className="mt-1 text-sm font-bold text-ink">{step}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
