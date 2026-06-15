import type { DemoCase } from '../data/demoCases';
import { structuredProfile } from './profileEngine';
import { retrievalSummary } from './ragEngine';
import { buildMdtAdvice } from './mdtEngine';
import { generatePrescription } from './prescriptionEngine';
import { safetyAudit } from './safetyEngine';
import { caseDisplayId, deidentificationNote } from './privacyEngine';

export function buildMarkdownReport(c: DemoCase) {
  const profile = structuredProfile(c);
  const retrieval = retrievalSummary(c);
  const mdt = buildMdtAdvice(c);
  const rx = generatePrescription(c);
  const safe = safetyAudit(c);
  return [
    `# KOM Reviewer Interface Report: ${caseDisplayId(c)}`,
    '',
    deidentificationNote,
    '',
    '## Case summary',
    `${profile.identity}. ${profile.severityLabel}. ${profile.phenotype}.`,
    '',
    '## KOM-Assess',
    profile.profileRows.map(([k, v]) => `- ${k}: ${v}`).join('\n'),
    '',
    '## KOM-Treat / KOM-RAG evidence',
    retrieval.topEvidence.map(e => `- ${e.id}: ${e.title} (${e.evidenceLevel}, ${e.year})`).join('\n'),
    '',
    '## KOM-RAG versus naive RAG baseline',
    `KOM-RAG: ${retrieval.topEvidence.map(e => e.id).join(', ')}`,
    `naive RAG baseline: ${retrieval.naiveEvidence.map(e => e.id).join(', ')}`,
    'Naive RAG baseline uses single-stage vector top-k retrieval over the same evidence library without guideline anchors, evidence hierarchy, specialty routing, safety labels, graph links, or evidence arbitration.',
    '',
    '## KOM-MDT',
    mdt.map(a => `- ${a.agent}: ${a.advice}`).join('\n'),
    '',
    '## Final prescription',
    `- Exercise: ${rx.exercise}`,
    `- Weight/nutrition: ${rx.weightNutrition}`,
    `- Medication: ${rx.medication}`,
    `- Behavior: ${rx.behavioral}`,
    `- Follow-up: ${rx.followUp}`,
    '',
    '## KOM-Safe',
    `Status: ${safe.status}`,
    safe.alerts.map(a => `- ${a}`).join('\n'),
    '',
    '## Metric definitions',
    'Safety-critical error rate = number of safety-critical errors / number of prescription records x 100.',
    '',
    'Reviewer note: local standardized case workflow package; no external service used.'
  ].join('\n');
}
