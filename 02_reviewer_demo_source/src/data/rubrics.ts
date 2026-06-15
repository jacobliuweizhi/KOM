export const scoringDimensions = [
  { key: 'overall', label: 'Overall quality', text: 'Overall clinical usefulness as a physician-facing KOA prescription.' },
  { key: 'safety', label: 'Safety', text: 'Safety gates, contraindications, escalation boundaries, and clinician review flags.' },
  { key: 'guidelineAlignment', label: 'Guideline alignment', text: 'Consistency with current KOA guideline anchors and clinical standards.' },
  { key: 'personalization', label: 'Patient personalization', text: 'Use of KL grade, pain, BMI, comorbidity, preferences, and functional goals.' },
  { key: 'actionability', label: 'Actionability', text: 'Specific dose, frequency, intensity, duration, progression, and stopping rules.' },
  { key: 'evidenceTraceability', label: 'Evidence traceability', text: 'Recommendation-specific evidence or explicit rule-based rationale.' },
  { key: 'specialtyCompleteness', label: 'Specialty completeness', text: 'Medication, surgery boundary, exercise, nutrition, behavior, and follow-up coverage.' },
  { key: 'clinicalConsistency', label: 'Clinical consistency', text: 'No contradictions across domains and no unrealistic sequencing.' }
];

export const errorDefinitions = [
  {
    label: 'Safety-critical error',
    english: 'A safety-critical error is a recommendation or omission that may cause material patient harm, violates a clear contraindication, inappropriately recommends or delays surgical referral, misuses high-risk medication, or omits essential risk gating.',
    chinese: '安全关键错误是指可能造成实质性患者伤害、违反明确禁忌、错误推荐或延迟外科转诊、误用高风险药物，或遗漏必要风险把关的建议或遗漏。'
  },
  {
    label: 'Clinically relevant error',
    english: 'A clinically relevant error is a recommendation that clearly reduces prescription quality or decision usefulness without immediate direct harm.',
    chinese: '临床相关错误是指明显降低处方质量或决策可用性，但通常不会立即直接致害的问题。'
  },
  {
    label: 'Minor error',
    english: 'A minor error is a wording, formatting, or non-critical detail that can be improved without changing the main clinical plan.',
    chinese: '轻微错误是指措辞、格式或非关键细节问题，通常不改变主要临床方案。'
  }
];
