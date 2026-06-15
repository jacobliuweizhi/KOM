export const reliabilityResults = [
  { label: 'Ablation task ICC', value: 0.796 },
  { label: 'KOM-Sim ICC', value: 0.946 },
  { label: 'Safety dimension ICC', value: 0.574 }
];

export const ablationResults = [
  { condition: 'Full KOM', overall: 8.46, safety: 9.11 },
  { condition: 'KOM w/o RAG', overall: 6.56, safety: 7.99 },
  { condition: 'KOM w/o MDT', overall: 6.44, safety: 7.91 },
  { condition: 'Direct LLM', overall: 5.47, safety: 7.07 }
];

export const simResults = [
  { condition: 'Clinician alone', overall: 4.87, ruleScore: 30.1, errorsPer100: 19.7 },
  { condition: 'Clinician + KOM', overall: 7.34, ruleScore: 63.7, errorsPer100: 8.8 },
  { condition: 'Clinician + KOM-R', overall: 7.01, ruleScore: 61.0, errorsPer100: 14.5 },
  { condition: 'KOM standalone', overall: 8.46, ruleScore: 70.0, errorsPer100: 0 }
];

export const seniorityResults = [
  { group: 'Low seniority', ruleBefore: 32.5, ruleAfter: 66.4, overallBefore: 62.0, overallAfter: 80.1, errorsBefore: 42.8, errorsAfter: 19.4 },
  { group: 'High seniority', ruleBefore: 26.4, ruleAfter: 57.1, overallBefore: 54.5, overallAfter: 71.6, errorsBefore: 63.3, errorsAfter: 30.0 }
];

export const ragResults = [
  { metric: 'Precision@10', graphRag: 0.676, baseline: 0.303 },
  { metric: 'MRR', graphRag: 0.748, baseline: 0.159 },
  { metric: 'nDCG@10', graphRag: 0.690, baseline: 0.237 },
  { metric: 'Hit@10', graphRag: 1.000, baseline: 0.688 },
  { metric: 'Recall@10', graphRag: 0.412, baseline: 0.236 },
  { metric: 'Recall@20', graphRag: 0.695, baseline: 0.388 },
  { metric: 'Recall@27', graphRag: 0.824, baseline: 0.442 },
  { metric: 'Recall@30', graphRag: 0.855, baseline: 0.463 }
];

export const assessResults = [
  { label: 'KOM-Profile cases', value: '120' },
  { label: 'Profile fields', value: '124' },
  { label: 'Mean F1/accuracy', value: '0.382' },
  { label: 'Fully matched fields', value: '31' },
  { label: 'Partially correct fields', value: '25' },
  { label: 'Non-observed/derived fields', value: '68' },
  { label: 'Staging agreement', value: '70.8%' },
  { label: 'Phenotype agreement', value: '73.3%' },
  { label: 'Quadrant agreement', value: '100%' },
  { label: 'Explanation reasonableness', value: '7.47/10' }
];

export const imagingResults = [
  { label: 'QWK', value: '0.806 ± 0.008' },
  { label: 'BACC', value: '0.659' },
  { label: 'Macro-F1', value: '0.664' },
  { label: 'MAE', value: '0.417' },
  { label: 'ECE', value: '0.119' },
  { label: 'sel_acc@80', value: '0.725' }
];

export const riskResults = [
  { label: 'KL progression AUROC', value: '0.817' },
  { label: 'TKR/surgery C-index', value: '0.862' },
  { label: 'Symptom/function worsening AUROC', value: '0.683' }
];
