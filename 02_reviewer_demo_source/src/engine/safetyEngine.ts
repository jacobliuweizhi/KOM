import type { DemoCase } from '../data/demoCases';

export type SafetyStatus = 'pass' | 'warning' | 'critical';

export function safetyAudit(c: DemoCase) {
  const alerts: string[] = [];
  const revisionSuggestions: string[] = [];
  const safetyCriticalErrors: string[] = [];
  const clinicallyRelevantErrors: string[] = [];
  const minorErrors: string[] = [];
  let status: SafetyStatus = 'pass';

  if (c.riskFlags.includes('renal_risk') || c.riskFlags.includes('gi_risk') || c.riskFlags.includes('cv_risk')) {
    status = 'warning';
    alerts.push('Oral NSAID escalation requires renal, gastrointestinal, cardiovascular, anticoagulant, and medication review.');
    revisionSuggestions.push('Defer routine oral NSAID recommendation until safety gates are documented.');
    clinicallyRelevantErrors.push('Medication plan must not recommend routine oral NSAID before safety gates are cleared.');
  }
  if (c.riskFlags.includes('high_exercise_demand') && c.klGrade >= 3) {
    status = 'warning';
    alerts.push('High-impact sport or work exposure conflicts with severe structural disease and active symptoms.');
    revisionSuggestions.push('Use low-impact conditioning first and specify stop rules for swelling or pain flare.');
    clinicallyRelevantErrors.push('Exercise prescription needs explicit intensity and stop-rule boundaries.');
  }
  if (c.riskFlags.includes('fall_risk')) {
    status = 'warning';
    alerts.push('Fall risk requires balance training, supervised progression, and home-safety review.');
    minorErrors.push('Balance and home-safety monitoring should be explicit.');
  }
  if (c.klGrade >= 4 && c.painNRS >= 8 && !c.riskFlags.includes('surgery_boundary')) {
    status = 'critical';
    alerts.push('Severe symptoms with advanced structure require explicit orthopaedic review boundary.');
    safetyCriticalErrors.push('Advanced KOA with severe symptoms lacks an orthopaedic referral boundary.');
  }
  if (!alerts.length) {
    alerts.push('No safety-critical issue detected in the available standardized case fields.');
  }
  return { status, alerts, revisionSuggestions, safetyCriticalErrors, clinicallyRelevantErrors, minorErrors };
}
