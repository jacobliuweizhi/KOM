import type { DemoCase } from '../data/demoCases';
import { retrieveEvidence } from './ragEngine';

export type AgentAdvice = {
  agent: string;
  focus: string;
  advice: string;
  evidenceIds: string[];
};

export function buildMdtAdvice(c: DemoCase): AgentAdvice[] {
  const ev = retrieveEvidence(c);
  const evidenceIds = (category: string) => ev.filter(e => e.category.includes(category) || e.category === category).map(e => e.id);
  return [
    {
      agent: 'Sports medicine',
      focus: 'FITT exercise prescription and load management',
      advice: c.klGrade >= 3
        ? 'Start supervised low-impact aerobic work, strength, balance, and mobility; avoid high-impact return until pain, swelling, and technique are stable.'
        : 'Use progressive walking/cycling, quadriceps and hip strengthening, and activity pacing with symptom-guided progression.',
      evidenceIds: [...evidenceIds('exercise'), ...evidenceIds('safety')]
    },
    {
      agent: 'Weight and nutrition',
      focus: 'Weight trajectory, protein adequacy, and metabolic risk',
      advice: c.bmi >= 30
        ? 'Set a 12-week weight target with muscle-preserving protein distribution and calcium/vitamin D adequacy review.'
        : 'Maintain energy balance and protein adequacy while supporting exercise adherence.',
      evidenceIds: evidenceIds('weight')
    },
    {
      agent: 'Psychology/behavior',
      focus: 'Pacing, confidence, adherence, and expectation alignment',
      advice: 'Use shared goals, flare rules, pain education, and short follow-up contacts to reduce avoidance and improve adherence.',
      evidenceIds: evidenceIds('self-management')
    },
    {
      agent: 'Orthopaedic management',
      focus: 'Referral boundary and escalation sequencing',
      advice: c.klGrade >= 3
        ? 'Document response to optimized conservative care and discuss orthopaedic review if severe pain/function limitation persists.'
        : 'Do not escalate to surgical decision-making; monitor symptoms, function, and radiographic progression.',
      evidenceIds: evidenceIds('surgery referral')
    },
    {
      agent: 'Evidence arbitration',
      focus: 'Guideline hierarchy and safety constraints',
      advice: 'Keep guideline-core care first, add enhanced options only when matched, and downgrade any medication or injection suggestion when safety data are incomplete.',
      evidenceIds: ev.slice(0, 4).map(e => e.id)
    }
  ];
}
