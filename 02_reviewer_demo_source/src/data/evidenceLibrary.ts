export type EvidenceItem = {
  id: string;
  category: string;
  title: string;
  evidenceLevel: 'Guideline' | 'Meta-analysis' | 'RCT' | 'Observational' | 'Safety rule';
  guidelineAnchor: boolean;
  year: number;
  summary: string;
  applicability: string[];
  specialtyTags: string[];
  safetyTags: string[];
};

export const evidenceLibrary: EvidenceItem[] = [
  { id: 'KOA-EU-00001', category: 'exercise', title: 'Core therapeutic exercise and physical activity for knee osteoarthritis', evidenceLevel: 'Guideline', guidelineAnchor: true, year: 2022, summary: 'Structured land-based exercise, strength, aerobic activity, and patient education are core conservative care.', applicability: ['early_structural_oa', 'moderate_severe_oa', 'severe_structural_oa', 'fall_risk'], specialtyTags: ['Sports medicine', 'Rehabilitation'], safetyTags: ['exercise_progression'] },
  { id: 'KOA-EU-00003', category: 'weight', title: 'Weight management for overweight or obese adults with knee OA', evidenceLevel: 'Guideline', guidelineAnchor: true, year: 2022, summary: 'Weight reduction should be paired with strength and nutritional adequacy when BMI is elevated.', applicability: ['high_bmi', 'weight_need', 'weight_watch'], specialtyTags: ['Nutrition'], safetyTags: ['muscle_preservation'] },
  { id: 'KOA-EU-00014', category: 'topical NSAIDs', title: 'Topical NSAID as first-line analgesic consideration', evidenceLevel: 'Guideline', guidelineAnchor: true, year: 2019, summary: 'Topical NSAIDs may be considered before systemic NSAIDs for knee OA pain when local therapy is appropriate.', applicability: ['gi_risk', 'renal_risk', 'cv_risk', 'low_pain', 'high_pain'], specialtyTags: ['Medication'], safetyTags: ['nsaid_gate'] },
  { id: 'KOA-EU-00030', category: 'oral NSAIDs', title: 'Oral NSAID safety gate', evidenceLevel: 'Safety rule', guidelineAnchor: true, year: 2022, summary: 'Renal, gastrointestinal, cardiovascular, anticoagulant, and current-medication review should precede oral NSAID escalation.', applicability: ['gi_risk', 'renal_risk', 'cv_risk'], specialtyTags: ['Medication', 'Safety'], safetyTags: ['renal', 'gi', 'cv', 'anticoagulant'] },
  { id: 'KOA-EU-00054', category: 'duloxetine', title: 'Central pain phenotype and duloxetine boundary', evidenceLevel: 'Guideline', guidelineAnchor: true, year: 2019, summary: 'Duloxetine may be conditionally considered in selected persistent pain phenotypes after safety and interaction review.', applicability: ['high_pain'], specialtyTags: ['Medication', 'Behavior'], safetyTags: ['drug_interaction'] },
  { id: 'KOA-EU-00071', category: 'injection', title: 'Injection therapy should not be routine maintenance care', evidenceLevel: 'Guideline', guidelineAnchor: true, year: 2022, summary: 'Injection is framed as a conditional bridge or escalation option, not a default long-term solution.', applicability: ['high_pain', 'surgery_boundary'], specialtyTags: ['Medication', 'Orthopaedics'], safetyTags: ['injection_boundary'] },
  { id: 'KOA-EU-00088', category: 'surgery referral', title: 'Orthopaedic referral based on symptoms, function, imaging, and preferences', evidenceLevel: 'Guideline', guidelineAnchor: true, year: 2022, summary: 'Surgery is not decided by imaging alone; referral is appropriate when severe symptoms and structural disease persist despite optimized conservative care.', applicability: ['surgery_boundary', 'surgery_information_gap', 'severe_structural_oa'], specialtyTags: ['Orthopaedics'], safetyTags: ['surgery_boundary'] },
  { id: 'KOA-EU-00108', category: 'self-management', title: 'Education, pacing, adherence, and shared decision-making', evidenceLevel: 'Guideline', guidelineAnchor: true, year: 2022, summary: 'Self-management support includes education, pacing, sleep, activity planning, shared goals, and follow-up.', applicability: ['high_exercise_demand', 'workload_conflict', 'high_pain'], specialtyTags: ['Behavior'], safetyTags: ['expectation'] },
  { id: 'KOA-EU-00129', category: 'safety', title: 'Fall-risk modification during exercise prescription', evidenceLevel: 'Observational', guidelineAnchor: false, year: 2021, summary: 'Balance limitation and prior falls should change exercise progression, supervision, and home-safety advice.', applicability: ['fall_risk', 'strength_decline'], specialtyTags: ['Rehabilitation', 'Safety'], safetyTags: ['fall_risk'] }
];
