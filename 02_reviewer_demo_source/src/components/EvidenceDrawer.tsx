import { X } from 'lucide-react';
import { evidenceLibrary } from '../data/evidenceLibrary';

export default function EvidenceDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 bg-slate-950/30" role="dialog" aria-label="Evidence drawer">
      <aside className="ml-auto h-full w-full max-w-xl overflow-y-auto bg-white p-5 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="section-title">Evidence drawer</p>
            <h2 className="mt-2 text-2xl font-black text-ink">Recommendation-linked evidence units</h2>
            <p className="mt-2 small-note">Each evidence unit shows its identifier, hierarchy level, specialty domain, applicability boundary, and limitation for reviewer inspection.</p>
          </div>
          <button className="focus-ring rounded-md border border-slate-300 p-2" onClick={onClose} aria-label="Close evidence drawer"><X size={18} /></button>
        </div>
        <div className="mt-5 space-y-3">
          {evidenceLibrary.map((item) => (
            <article key={item.id} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-black text-clinical">{item.id}</span>
                <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-black text-teal">{item.evidenceLevel}</span>
                <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-slate-600">{item.category}</span>
              </div>
              <h3 className="mt-3 font-black text-ink">{item.title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted">{item.summary}</p>
              <dl className="mt-3 grid gap-2 text-xs text-slate-600">
                <div><dt className="font-black text-ink">Applicability</dt><dd>{item.applicability.join(', ')}</dd></div>
                <div><dt className="font-black text-ink">Specialty library</dt><dd>{item.specialtyTags.join(', ')}</dd></div>
                <div><dt className="font-black text-ink">Safety boundary</dt><dd>{item.safetyTags.join(', ')}</dd></div>
              </dl>
            </article>
          ))}
        </div>
      </aside>
    </div>
  );
}
