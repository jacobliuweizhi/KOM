import { X } from 'lucide-react';
import { auditContentCompleteness } from '../utils/auditContent';

export default function AuditDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null;
  const audit = auditContentCompleteness();
  return (
    <div className="fixed inset-0 z-50 bg-slate-950/30" role="dialog" aria-label="Audit drawer">
      <aside className="ml-auto h-full w-full max-w-xl overflow-y-auto bg-white p-5 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="section-title">Audit drawer</p>
            <h2 className="mt-2 text-2xl font-black text-ink">Content, source, and export audit</h2>
            <p className="mt-2 small-note">The audit drawer tracks page coverage, field-source logic, MDT modification chain, evidence availability, and export readiness.</p>
          </div>
          <button className="focus-ring rounded-md border border-slate-300 p-2" onClick={onClose} aria-label="Close audit drawer"><X size={18} /></button>
        </div>
        <div className="mt-5 rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div className="text-sm font-black text-ink">Overall audit status: {audit.pass ? 'Pass' : 'Needs source import'}</div>
          <div className="mt-1 text-xs text-muted">Generated at {audit.generated_at}</div>
        </div>
        <div className="mt-4 space-y-2">
          {audit.checks.map((check, index) => (
            <div key={`${check.name}-${index}`} className="rounded-lg border border-slate-200 bg-white p-3">
              <div className="flex items-center justify-between gap-3">
                <span className="font-black text-ink">{check.name}</span>
                <span className={`rounded-full px-3 py-1 text-xs font-black ${check.pass ? 'bg-emerald-50 text-teal' : 'bg-amber-50 text-amber-900'}`}>{check.pass ? 'Pass' : 'Pending'}</span>
              </div>
              <p className="mt-2 text-xs leading-5 text-muted">{check.detail}</p>
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
}
