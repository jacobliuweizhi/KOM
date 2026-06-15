import type { DemoCase } from '../data/demoCases';
import { safetyAudit } from './safetyEngine';

export function generatePrescription(c: DemoCase) {
  const audit = safetyAudit(c);
  return {
    goals: [`Reduce pain from NRS ${c.painNRS}`, c.functionalGoal, 'Preserve function while avoiding unsafe escalation.'],
    exercise: c.klGrade >= 3
      ? 'FITT: low-impact aerobic training 3-5 days/week, 20-30 minutes/session as tolerated; supervised strength 2-3 days/week; balance and gait training twice weekly; progress only when next-day swelling and pain remain controlled.'
      : 'FITT: walking or cycling 4-5 days/week, 20-40 minutes/session; strengthening 2-3 days/week; progress duration before intensity and use flare-based pacing.',
    weightNutrition: c.bmi >= 30
      ? 'Set a 12-week 5% weight-loss target with protein distributed across meals, resistance exercise support, and diet recording.'
      : 'Maintain healthy weight, adequate protein, and vitamin D/calcium review while supporting activity adherence.',
    medication: c.riskFlags.some(f => ['renal_risk', 'gi_risk', 'cv_risk'].includes(f))
      ? 'Topical NSAID or acetaminophen may be considered; defer routine oral NSAID until renal, GI, CV, anticoagulant, and current-medication review is complete.'
      : 'Topical NSAID first; short oral NSAID trial only if risk review is acceptable and clinician confirms indication.',
    behavioral: 'Provide pain education, shared goals, pacing, sleep and flare rules, and a 2-4 week adherence check.',
    injectionBoundary: c.painNRS >= 7 ? 'Injection is not routine; consider only as a time-limited bridge after clinician review and if conservative care response is inadequate.' : 'Injection is not indicated as routine care in this demonstration scenario.',
    surgeryBoundary: c.klGrade >= 3 ? 'Arrange orthopaedic review if optimized conservative care fails or severe function limitation persists; imaging alone does not decide surgery.' : 'No surgical pathway unless symptoms and function substantially worsen.',
    followUp: 'Reassess pain, WOMAC/function, walking tolerance, swelling, adverse events, and adherence at 2-4 weeks and 8-12 weeks.',
    safetyNotes: audit.alerts
  };
}
