# KOM Figure Deep Optimization Audit

- Output folder: `C:\Users\Liu\Documents\医学科研专用项目内容\KOM_Figure_Deep_Optimization_20260615`
- Master table: `C:\Users\Liu\Documents\医学科研专用项目内容\KOM_Figure_Deep_Optimization_20260615\tables\KOM_Figure_Deep_Optimization_Master_Table_20260615.xlsx`
- Figure files generated: 246 figure records, each exported as PNG/SVG/PDF when applicable.
- QC: PASS=246, REVIEW=0, FAIL=0.
- No-title rule: plotting functions do not set panel titles; file names and source tables carry the semantic label.
- Same-direction radar rule: lower-better metrics are inverted by within-comparison min-max normalization before polar plotting.
- Axis rule: bar/process/metric figures are exported in both dynamic and zero-baseline variants where meaningful.
- Quadrant rule: no Q1/Q2/Q3/Q4 quadrant panel is generated; raw case IDs are not used as figure labels.

## Methods Result Map
| module      | methods_required_result                                                         | status         | source_or_gap                                                           |
|:------------|:--------------------------------------------------------------------------------|:---------------|:------------------------------------------------------------------------|
| KOM-Profile | field extraction accuracy / completeness                                        | gap_or_partial | No directly recovered metric table in current files                     |
| OAK-Net     | QWK, balanced accuracy, macro-F1, MAE, ECE, selective accuracy, training curves | available      | oaknet_metrics_summary; oaknet_training_history_long                    |
| KOM-Risk    | AUROC, AUPRC, Brier, calibration, DCA, SHAP, thresholds                         | available      | komrisk_mode_performance; komrisk_threshold_metrics; komrisk_shap_top   |
| KOM-RAG     | Precision@10, Recall@K, Hit@10, MRR, nDCG@10; generation faithfulness           | gap_or_partial | No GraphRAG retrieval/generation metric table recovered in project root |
| KOM-Treat   | Full / without RAG / without MDT / Direct LLM ablation                          | gap_or_partial | No treatment-agent judge summary recovered in project root              |
| KOM-Sim     | case ratings, workload, process behavior, final survey                          | available      | hci_case_ratings; hci_stage_workload; hci_case_level; hci_final_survey  |
| KOM-Safe    | safety errors, red flag challenge set                                           | gap_or_partial | No dedicated safety challenge result table recovered                    |

## Remaining Real-Data Gaps
| module      | item                                                                  | status                     | detail                                                                  |
|:------------|:----------------------------------------------------------------------|:---------------------------|:------------------------------------------------------------------------|
| KOM-Profile | field extraction accuracy / completeness                              | source table not recovered | No directly recovered metric table in current files                     |
| KOM-RAG     | Precision@10, Recall@K, Hit@10, MRR, nDCG@10; generation faithfulness | source table not recovered | No GraphRAG retrieval/generation metric table recovered in project root |
| KOM-Treat   | Full / without RAG / without MDT / Direct LLM ablation                | source table not recovered | No treatment-agent judge summary recovered in project root              |
| KOM-Safe    | safety errors, red flag challenge set                                 | source table not recovered | No dedicated safety challenge result table recovered                    |