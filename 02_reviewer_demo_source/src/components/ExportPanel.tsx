import type { DemoCase } from '../data/demoCases';
import { buildMarkdownReport } from '../engine/exportEngine';
import { caseDisplayId } from '../engine/privacyEngine';

export default function ExportPanel({ selectedCase }: { selectedCase: DemoCase }) {
  const report = buildMarkdownReport(selectedCase);
  const copy = async () => navigator.clipboard?.writeText(report);
  const download = () => {
    const blob = new Blob([report], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${caseDisplayId(selectedCase).replace(/\s/g, '_')}_KOM_report.md`;
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <div className="panel p-5">
      <p className="section-title">Export</p>
      <h3 className="mt-2 text-lg font-black text-ink">Markdown report</h3>
      <div className="mt-4 flex flex-wrap gap-3">
        <button className="focus-ring rounded-md bg-ink px-4 py-2 text-sm font-bold text-white" onClick={download}>Download report</button>
        <button className="focus-ring rounded-md border border-slate-300 px-4 py-2 text-sm font-bold text-ink" onClick={copy}>Copy markdown</button>
      </div>
      <pre className="mt-4 max-h-56 overflow-auto rounded-md bg-slate-950 p-4 text-xs leading-5 text-slate-100">{report}</pre>
    </div>
  );
}
