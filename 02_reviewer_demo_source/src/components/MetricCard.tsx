export default function MetricCard({ label, value, note }: { label: string; value: string | number; note?: string }) {
  return (
    <div className="panel p-4">
      <div className="text-2xl font-black text-ink">{value}</div>
      <div className="mt-1 text-sm font-semibold text-slate-700">{label}</div>
      {note ? <div className="mt-2 text-xs leading-5 text-muted">{note}</div> : null}
    </div>
  );
}
