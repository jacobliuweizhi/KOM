import type { DemoCase } from '../data/demoCases';
import { generatePrescription } from './prescriptionEngine';
import { safetyAudit } from './safetyEngine';
import { retrievalSummary } from './ragEngine';

export function scorePrescription(c: DemoCase) {
  const rx = generatePrescription(c);
  const audit = safetyAudit(c);
  const retrieval = retrievalSummary(c);
  const fields = Object.values(rx).filter(Boolean).length;
  const completeness = Math.min(10, fields);
  const safety = audit.status === 'critical' ? 4 : audit.status === 'warning' ? 8 : 9.5;
  const guidelineAlignment = retrieval.currentGuidelineAnchorUsed ? 8.8 : 6.5;
  const personalization = c.riskFlags.length >= 4 ? 9 : 7.8;
  const actionability = rx.exercise.includes('FITT') && rx.followUp.includes('weeks') ? 9 : 7;
  const evidenceTraceability = retrieval.directEvidenceIds.length >= 3 ? 9 : 6.5;
  const overall = Number(((completeness + safety + guidelineAlignment + personalization + actionability + evidenceTraceability) / 6).toFixed(2));
  const safetyCriticalErrorRate = audit.safetyCriticalErrors.length * 100;
  return {
    completeness,
    safety,
    guidelineAlignment,
    personalization,
    actionability,
    evidenceTraceability,
    overall,
    safetyCriticalErrors: audit.safetyCriticalErrors.length,
    clinicallyRelevantErrors: audit.clinicallyRelevantErrors.length,
    safetyCriticalErrorRate
  };
}
