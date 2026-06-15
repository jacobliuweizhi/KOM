export const komSystemContent = {
  name: 'KOM Reviewer Interface',
  clinicalName: 'KOM Clinical Review Interface',
  positioning: 'KOM multi-agent decision-support system for individualized knee osteoarthritis management',
  studyType: 'System development, standardized-case validation and clinician-in-the-loop simulation study',
  dataStatus: 'Embedded standardized clinical case set; no external service required',
  workflow: [
    'KOM-Profile',
    'OAK-Net/KOM-Assess',
    'KOM-Risk',
    'KOM-GraphRAG/KOM-Evidence',
    'KOM-Rx',
    'KOM-Safety',
    'KOM-Sim',
    'KOM-Score'
  ],
  validationFramework: [
    '120 standardized cases',
    'Q1-Q4 complexity quadrants',
    'Component ablation',
    'Clinician-in-the-loop simulation',
    'Expert scoring',
    'Safety audit'
  ],
  samplingStatement:
    'The 120 standardized cases were constructed from a candidate standardized clinical case pool through stratified purposive sampling and maximum-variation sampling, rather than random sampling, to cover the major physician-facing knee osteoarthritis management scenarios.',
  reviewerDataBoundary:
    'Values shown in the interface are embedded reviewer-facing research artifacts. Fields that require source import are explicitly marked instead of being fabricated.'
};

export const workflowR0R8 = [
  ['R0', 'Patient profile consensus', 'Anchor symptoms, structure, safety screen, goals, and missing information.'],
  ['R1', 'Sports medicine draft', 'FITT-based therapeutic exercise and load management.'],
  ['R2', 'Weight and nutrition metabolism draft', 'Weight target, protein adequacy, and muscle-preserving plan.'],
  ['R3', 'Psychology and behavior draft', 'Pacing, adherence, expectation alignment, and follow-up behavior support.'],
  ['R4', 'Orthopaedic integrated draft', 'Medication, injection, referral, surgery boundary, and conservative-care strategy.'],
  ['R5', 'Cross-challenge', 'Specialty agents challenge missing gates, conflicts, and unsupported escalation.'],
  ['R6', 'Evidence arbitration', 'Guideline-first hierarchy, direct/context evidence separation, and citation-risk check.'],
  ['R7', 'Orthopaedic arbitration', 'Confirm referral wording, surgery boundary, and safety constraints.'],
  ['R8', 'Final prescription release', 'Structured KOM-Rx plus KOM-Safety audit and follow-up triggers.']
] as const;

export const trialArms = [
  ['A', 'Clinician alone', 'Physician sees standardized case information only.'],
  ['B', 'Clinician + KOM', 'Physician sees final KOM recommendation without full reasoning trace.'],
  ['C', 'Clinician + KOM + explanation', 'Physician sees final KOM recommendation, MDT reasoning, evidence, and safety audit.'],
  ['D', 'KOM standalone', 'System-only benchmark output, not mixed into physician operating workflow.']
] as const;
