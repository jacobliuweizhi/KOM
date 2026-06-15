# KOM-Risk retraining protocol FREEZE DRAFT

## 1. Study objective

Retrain KOM-Risk longitudinal risk prediction models for knee OA progression, knee surgery/TKR event, and symptom/function worsening using OAI data with auditable knee-level construction.

## 2. Data source

OAI CSV/SAS/codebook resources only. OAKNet imaging-prediction outputs are excluded from main KOM-Risk model construction.

## 3. Q1-Q4 not used

The Q1-Q4 clinical quadrant system is not used as a training input, split variable, outcome definition, or performance subgroup in the primary KOM-Risk retraining stage.

## 4. No downstream KOM integration analysis

This phase freezes standalone risk-prediction training. Downstream MDT or product integration analyses are deferred until validated model outputs exist.

## 5. Modeling unit

Primary unit: knee-level row. Person-level covariates can be attached to both knees, but both knees from one person must remain in the same split.

## 6. Side-coding restoration

Use file-specific side mapping. Do not assume `1=Right / 2=Left`. Wide right/left field names may be used directly. Numeric `SIDE/SID/MRSIDE/MRKSIDE` fields require codebook or SAS-label evidence.

## 7. Endpoint 1 candidates

- KL grade increase >=1.
- KL grade increase >=2.
- Incident radiographic OA.
- JSN worsening.
- Composite structural progression.

## 8. Endpoint 2 candidates

- TKR-only event.
- Any knee surgery event.
- Survival endpoint with event_time/censor_time if reliably constructible.
- Fixed-horizon binary endpoint if survival time is incomplete.

## 9. Endpoint 3 candidates

- Knee-level WOMAC pain/function worsening.
- KOOS pain/symptom/ADL/QOL worsening.
- MCID-based worsening.
- Person-level sensitivity endpoint if knee-level symptom labels cannot be confirmed.

## 10. Baseline-only primary model

Primary model uses baseline predictors only to avoid leakage from follow-up measurements.

## 11. Early-longitudinal supplementary model

May be added only if visit timing is standardized and leakage controls are explicit.

## 12. Candidate predictor domains

Demographics, baseline symptoms/function, radiographic severity, comorbidities/safety, medication/treatment history, physical activity, psychosocial status and missingness indicators.

## 13. Exclusion rules

Exclude post-baseline variables from baseline-only models, outcome proxies, future treatment variables, OAKNet prediction outputs, and variables without source mapping.

## 14. Leakage prevention

No follow-up outcome, future imaging, future surgery, future medication escalation, or post-event variable may enter baseline models.

## 15. Split rule

Split at person level. Both knees from the same participant remain in the same split.

## 16. Bilateral rule

Do not allow one knee in training and the other knee in validation/test.

## 17. Candidate algorithms

Logistic regression / elastic net, random forest, gradient boosting, LightGBM/CatBoost/XGBoost, CoxPH, random survival forest, gradient boosting survival where appropriate.

## 18. Metrics

Binary endpoints: AUROC, balanced accuracy, sensitivity, specificity, PPV, NPV, calibration, Brier score. Survival endpoints: C-index, time-dependent AUC, Brier, calibration.

## 19. DCA

DCA is a supplementary clinical utility analysis, not the only model-selection standard. If calibration is poor, DCA is not used as a strong conclusion. Binary endpoints can use standard DCA. Survival endpoint DCA requires prespecified time horizons such as 2, 4 and 6 years; if implementation is difficult, report C-index, time-dependent AUC, Brier and calibration first.

## 20. Interpretability

SHAP summary, SHAP dependence, permutation importance, top-feature plausibility audit and individual high-risk explanation may be used. SHAP is predictive explanation, not causal interpretation.

## 21. Posthoc error analysis

Analyze false positives/false negatives by KL grade, age, BMI, sex, side, missingness burden, follow-up length and endpoint definition. Treat this as posthoc, not a primary claim.

## 22. Acceptance standards

Accept a model only if endpoint construction is reproducible, split leakage is prevented, calibration is acceptable, external/holdout performance is stable and feature importance is clinically plausible.

## 23. Must-confirm before training

- File-specific side mapping for numeric SIDE/SID fields.
- Endpoint label definitions and thresholds.
- Person-level split implementation.
- Encoded feature matrix export.
- Model config and random seed logging.
- Sample-level predictions export.
