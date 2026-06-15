import { glossary } from '../data/glossary';
import { useMemo, useState } from 'react';

export default function GlossaryPage() {
  const [query, setQuery] = useState('');
  const filtered = useMemo(() => glossary.filter(([term, def]) => `${term} ${def}`.toLowerCase().includes(query.toLowerCase())), [query]);
  return (
    <div className="space-y-6">
      <section>
        <p className="section-title">Glossary</p>
        <h2 className="mt-2 text-3xl font-black text-ink">KOM terms and study conditions</h2>
        <input
          aria-label="Search glossary"
          className="mt-4 w-full max-w-xl rounded-lg border border-slate-300 bg-white px-4 py-3 text-base focus-ring"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search terms, e.g. naive RAG baseline"
        />
      </section>
      <section className="panel divide-y divide-slate-100 p-5">
        {filtered.map(([term, def]) => (
          <div key={term} className="grid gap-3 py-3 md:grid-cols-[220px_1fr]">
            <div className="font-black text-ink">{term}</div>
            <div className="small-note">{def}</div>
          </div>
        ))}
      </section>
    </div>
  );
}
