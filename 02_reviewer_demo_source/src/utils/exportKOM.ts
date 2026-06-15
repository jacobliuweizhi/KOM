import type { DemoCase } from '../data/demoCases';
import { komSystemContent } from '../data/komContent';
import { buildMarkdownReport } from '../engine/exportEngine';
import { structuredProfile } from '../engine/profileEngine';
import { retrievalSummary } from '../engine/ragEngine';
import { safetyAudit } from '../engine/safetyEngine';
import { generatePrescription } from '../engine/prescriptionEngine';
import { caseDisplayId } from '../engine/privacyEngine';
import { auditContentCompleteness } from './auditContent';

function downloadText(filename: string, text: string, mime = 'text/plain;charset=utf-8') {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function safeId(c: DemoCase) {
  return c.id.replace(/[^A-Za-z0-9_-]/g, '_');
}

export function exportCurrentCaseJSON(c: DemoCase) {
  const payload = {
    system: komSystemContent.name,
    case_label: caseDisplayId(c),
    case: c,
    profile: structuredProfile(c),
    evidence: retrievalSummary(c),
    prescription: generatePrescription(c),
    safety: safetyAudit(c),
    exported_at: new Date().toISOString()
  };
  downloadText(`KOM_case_${safeId(c)}_review.json`, JSON.stringify(payload, null, 2), 'application/json;charset=utf-8');
}

export function exportTrialWideCSV(cases: DemoCase[]) {
  const header = [
    'physician_id',
    'case_id',
    'quadrant',
    'arm',
    'prescription_text',
    'time_seconds',
    'trust_score',
    'workload_score',
    'info_sufficiency',
    'decision_confidence',
    'ai_adoption',
    'safety_flags',
    'quality_score',
    'timestamp'
  ];
  const rows = cases.flatMap((c) => ['Clinician alone', 'Clinician + KOM', 'Clinician + KOM + explanation'].map((arm, idx) => [
    `anonymous_${String(idx + 1).padStart(2, '0')}`,
    c.id,
    c.quadrant,
    arm,
    idx === 0 ? 'Pending clinician-entered prescription' : generatePrescription(c).exercise,
    '',
    '',
    '',
    '',
    '',
    '',
    safetyAudit(c).alerts.join('; '),
    '',
    new Date().toISOString()
  ]));
  const csv = [header, ...rows]
    .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    .join('\n');
  downloadText('KOM_clinician_trial_wide_export.csv', csv, 'text/csv;charset=utf-8');
}

export function exportReviewerSummaryMarkdown(c: DemoCase) {
  downloadText(`KOM_reviewer_summary_${safeId(c)}.md`, buildMarkdownReport(c), 'text/markdown;charset=utf-8');
}

export function exportContentAuditJSON() {
  const audit = auditContentCompleteness();
  downloadText('KOM_content_audit.json', JSON.stringify(audit, null, 2), 'application/json;charset=utf-8');
}
