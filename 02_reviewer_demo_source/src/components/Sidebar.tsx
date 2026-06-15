import { BarChart3, BookOpen, ClipboardList, FileText, FlaskConical, GitBranch, Home, ShieldCheck, Stethoscope, type LucideIcon } from 'lucide-react';

export type PageKey = 'overview' | 'workspace' | 'assess' | 'treat' | 'sim' | 'score' | 'results' | 'methods' | 'glossary';

const nav: { key: PageKey; label: string; icon: LucideIcon }[] = [
  { key: 'overview', label: 'Overview', icon: Home },
  { key: 'workspace', label: 'Case workspace', icon: Stethoscope },
  { key: 'assess', label: 'KOM-Assess', icon: ClipboardList },
  { key: 'treat', label: 'KOM-Treat', icon: ShieldCheck },
  { key: 'sim', label: 'KOM-Sim', icon: GitBranch },
  { key: 'score', label: 'KOM-Score', icon: FlaskConical },
  { key: 'results', label: 'Results', icon: BarChart3 },
  { key: 'methods', label: 'Methods', icon: FileText },
  { key: 'glossary', label: 'Glossary', icon: BookOpen }
];

export default function Sidebar({ page, setPage }: { page: PageKey; setPage: (p: PageKey) => void }) {
  return (
    <aside className="sticky top-[65px] hidden h-[calc(100vh-65px)] w-64 shrink-0 border-r border-slate-200 bg-white p-4 lg:block">
      <nav className="space-y-1">
        {nav.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.key}
              onClick={() => setPage(item.key)}
              className={`focus-ring flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm font-bold ${page === item.key ? 'bg-clinical text-white' : 'text-slate-700 hover:bg-slate-100'}`}
            >
              <Icon size={18} /> {item.label}
            </button>
          );
        })}
      </nav>
      <div className="mt-6 rounded-lg border border-teal/20 bg-emerald-50 p-3 text-xs leading-5 text-teal">
        Embedded standardized case set for reviewer inspection. The interface uses de-identified labels and does not expose source identifiers.
      </div>
    </aside>
  );
}
