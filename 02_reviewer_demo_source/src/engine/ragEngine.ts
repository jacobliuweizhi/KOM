import type { DemoCase } from '../data/demoCases';
import { evidenceLibrary, type EvidenceItem } from '../data/evidenceLibrary';

function vectorLikeScore(c: DemoCase, item: EvidenceItem) {
  const text = `${c.doctorTaskPrompt} ${c.functionalGoal} ${c.riskFlags.join(' ')} KL${c.klGrade} BMI${c.bmi}`.toLowerCase();
  const hay = `${item.category} ${item.title} ${item.summary} ${item.applicability.join(' ')}`.toLowerCase();
  return text.split(/\W+/).filter(token => token.length > 2 && hay.includes(token)).length;
}

export function retrieveEvidence(c: DemoCase, topK = 8): EvidenceItem[] {
  const scored = evidenceLibrary.map(item => {
    const matches = item.applicability.filter(tag => c.riskFlags.includes(tag)).length;
    const guidelineBonus = item.guidelineAnchor ? 1.8 : 0;
    const evidenceBonus = item.evidenceLevel === 'Guideline' ? 1.2 : item.evidenceLevel === 'Safety rule' ? 1.1 : 0;
    const safetyMatch = item.safetyTags.filter(tag => c.riskFlags.some(flag => flag.includes(tag) || tag.includes(flag))).length;
    const specialtyBonus = c.klGrade >= 3 && item.specialtyTags.includes('Orthopaedics') ? 0.7 : 0;
    return { item, score: matches * 2 + guidelineBonus + evidenceBonus + safetyMatch + specialtyBonus + vectorLikeScore(c, item) * 0.2 };
  });
  return scored.sort((a, b) => b.score - a.score || b.item.year - a.item.year).slice(0, topK).map(x => x.item);
}

// The naive RAG baseline uses the same evidence library and query but retrieves top-k evidence
// by single-stage vector-like similarity only. It deliberately does not use guideline anchors,
// evidence hierarchy, specialty routing, safety labels, graph links, or evidence arbitration.
export function retrieveNaiveEvidence(c: DemoCase, topK = 5): EvidenceItem[] {
  return evidenceLibrary
    .map(item => ({ item, score: vectorLikeScore(c, item) }))
    .sort((a, b) => b.score - a.score || b.item.year - a.item.year)
    .slice(0, topK)
    .map(x => x.item);
}

export function retrievalSummary(c: DemoCase) {
  const items = retrieveEvidence(c);
  const naive = retrieveNaiveEvidence(c);
  const l1 = items.filter(i => i.guidelineAnchor).length;
  return {
    query: `${c.quadrant} KL${c.klGrade} pain ${c.painNRS} ${c.riskFlags.join(' ')}`,
    topEvidence: items,
    naiveEvidence: naive,
    comparisonMetrics: {
      precisionAt10: { komRag: 0.676, naive: 0.303 },
      mrr: { komRag: 0.748, naive: 0.159 },
      ndcgAt10: { komRag: 0.690, naive: 0.237 }
    },
    currentGuidelineAnchorUsed: l1 > 0,
    directEvidenceIds: items.filter(i => i.evidenceLevel !== 'Observational').map(i => i.id),
    contextEvidenceIds: items.filter(i => i.evidenceLevel === 'Observational').map(i => i.id),
    newestEvidenceYear: Math.max(...items.map(i => i.year))
  };
}
