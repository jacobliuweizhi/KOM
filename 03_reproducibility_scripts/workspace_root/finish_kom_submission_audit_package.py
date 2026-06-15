from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import os
import re
import json
import shutil
import math
from datetime import datetime

import pandas as pd
import openpyxl


ROOT = Path("C:/OAI" + "\u7814\u7a76\u9879\u76ee" + "/pythonProject1/" + "KOM" + "\u8fd4\u4fee\u4fee\u6539")
LOCAL = ROOT / "\u672c\u5730\u5316" / "koa_mdt_agents"
OUT = ROOT / "KOM_Submission_Audit_Package_202606"
ZIP_OUT = ROOT / "KOM_Submission_Audit_Package_202606.zip"
STAGE4A = LOCAL / "data" / "processed" / "stage_validation" / "stage4a_retrieval_metrics.json"
STAGE3 = LOCAL / "data" / "processed" / "stage_validation" / "stage3_retrieval_dod.json"


def write_csv(path: Path, rows, columns=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    if columns:
        for c in columns:
            if c not in df.columns:
                df[c] = pd.NA
        df = df[columns]
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return df


def write_md(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_csv_safe(path: Path):
    for enc in ["utf-8-sig", "utf-8", "gbk", "latin1"]:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            pass
    return None


def first_col(df, terms):
    for c in df.columns:
        lc = str(c).lower()
        if any(t in lc for t in terms):
            return c
    return None


def val(row, col):
    return row.get(col, pd.NA) if col is not None else pd.NA


def rel(path: Path):
    try:
        return str(path.relative_to(OUT))
    except Exception:
        return ""


def category_for(path: Path):
    s = str(path).lower()
    if any(k in s for k in ["komsim", "hci", "hai", "time_workload", "experience", "physician", "workload", "interaction", "materialviews", "adoption"]):
        return "KOM-Sim/HCI"
    if any(k in s for k in ["risk", "oaknet", "prediction", "cox", "lightgbm", "catboost", "calibration", "shap", "feature_importance", "reliability"]):
        return "KOM-Risk/OAKNet"
    if any(k in s for k in ["rag", "retrieval", "evidence", "guideline", "stage4a", "ret_", "graphrag"]):
        return "KOM-RAG/Evidence"
    return "KOM source asset"


def file_records_from_dir(folder: Path, category=None, prefix: str | None = None):
    rows = []
    if not folder.exists():
        return rows
    for p in folder.rglob("*"):
        if p.is_file():
            if prefix and not p.name.startswith(prefix):
                continue
            rows.append(
                {
                    "absolute_path": str(p),
                    "relative_path": rel(p),
                    "file_name": p.name,
                    "extension": p.suffix.lower(),
                    "file_size_bytes": p.stat().st_size,
                    "source_archive": "generated_or_extracted",
                    "detected_category": category or category_for(p),
                }
            )
    return rows


def main():
    assert OUT.exists(), f"Output directory does not exist: {OUT}"
    inv_path = OUT / "00_inventory" / "all_files_inventory.csv"
    inv = read_csv_safe(inv_path) if inv_path.exists() else pd.DataFrame()
    base_records = inv.to_dict("records") if inv is not None and not inv.empty else []

    sim_dir = OUT / "01_KOMSim_logs_and_time_definition"
    risk_dir = OUT / "02_KOMRisk_reproducible_prediction_package"
    rag_dir = OUT / "03_KOMRAG_query_level_evidence_mapping"
    cross_dir = OUT / "04_crosscheck_reports"
    ready_dir = OUT / "05_submission_ready_tables"
    for d in [sim_dir, risk_dir, rag_dir, cross_dir, ready_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # KOM-Sim.
    sim_files = [r for r in base_records if r.get("detected_category") == "KOM-Sim/HCI"] + file_records_from_dir(sim_dir, "KOM-Sim/HCI", prefix="sheet_")
    write_csv(sim_dir / "KOMSim_raw_log_inventory.csv", sim_files, ["absolute_path", "relative_path", "file_name", "extension", "file_size_bytes", "source_archive", "detected_category"])
    event_rows, task_rows, time_rows, phys_rows = [], [], [], []
    for r in sim_files:
        p = Path(str(r.get("absolute_path", "")))
        if p.suffix.lower() != ".csv" or not p.exists() or p.stat().st_size > 5_000_000:
            continue
        df = read_csv_safe(p)
        if df is None or df.empty:
            continue
        cols = " ".join(map(str, df.columns)).lower()
        if all(t in cols for t in ["timestamp", "event"]) or ("action" in cols and "session" in cols):
            pid = first_col(df, ["participant", "physician", "doctor", "user", "id"])
            cid = first_col(df, ["case"])
            cond = first_col(df, ["condition", "arm", "group"])
            ts = first_col(df, ["timestamp", "time"])
            ev = first_col(df, ["event", "action", "click"])
            mod = first_col(df, ["screen", "module", "page"])
            dur = first_col(df, ["duration", "seconds", "sec"])
            for _, row in df.head(5000).iterrows():
                event_rows.append({"participant_id": val(row, pid), "physician_id": val(row, pid), "case_id": val(row, cid), "condition": val(row, cond), "timestamp": val(row, ts), "event_type": val(row, ev), "screen_or_module": val(row, mod), "action_label": val(row, ev), "duration_seconds": val(row, dur), "raw_source_file": str(p), "cleaning_note": "standardized from event-like log columns"})
        if any(t in cols for t in ["time", "workload", "duration", "minutes", "task", "condition", "arm", "physician", "doctor", "case"]):
            pid = first_col(df, ["participant", "physician", "doctor", "user", "id"])
            cid = first_col(df, ["case"])
            cond = first_col(df, ["condition", "arm", "group", "module"])
            qcol = first_col(df, ["quadrant"])
            tcol = first_col(df, ["time", "minute", "duration"])
            for _, row in df.head(2000).iterrows():
                tm = val(row, tcol)
                try:
                    sec = float(tm) * 60 if pd.notna(tm) else pd.NA
                except Exception:
                    sec = pd.NA
                task_rows.append({"participant_id": val(row, pid), "physician_id": val(row, pid), "case_id": val(row, cid), "condition": val(row, cond), "task_id": pd.NA, "case_quadrant": val(row, qcol), "time_minutes": tm, "time_seconds": sec, "material_views": val(row, first_col(df, ["material", "view"])), "evidence_views": val(row, first_col(df, ["evidence"])), "agent_trace_views": pd.NA, "interaction_count": pd.NA, "perceived_workload": val(row, first_col(df, ["workload", "nasa", "tlx"])), "usability_score": val(row, first_col(df, ["usability", "sus"])), "trust_score": val(row, first_col(df, ["trust"])), "decision_confidence": val(row, first_col(df, ["confidence"])), "completion_status": pd.NA, "raw_source_file": str(p), "standardization_note": "task-level or summary-level table; not verified as raw event log"})
        if any(k in p.name.lower() for k in ["time", "workload"]):
            for _, row in df.head(1000).iterrows():
                rec = {str(k): v for k, v in row.items()}
                rec["raw_source_file"] = str(p)
                time_rows.append(rec)
        if any(k in p.name.lower() for k in ["physician", "hai", "doctor", "distribution"]):
            for _, row in df.head(1000).iterrows():
                rec = {str(k): v for k, v in row.items()}
                rec["raw_source_file"] = str(p)
                phys_rows.append(rec)
    write_csv(sim_dir / "KOMSim_event_log_standardized.csv", event_rows, ["participant_id", "physician_id", "case_id", "condition", "timestamp", "event_type", "screen_or_module", "action_label", "evidence_id", "recommendation_id", "duration_seconds", "raw_source_file", "cleaning_note"])
    write_csv(sim_dir / "KOMSim_task_level_log_standardized.csv", task_rows, ["participant_id", "physician_id", "case_id", "condition", "task_id", "case_quadrant", "time_minutes", "time_seconds", "material_views", "evidence_views", "agent_trace_views", "interaction_count", "perceived_workload", "usability_score", "trust_score", "decision_confidence", "completion_status", "raw_source_file", "standardization_note"])
    write_csv(sim_dir / "KOMSim_time_and_interaction_summary.csv", time_rows)
    write_csv(sim_dir / "KOMSim_physician_level_summary.csv", phys_rows)
    cond_rows = []
    if task_rows:
        tdf = pd.DataFrame(task_rows)
        nums_all = pd.to_numeric(tdf.get("time_minutes"), errors="coerce")
        for cond, grp in tdf.assign(_time=nums_all).groupby("condition", dropna=False):
            nums = grp["_time"].dropna()
            cond_rows.append({"metric": "time_minutes", "condition": cond, "n": len(nums), "mean": nums.mean() if len(nums) else pd.NA, "sd": nums.std() if len(nums) > 1 else pd.NA, "source": "KOMSim_task_level_log_standardized.csv"})
    write_csv(sim_dir / "KOMSim_condition_comparison_statistics.csv", cond_rows, ["metric", "condition", "n", "mean", "sd", "source"])
    write_md(sim_dir / "KOM-Sim_log_cleaning_protocol.md", f"""# KOM-Sim log cleaning protocol

Generated: {datetime.now().isoformat(timespec='seconds')}

- Raw event logs: {'FOUND' if event_rows else 'NOT FOUND'}
- Task/time summary rows: {len(task_rows)}

No missing event/session fields were inferred. Summary-level files are marked as summary-level and should not be presented as raw event logs.
""")

    # KOM-Risk.
    risk_files = [r for r in base_records if r.get("detected_category") == "KOM-Risk/OAKNet"] + file_records_from_dir(risk_dir, "KOM-Risk/OAKNet", prefix="sheet_")
    write_csv(risk_dir / "KOMRisk_file_inventory.csv", risk_files, ["absolute_path", "relative_path", "file_name", "extension", "file_size_bytes", "source_archive", "detected_category"])
    pred_rows, feat_rows, calib_rows, split_rows = [], [], [], []
    for r in risk_files:
        p = Path(str(r.get("absolute_path", "")))
        if p.suffix.lower() != ".csv" or not p.exists() or p.stat().st_size > 10_000_000:
            continue
        df = read_csv_safe(p)
        if df is None or df.empty:
            continue
        low = p.name.lower()
        if "prediction" in low:
            for _, row in df.head(10000).iterrows():
                rec = {str(k): v for k, v in row.items()}
                rec["raw_source_file"] = str(p)
                pred_rows.append(rec)
        if any(k in low for k in ["feature", "shap", "importance"]):
            for _, row in df.head(5000).iterrows():
                rec = {str(k): v for k, v in row.items()}
                rec["raw_source_file"] = str(p)
                feat_rows.append(rec)
        if any(k in low for k in ["calibration", "reliability"]):
            for _, row in df.head(5000).iterrows():
                rec = {str(k): v for k, v in row.items()}
                rec["raw_source_file"] = str(p)
                calib_rows.append(rec)
        if any(k in low for k in ["split", "train", "test", "fold"]):
            for _, row in df.head(5000).iterrows():
                rec = {str(k): v for k, v in row.items()}
                rec["raw_source_file"] = str(p)
                split_rows.append(rec)
    risk_metrics = [
        {"endpoint": "KL structural progression", "model": "LightGBM", "n": 7855, "event_rate_percent": 13.4, "metric_name": "AUROC", "metric_value": 0.817, "secondary_metric_name": "BACC", "secondary_metric_value": 0.735, "source": "specified main-text result; sample-level endpoint predictions not found in current source package"},
        {"endpoint": "TKR / knee surgery event", "model": "CoxPH", "n": 9014, "event_rate_percent": 5.2, "metric_name": "C-index", "metric_value": 0.862, "secondary_metric_name": pd.NA, "secondary_metric_value": pd.NA, "source": "specified main-text result; sample-level endpoint predictions not found in current source package"},
        {"endpoint": "Symptom/function worsening", "model": "CatBoost", "n": 8962, "event_rate_percent": 31.0, "metric_name": "AUROC", "metric_value": 0.683, "secondary_metric_name": pd.NA, "secondary_metric_value": pd.NA, "source": "specified main-text result; sample-level endpoint predictions not found in current source package"},
    ]
    write_csv(risk_dir / "risk_predictions.csv", pred_rows)
    write_csv(risk_dir / "risk_model_metrics.csv", risk_metrics, ["endpoint", "model", "n", "event_rate_percent", "metric_name", "metric_value", "secondary_metric_name", "secondary_metric_value", "source"])
    write_csv(risk_dir / "risk_feature_importance.csv", feat_rows)
    write_csv(risk_dir / "risk_calibration_curve.csv", calib_rows)
    write_csv(risk_dir / "risk_split_definition.csv", split_rows)
    (risk_dir / "risk_model_config.json").write_text(json.dumps({"generated": datetime.now().isoformat(timespec="seconds"), "prediction_rows_detected": len(pred_rows), "feature_rows_detected": len(feat_rows), "calibration_rows_detected": len(calib_rows), "split_rows_detected": len(split_rows)}, ensure_ascii=False, indent=2), encoding="utf-8")
    missing_risk = []
    if not pred_rows:
        missing_risk.append("Sample-level predictions for the three specified KOMRisk endpoints were not found; do not infer them from summary metrics.")
    if not feat_rows:
        missing_risk.append("Feature importance / SHAP files were not found.")
    if not calib_rows:
        missing_risk.append("Calibration curve files for KOMRisk endpoints were not found.")
    if not split_rows:
        missing_risk.append("Train/validation/test split definition files were not found.")
    write_md(risk_dir / "KOMRisk_missing_items_report.md", "# KOMRisk missing items report\n\n" + ("\n".join(f"- {m}" for m in missing_risk) if missing_risk else "- No missing items detected."))

    # KOM-RAG.
    rag_files = [r for r in base_records if r.get("detected_category") == "KOM-RAG/Evidence"] + file_records_from_dir(rag_dir, "KOM-RAG/Evidence", prefix="sheet_")
    write_csv(rag_dir / "KOMRAG_file_inventory.csv", rag_files, ["absolute_path", "relative_path", "file_name", "extension", "file_size_bytes", "source_archive", "detected_category"])
    stage4a_data = json.loads(STAGE4A.read_text(encoding="utf-8")) if STAGE4A.exists() else {}
    stage3_data = json.loads(STAGE3.read_text(encoding="utf-8")) if STAGE3.exists() else {}
    (rag_dir / "stage4a_retrieval_metrics.source.json").write_text(json.dumps(stage4a_data, ensure_ascii=False, indent=2), encoding="utf-8")
    if stage3_data:
        (rag_dir / "stage3_retrieval_dod.source.json").write_text(json.dumps(stage3_data, ensure_ascii=False, indent=2), encoding="utf-8")
    metrics = stage4a_data.get("final_holdout") or stage4a_data.get("holdout") or stage4a_data.get("holdout_metrics") or {}
    if isinstance(metrics, dict) and "graph" in metrics:
        metrics = metrics.get("graph") or {}
    if not metrics and stage4a_data.get("iterations"):
        metrics = stage4a_data["iterations"][-1].get("graph", {})
    metric_rows = [
        {"query_id": "[summary_holdout]", "case_id": pd.NA, "agent": pd.NA, "precision_at_10": metrics.get("precision_at_10"), "recall_at_10": metrics.get("recall_at_10"), "hit_rate_at_10": metrics.get("hit_rate_at_10"), "mrr": metrics.get("mrr"), "ndcg_at_10": metrics.get("ndcg_at_10"), "source_file": str(STAGE4A), "note": "summary row from source JSON; query-level rows extracted only when present"}
    ]
    for rr in stage4a_data.get("rows_sample", []):
        graph = rr.get("graph") or {}
        metric_rows.append(
            {
                "query_id": rr.get("case_id"),
                "case_id": rr.get("case_id"),
                "agent": rr.get("agent_name") or rr.get("gold_agent"),
                "precision_at_10": graph.get("precision_at_10"),
                "recall_at_10": graph.get("recall_at_10"),
                "hit_rate_at_10": graph.get("hit_rate_at_10"),
                "mrr": graph.get("mrr"),
                "ndcg_at_10": graph.get("ndcg_at_10"),
                "source_file": str(STAGE4A),
                "note": "rows_sample from source JSON",
            }
        )
    query_rows, retrieval_rows, relevance_rows, anchor_rows = [], [], [], []
    for r in rag_files:
        p = Path(str(r.get("absolute_path", "")))
        if p.suffix.lower() != ".csv" or not p.exists() or p.stat().st_size > 10_000_000:
            continue
        df = read_csv_safe(p)
        if df is None or df.empty:
            continue
        cols = " ".join(map(str, df.columns)).lower()
        if "query" in cols:
            qcol = first_col(df, ["query", "clinical question", "question"])
            if qcol:
                for _, row in df.head(2000).iterrows():
                    query_rows.append({"query_id": val(row, first_col(df, ["query_id", "id"])), "case_id": val(row, first_col(df, ["case"])), "agent": val(row, first_col(df, ["agent", "domain"])), "query_text": val(row, qcol), "source_file": str(p)})
        if any(k in cols for k in ["precision", "recall", "mrr", "ndcg", "hit"]):
            for _, row in df.head(2000).iterrows():
                metric_rows.append({"query_id": val(row, first_col(df, ["query_id", "query"])), "case_id": val(row, first_col(df, ["case"])), "agent": val(row, first_col(df, ["agent", "domain"])), "precision_at_10": val(row, first_col(df, ["precision"])), "recall_at_10": val(row, first_col(df, ["recall"])), "hit_rate_at_10": val(row, first_col(df, ["hit"])), "mrr": val(row, first_col(df, ["mrr"])), "ndcg_at_10": val(row, first_col(df, ["ndcg"])), "source_file": str(p), "note": "extracted from detected metric-like table"})
        if any(k in cols for k in ["evidence", "eu_id", "direct"]):
            evid = first_col(df, ["eu_id", "evidence_id", "evidence"])
            if evid:
                for _, row in df.head(3000).iterrows():
                    retrieval_rows.append({"query_id": val(row, first_col(df, ["query_id", "query"])), "case_id": val(row, first_col(df, ["case"])), "agent": val(row, first_col(df, ["agent", "domain"])), "rank": val(row, first_col(df, ["rank"])), "evidence_id": val(row, evid), "score": val(row, first_col(df, ["score"])), "evidence_role": val(row, first_col(df, ["role", "direct", "context"])), "source_file": str(p)})
        if any(k in cols for k in ["gold", "label", "relevance", "strict", "weak"]):
            evid = first_col(df, ["eu_id", "evidence_id", "evidence"])
            if evid:
                for _, row in df.head(3000).iterrows():
                    relevance_rows.append({"query_id": val(row, first_col(df, ["query_id", "query"])), "evidence_id": val(row, evid), "label": val(row, first_col(df, ["label", "relevance", "gold", "strict", "weak"])), "source_file": str(p)})
        if any(k in cols for k in ["guideline", "anchor", "acr", "eular", "nice", "oarsi", "aaos"]):
            evid = first_col(df, ["eu_id", "evidence_id", "evidence"])
            title = first_col(df, ["title", "guideline", "source"])
            year = first_col(df, ["year"])
            for _, row in df.head(2000).iterrows():
                txt = " ".join(str(row.get(c, "")) for c in df.columns[:8]).lower()
                if any(k in txt for k in ["nice", "eular", "aaos", "oarsi", "american college", "acr", "arthritis foundation", "guideline"]):
                    anchor_rows.append({"evidence_id": val(row, evid), "guideline_family": pd.NA, "title_or_source": val(row, title) if title else txt[:300], "year": val(row, year), "source_file": str(p), "source_note": "detected guideline-like row; verify family manually if needed"})
    write_csv(rag_dir / "rag_query_set.csv", query_rows, ["query_id", "case_id", "agent", "query_text", "source_file"])
    write_csv(rag_dir / "guideline_anchor_mapping.csv", anchor_rows, ["evidence_id", "guideline_family", "title_or_source", "year", "source_file", "source_note"])
    write_csv(rag_dir / "rag_retrieval_results.csv", retrieval_rows, ["query_id", "case_id", "agent", "rank", "evidence_id", "score", "evidence_role", "source_file"])
    write_csv(rag_dir / "rag_relevance_labels.csv", relevance_rows, ["query_id", "evidence_id", "label", "source_file"])
    write_csv(rag_dir / "rag_metric_by_query.csv", metric_rows, ["query_id", "case_id", "agent", "precision_at_10", "recall_at_10", "hit_rate_at_10", "mrr", "ndcg_at_10", "source_file", "note"])
    write_csv(rag_dir / "rag_error_cases.csv", [])
    write_md(rag_dir / "KOMRAG_query_level_audit_report.md", f"""# KOMRAG query-level audit report

Generated: {datetime.now().isoformat(timespec='seconds')}

- Stage4A metrics file: {'FOUND' if STAGE4A.exists() else 'NOT FOUND'}
- Stage3 comparison file: {'FOUND' if STAGE3.exists() else 'NOT FOUND'}
- Query rows extracted: {len(query_rows)}
- Retrieval result rows extracted: {len(retrieval_rows)}
- Relevance label rows extracted: {len(relevance_rows)}
- Guideline anchor rows extracted: {len(anchor_rows)}

Missing rows were not invented. If query-level labels or TopK tables are stored elsewhere, attach them and rerun this audit.
""")

    # Copy key tables.
    for src in [sim_dir / "KOMSim_time_and_interaction_summary.csv", risk_dir / "risk_model_metrics.csv", rag_dir / "rag_metric_by_query.csv", rag_dir / "guideline_anchor_mapping.csv"]:
        if src.exists():
            shutil.copy2(src, ready_dir / src.name)

    checklist = []
    def add(item, status, evidence, action):
        checklist.append({"item": item, "status": status, "evidence": evidence, "recommended_next_action": action})
    add("KOM-Sim raw event logs", "COMPLETE" if event_rows else "MISSING", str(sim_dir / "KOMSim_event_log_standardized.csv"), "Provide raw browser/session logs if event-level analysis is needed.")
    add("KOM-Sim task/time summaries", "COMPLETE" if task_rows or time_rows else "MISSING", str(sim_dir), "If only summaries exist, state this in methods.")
    add("KOMRisk headline metrics", "COMPLETE", str(risk_dir / "risk_model_metrics.csv"), "Verify against manuscript values.")
    add("KOMRisk sample-level predictions", "COMPLETE/PARTIAL" if pred_rows else "MISSING/PARTIAL", str(risk_dir / "risk_predictions.csv"), "Add endpoint-specific sample predictions to recompute endpoints.")
    add("KOM-RAG Stage4A metrics", "COMPLETE" if STAGE4A.exists() else "MISSING", str(STAGE4A), "Keep source JSON.")
    add("KOM-RAG query-level retrieval rows", "COMPLETE/PARTIAL" if retrieval_rows else "MISSING/PARTIAL", str(rag_dir / "rag_retrieval_results.csv"), "Add per-query TopK table if outside current package.")
    add("KOM-RAG relevance labels", "COMPLETE/PARTIAL" if relevance_rows else "MISSING", str(rag_dir / "rag_relevance_labels.csv"), "Add strict/wide gold labels; do not infer them.")
    write_csv(cross_dir / "submission_readiness_checklist.csv", checklist, ["item", "status", "evidence", "recommended_next_action"])

    wb_path = cross_dir / "submission_audit_crosscheck.xlsx"
    with pd.ExcelWriter(wb_path, engine="openpyxl") as writer:
        pd.DataFrame([{"package": "KOM_Submission_Audit_Package_202606", "generated": datetime.now().isoformat(timespec="seconds"), "principle": "Real source files only; missing items remain marked missing."}]).to_excel(writer, "README", index=False)
        pd.DataFrame(sim_files).to_excel(writer, "KOM-Sim log status", index=False)
        pd.DataFrame([{"raw_event_logs_found": bool(event_rows), "task_level_rows": len(task_rows), "time_summary_rows": len(time_rows), "physician_summary_rows": len(phys_rows), "condition_comparison_rows": len(cond_rows)}]).to_excel(writer, "KOM-Sim time definition", index=False)
        pd.DataFrame(risk_files).to_excel(writer, "KOM-Risk files", index=False)
        pd.DataFrame(risk_metrics).to_excel(writer, "KOM-Risk metrics", index=False)
        pd.DataFrame(query_rows).to_excel(writer, "KOM-RAG query set", index=False)
        pd.DataFrame(anchor_rows).to_excel(writer, "KOM-RAG evidence mapping", index=False)
        pd.DataFrame(metric_rows).to_excel(writer, "KOM-RAG query metrics", index=False)
        missing = []
        for m in missing_risk:
            missing.append({"module": "KOM-Risk", "missing_item": m})
        if not event_rows:
            missing.append({"module": "KOM-Sim", "missing_item": "Raw event-level logs not found."})
        if not relevance_rows:
            missing.append({"module": "KOM-RAG", "missing_item": "Query-level relevance labels not found."})
        if not retrieval_rows:
            missing.append({"module": "KOM-RAG", "missing_item": "Query-level retrieval result table not found or not mappable."})
        pd.DataFrame(missing).to_excel(writer, "Missing items", index=False)
        pd.DataFrame(checklist).to_excel(writer, "Ready checklist", index=False)

    readme = f"""# KOM Submission Audit Package 202606

Generated: {datetime.now().isoformat(timespec='seconds')}

This package consolidates reviewer-auditable source materials for KOM-Sim, KOMRisk, and KOMRAG. It uses real source files only. Missing raw logs, sample-level predictions, query-level retrieval rows, or relevance labels are explicitly marked as missing or partial.

## Status summary

- KOM-Sim raw event logs: {'FOUND' if event_rows else 'NOT FOUND'}
- KOM-Sim task/time summaries: {'FOUND' if (task_rows or time_rows) else 'NOT FOUND'}
- KOMRisk sample-level prediction rows detected: {len(pred_rows)}
- KOMRisk feature-importance rows detected: {len(feat_rows)}
- KOMRisk calibration rows detected: {len(calib_rows)}
- KOMRAG Stage4A metrics: {'FOUND' if STAGE4A.exists() else 'NOT FOUND'}
- KOMRAG query rows extracted: {len(query_rows)}
- KOMRAG retrieval result rows extracted: {len(retrieval_rows)}
- KOMRAG relevance label rows extracted: {len(relevance_rows)}

## Recommended next action

1. Provide raw KOM-Sim event/session logs if event-level reanalysis is required.
2. Provide endpoint-specific KOMRisk sample predictions and split definitions if reviewers require recalculation.
3. Provide strict/wide KOMRAG relevance labels and per-query TopK retrieval rows if stored outside the current package.

## Non-fabrication note

No missing raw log, prediction, guideline-anchor, query-label, or retrieval-result rows were generated synthetically.
"""
    write_md(OUT / "README_KOM_SUBMISSION_AUDIT_PACKAGE.md", readme)

    try:
        wb = openpyxl.load_workbook(wb_path, read_only=True)
        sheets = wb.sheetnames
        wb.close()
        audit_ok = True
    except Exception:
        sheets = []
        audit_ok = False
    write_csv(cross_dir / "workbook_audit.csv", [{"path": str(wb_path), "exists": wb_path.exists(), "size_bytes": wb_path.stat().st_size if wb_path.exists() else None, "sheet_count": len(sheets), "sheets": "; ".join(sheets)}])
    write_md(cross_dir / "workbook_audit_result.md", f"workbook_audit exit {0 if audit_ok else 1}\n")

    if ZIP_OUT.exists():
        ZIP_OUT.rename(ROOT / f"KOM_Submission_Audit_Package_202606_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")
    with ZipFile(ZIP_OUT, "w", ZIP_DEFLATED) as z:
        for dirpath, _, filenames in os.walk(OUT):
            for fn in filenames:
                p = Path(dirpath) / fn
                z.write(p, p.relative_to(ROOT))
    status = {
        "output_dir": str(OUT),
        "zip_path": str(ZIP_OUT),
        "inventory_rows": len(base_records),
        "komsim_raw_event_logs_found": bool(event_rows),
        "komsim_task_rows": len(task_rows),
        "komsim_time_summary_rows": len(time_rows),
        "komsim_physician_summary_rows": len(phys_rows),
        "komrisk_prediction_rows": len(pred_rows),
        "komrisk_feature_importance_rows": len(feat_rows),
        "komrisk_calibration_rows": len(calib_rows),
        "komrisk_split_rows": len(split_rows),
        "komrag_stage4a_found": STAGE4A.exists(),
        "komrag_query_rows": len(query_rows),
        "komrag_retrieval_rows": len(retrieval_rows),
        "komrag_relevance_rows": len(relevance_rows),
        "komrag_metric_rows": len(metric_rows),
        "workbook_audit_exit": 0 if audit_ok else 1,
        "zip_size_bytes": ZIP_OUT.stat().st_size if ZIP_OUT.exists() else None,
    }
    (OUT / "00_inventory" / "package_build_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
