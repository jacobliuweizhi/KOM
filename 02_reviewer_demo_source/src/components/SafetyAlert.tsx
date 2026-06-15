import ModuleBadge from './ModuleBadge';

export default function SafetyAlert({ status, alerts }: { status: 'pass' | 'warning' | 'critical'; alerts: string[] }) {
  const tone = status === 'critical' ? 'red' : status === 'warning' ? 'amber' : 'teal';
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-bold text-ink">KOM-Safe safety audit</h3>
        <ModuleBadge label={status.toUpperCase()} tone={tone} />
      </div>
      <ul className="mt-3 space-y-2 text-sm leading-6 text-muted">
        {alerts.map((a) => <li key={a}>• {a}</li>)}
      </ul>
    </div>
  );
}
