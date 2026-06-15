export default function ModuleBadge({ label, tone = 'blue' }: { label: string; tone?: 'blue' | 'teal' | 'amber' | 'red' }) {
  const map = {
    blue: 'bg-blue-50 text-clinical border-blue-100',
    teal: 'bg-emerald-50 text-teal border-emerald-100',
    amber: 'bg-amber-50 text-amber-800 border-amber-100',
    red: 'bg-rose-50 text-rose-800 border-rose-100'
  };
  return <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-bold ${map[tone]}`}>{label}</span>;
}
