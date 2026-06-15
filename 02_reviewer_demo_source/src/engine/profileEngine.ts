import type { DemoCase } from '../data/demoCases';

export function structuredProfile(c: DemoCase) {
  return {
    identity: `${c.age}-year-old ${c.sex.toLowerCase()} with ${c.affectedSide.toLowerCase()} knee-dominant KOA`,
    severityLabel: severityLabel(c),
    phenotype: phenotype(c),
    quadrantExplanation: quadrantExplanation(c),
    keyRisks: keyRisks(c),
    profileRows: [
      ['Age / sex', `${c.age}, ${c.sex}`],
      ['BMI', c.bmi.toFixed(1)],
      ['Pain NRS', String(c.painNRS)],
      ['KL grade', `KL ${c.klGrade}`],
      ['Radiographic pattern', `${c.jsn} JSN, ${c.osteophyte} osteophyte, ${c.sclerosis} sclerosis`],
      ['Functional goal', c.functionalGoal]
    ]
  };
}

export function severityLabel(c: DemoCase) {
  if (c.klGrade >= 4 || c.painNRS >= 8) return 'High structural or symptom burden';
  if (c.klGrade >= 3 || c.painNRS >= 6) return 'Moderate-to-high burden';
  return 'Early or mild-to-moderate burden';
}

export function phenotype(c: DemoCase) {
  const tags = [];
  if (c.bmi >= 30) tags.push('obesity-related mechanical load');
  if (c.riskFlags.includes('fall_risk') || c.riskFlags.includes('strength_decline')) tags.push('neuromuscular/fall-risk phenotype');
  if (c.riskFlags.includes('gi_risk') || c.riskFlags.includes('renal_risk') || c.riskFlags.includes('cv_risk')) tags.push('medication-safety constrained phenotype');
  if (c.klGrade >= 3) tags.push('structural progression phenotype');
  if (!tags.length) tags.push('conservative-care responsive phenotype');
  return tags.join('; ');
}

export function quadrantExplanation(c: DemoCase) {
  const demand = c.riskFlags.includes('high_exercise_demand') || c.functionalGoal.toLowerCase().includes('work') ? 'high demand' : 'usual demand';
  const burden = c.klGrade >= 3 || c.painNRS >= 6 ? 'high burden' : 'lower burden';
  return `${c.quadrant}: ${burden}, ${demand}.`;
}

export function keyRisks(c: DemoCase) {
  return c.riskFlags.map(flag => flag.replace(/_/g, ' '));
}
