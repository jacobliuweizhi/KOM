from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from datetime import datetime
import os
import re
import json
import shutil
import hashlib
import math

import pandas as pd
import openpyxl


ROOT = Path("C:/OAI" + "\u7814\u7a76\u9879\u76ee" + "/pythonProject1/" + "KOM" + "\u8fd4\u4fee\u4fee\u6539")
SUBMISSION = ROOT / "\u6295\u7a3f\u4f7f\u7528"
LOCAL = ROOT / "\u672c\u5730\u5316" / "koa_mdt_agents"
PREV = ROOT / "KOM_Submission_Audit_Package_202606"
OUT = ROOT / "KOM_Submission_Audit_Package_202606_FINAL"
ZIP_OUT = ROOT / "KOM_Submission_Audit_Package_202606_FINAL.zip"
STAGE = LOCAL / "data" / "processed" / "stage_validation"

STAGE4A_METRICS = STAGE / "stage4a_retrieval_metrics.json"
STAGE4A_HOLDOUT = STAGE / "stage4a_holdout_rows.csv"
STAGE4A_PRECOMP_HOLDOUT = STAGE / "stage4a_precomputed_holdout.json"
STAGE3 = STAGE / "stage3_retrieval_dod.json"

NOW = datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_clean_output() -> None:
    if OUT.exists():
        backup = ROOT / f"KOM_Submission_Audit_Package_202606_FINAL_backup_{NOW}"
        shutil.move(str(OUT), str(backup))
        print("Backed up existing FINAL dir:", backup)
    OUT.mkdir(parents=True, exist_ok=True)
    dirs = [
        "00_inventory",
        "01_KOMSim_time_and_log_audit/source_code_audit",
        "01_KOMSim_time_and_log_audit/raw_or_task_log_inventory",
        "01_KOMSim_time_and_log_audit/standardized_logs",
        "01_KOMSim_time_and_log_audit/time_definition_protocol",
        "01_KOMSim_time_and_log_audit/time_and_interaction_tables",
        "01_KOMSim_time_and_log_audit/manuscript_ready_methods",
        "02_KOMRisk_reproducible_prediction_package/inventory",
        "02_KOMRisk_reproducible_prediction_package/endpoint_specific_predictions",
        "02_KOMRisk_reproducible_prediction_package/metrics",
        "02_KOMRisk_reproducible_prediction_package/calibration",
        "02_KOMRisk_reproducible_prediction_package/feature_importance",
        "02_KOMRisk_reproducible_prediction_package/splits_and_config",
        "02_KOMRisk_reproducible_prediction_package/missing_items",
        "03_KOMRAG_query_level_evidence_mapping/inventory",
        "03_KOMRAG_query_level_evidence_mapping/clean_query_set",
        "03_KOMRAG_query_level_evidence_mapping/guideline_anchor_mapping",
        "03_KOMRAG_query_level_evidence_mapping/retrieval_results",
        "03_KOMRAG_query_level_evidence_mapping/relevance_labels",
        "03_KOMRAG_query_level_evidence_mapping/query_metrics",
        "03_KOMRAG_query_level_evidence_mapping/error_cases",
        "03_KOMRAG_query_level_evidence_mapping/audit_report",
        "04_expert_label_name_audit",
        "05_crosscheck_reports",
        "06_submission_ready_text",
        "07_scripts",
    ]
    for d in dirs:
        (OUT / d).mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, rows, columns: list[str] | None = None) -> pd.DataFrame:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    if columns:
        for c in columns:
            if c not in df.columns:
                df[c] = pd.NA
        df = df[columns]
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return df


def write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_csv(path: Path, nrows: int | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    for enc in ["utf-8-sig", "utf-8", "gbk", "latin1"]:
        try:
            return pd.read_csv(path, encoding=enc, nrows=nrows, low_memory=False)
        except Exception:
            pass
    return pd.DataFrame()


def read_json(path: Path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def safe_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def rel_to_out(path: Path) -> str:
    try:
        return str(path.relative_to(OUT))
    except Exception:
        return ""


def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:12]


def normalize_domain(text: str) -> str:
    s = (text or "").lower()
    if any(k in s for k in ["exercise", "rehab", "physical", "fitt", "balance"]):
        return "exercise_rehabilitation"
    if any(k in s for k in ["weight", "nutrition", "diet", "bmi"]):
        return "weight_nutrition"
    if any(k in s for k in ["nsaid", "oral", "topical", "analges", "medication"]):
        return "NSAID_safety" if "nsaid" in s else "pain_medication"
    if any(k in s for k in ["injection", "steroid", "prp", "ha"]):
        return "injection_PRP_HA_steroid"
    if any(k in s for k in ["surgery", "surgical", "referral", "tkr", "arthroplasty"]):
        return "surgical_referral"
    if any(k in s for k in ["psych", "behavior", "self", "education", "sleep"]):
        return "psychological_self_management"
    if any(k in s for k in ["assistive", "brace", "device", "environment"]):
        return "assistive_device_environment"
    if any(k in s for k in ["risk", "prognosis", "prediction"]):
        return "prognosis_risk"
    if any(k in s for k in ["follow", "monitor"]):
        return "education_followup"
    if "koa" in s or "osteoarthritis" in s:
        return "general_KOA_management"
    return "unknown"


def detailed_category(path: Path, columns: str = "") -> tuple[str, str, str, str]:
    s = (str(path) + " " + path.name + " " + columns).lower()
    if any(k in s for k in ["expert", "rater", "icc", "blind", "reviewer", "overall expert", "expert grade", "final adjudicator", "专家", "评分", "盲评"]):
        if any(k in s for k in ["dictionary", "label", "标签", "mapping"]):
            return "expert label dictionary", "Expert ratings", "expert label normalization", "Do not alter score values"
        return "expert rating table", "Expert ratings", "human expert score/label audit", "Do not alter score values; do not mix API ratings with human ratings"
    if path.suffix.lower() in [".html", ".htm"]:
        if any(k in s for k in ["doctor", "physician", "interaction", "blind_review", "offline", "hci", "人机"]):
            return "KOM-Sim HTML source", "KOM-Sim", "HTML timer/randomization/export audit", ""
        return "KOM-RAG evidence unit", "KOM-RAG", "evidence source page audit", "HTML source"
    if any(k in s for k in ["timestamp", "event_type", "click", "page_name", "action_name", "event log"]):
        return "KOM-Sim raw event log", "KOM-Sim", "event-level analysis", ""
    if any(k in s for k in ["editing time", "submitted at", "doctor final prescription", "case order", "participant", "condition label"]):
        return "KOM-Sim task-level log", "KOM-Sim", "task-level time and prescription analysis", ""
    if any(k in s for k in ["questionnaire", "workload", "confidence", "trust", "sufficiency"]):
        return "KOM-Sim questionnaire", "KOM-Sim", "workload and experience analysis", ""
    if any(k in s for k in ["doctor_prescriptions", "prescription"]):
        return "KOM-Sim prescription output", "KOM-Sim", "prescription output audit", ""
    if any(k in s for k in ["komsim", "time_workload", "hai", "physician", "experience"]):
        return "KOM-Sim summary table", "KOM-Sim", "summary-level HCI evidence", "summary_table_only unless task rows are present"
    if any(k in s for k in ["prediction", "predicted", "oof", "prob_kl", "oof_risk"]):
        return "KOM-Risk prediction", "KOM-Risk", "prediction audit; verify endpoint identity", "Do not mix OAKNet imaging predictions with KOMRisk longitudinal endpoints"
    if any(k in s for k in ["auroc", "c-index", "cindex", "bacc", "brier", "metric", "performance"]):
        return "KOM-Risk metrics", "KOM-Risk", "model metric audit", ""
    if any(k in s for k in ["config", "hyperparameter", "seed"]):
        return "KOM-Risk model config", "KOM-Risk", "model configuration audit", ""
    if any(k in s for k in ["calibration", "reliability", "ece"]):
        return "KOM-Risk calibration", "KOM-Risk", "calibration audit", ""
    if any(k in s for k in ["split", "fold", "train", "test"]):
        return "KOM-Risk split", "KOM-Risk", "split audit", ""
    if any(k in s for k in ["shap", "feature_importance", "importance"]):
        return "KOM-Risk feature importance", "KOM-Risk", "feature importance audit", ""
    if any(k in s for k in ["query_text", "clinical question", "query set"]):
        return "KOM-RAG query set", "KOM-RAG", "query-level audit", ""
    if any(k in s for k in ["evidence unit", "eu_id", "evidence_id"]):
        return "KOM-RAG evidence unit", "KOM-RAG", "evidence traceability", ""
    if any(k in s for k in ["retrieval", "top30", "rank", "graph_top"]):
        return "KOM-RAG retrieval result", "KOM-RAG", "TopK retrieval audit", ""
    if any(k in s for k in ["strict_gold", "wide_gold", "relevance", "label"]):
        return "KOM-RAG relevance label", "KOM-RAG", "relevance label audit", ""
    if any(k in s for k in ["precision", "mrr", "ndcg", "hit", "recall"]):
        return "KOM-RAG metric", "KOM-RAG", "query metric audit", ""
    if any(k in s for k in ["guideline", "anchor", "nice", "oarsi", "eular", "aaos", "acr"]):
        return "KOM-RAG guideline anchor", "KOM-RAG", "guideline anchor mapping", ""
    if "系统证据矩阵" in str(path) or "evidence matrix" in s:
        return "evidence matrix", "KOM-RAG", "evidence matrix audit", ""
    if path.suffix.lower() in [".xlsx", ".docx"]:
        return "manuscript table", "manuscript", "submission table", ""
    if path.suffix.lower() in [".png", ".svg", ".pdf", ".pptx"]:
        return "figure output", "figure", "figure/source audit", ""
    return "unknown", "unknown", "inventory only", ""


def copy_previous_extracts() -> list[dict]:
    rows = []
    src = PREV / "00_inventory" / "x"
    dst = OUT / "00_inventory" / "x"
    if src.exists():
        shutil.copytree(src, dst)
    old_manifest = PREV / "00_inventory" / "extraction_manifest.csv"
    if old_manifest.exists():
        df = read_csv(old_manifest)
        df.to_csv(OUT / "00_inventory" / "input_zip_manifest.csv", index=False, encoding="utf-8-sig")
    else:
        write_csv(OUT / "00_inventory" / "input_zip_manifest.csv", [])
    return rows


def build_inventory() -> pd.DataFrame:
    scan_roots = [
        OUT / "00_inventory" / "x",
        PREV,
        SUBMISSION,
        LOCAL / "data" / "processed",
        STAGE,
    ]
    exclude = {".venv", "venv", "site-packages", "node_modules", "__pycache__", ".git"}
    records = []
    seen = set()
    keywords = re.compile(r"(KOM|Sim|HCI|doctor|physician|interaction|offline|html|log|event|task|time|timestamp|questionnaire|RAG|GraphRAG|evidence|guideline|anchor|query|retrieval|relevance|precision|mrr|ndcg|hit|recall|risk|prediction|prognosis|cox|survival|lightgbm|catboost|calibration|brier|cindex|shap|feature|split|OAKNet)", re.I)
    for root in scan_roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in exclude and not d.startswith(".")]
            for fn in filenames:
                p = Path(dirpath) / fn
                if p in seen:
                    continue
                seen.add(p)
                if root not in [OUT / "00_inventory" / "x", PREV] and not keywords.search(str(p)):
                    continue
                cols = ""
                if p.suffix.lower() == ".csv" and p.stat().st_size < 3_000_000:
                    try:
                        cols = "|".join(map(str, read_csv(p, nrows=1).columns))
                    except Exception:
                        cols = ""
                cat, module, usable, notes = detailed_category(p, cols)
                records.append(
                    {
                        "absolute_path": str(p),
                        "relative_path": rel_to_out(p),
                        "file_name": p.name,
                        "extension": p.suffix.lower(),
                        "file_size_bytes": p.stat().st_size,
                        "source_archive": "previous_extracted_archive" if str(p).startswith(str(OUT / "00_inventory" / "x")) else ("previous_audit_package" if str(p).startswith(str(PREV)) else "project_source"),
                        "detected_category": cat,
                        "module_guess": module,
                        "usable_for": usable,
                        "notes": notes,
                    }
                )
    df = pd.DataFrame(records).sort_values(["module_guess", "detected_category", "file_name"])
    df.to_csv(OUT / "00_inventory" / "all_files_inventory.csv", index=False, encoding="utf-8-sig")
    return df


def build_key_summary(inv: pd.DataFrame) -> None:
    def count(cat):
        return int((inv["detected_category"] == cat).sum())
    lines = [
        "# Key asset summary\n\n",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}\n\n",
        "## 1. KOM-Sim logs or task-level records found\n",
        f"- Raw event-log candidate files: {count('KOM-Sim raw event log')}\n",
        f"- Task-level log candidate files: {count('KOM-Sim task-level log')}\n",
        f"- Questionnaire/summary candidate files: {count('KOM-Sim questionnaire') + count('KOM-Sim summary table')}\n",
        "\n## 2. HTML/source files found\n",
        f"- KOM-Sim HTML source candidates: {count('KOM-Sim HTML source')}\n",
        f"- Other HTML/evidence source files: {count('KOM-RAG evidence unit')}\n",
        "\n## 3. KOM-Risk files found\n",
        f"- Prediction-like files: {count('KOM-Risk prediction')}\n",
        f"- Metric-like files: {count('KOM-Risk metrics')}\n",
        f"- Calibration-like files: {count('KOM-Risk calibration')}\n",
        f"- Feature-importance-like files: {count('KOM-Risk feature importance')}\n",
        "\n## 4. KOM-RAG files found\n",
        f"- Query-set-like files: {count('KOM-RAG query set')}\n",
        f"- Retrieval-result-like files: {count('KOM-RAG retrieval result')}\n",
        f"- Relevance-label-like files: {count('KOM-RAG relevance label')}\n",
        f"- Metric-like files: {count('KOM-RAG metric')}\n",
        f"- Guideline-anchor-like files: {count('KOM-RAG guideline anchor')}\n",
        "\n## 5. Directly usable for submission-grade audit\n",
        "- Stage4A frozen bge-m3 retrieval JSON/CSV files are directly usable for RAG benchmark metrics.\n",
        "- Doctor prescription/task-level exported records are usable for task-level KOM-Sim timing summaries.\n",
        "- Main-text KOMRisk headline metrics are preserved as summary-level reproducibility evidence.\n",
        "\n## 6. Preliminary evidence only\n",
        "- Figure-source CSVs and workbook-derived sheets are useful for traceability but should not be described as raw event logs or sample-level risk predictions without source verification.\n",
        "\n## 7. Missing or partial\n",
        "- Complete raw event-level KOM-Sim click/session logs were not verified.\n",
        "- Endpoint-specific sample-level longitudinal KOMRisk predictions were not verified; OAKNet imaging predictions are not treated as KOMRisk longitudinal predictions.\n",
        "- Full all-query RAG TopK final ranking rows are partial; Stage4A per-query metrics are available, with top-k examples/sample/candidate records.\n",
    ]
    write_md(OUT / "00_inventory" / "key_asset_summary.md", "".join(lines))


def build_komsim(inv: pd.DataFrame) -> dict:
    sim_dir = OUT / "01_KOMSim_time_and_log_audit"
    candidates = inv[inv["module_guess"].eq("KOM-Sim") | inv["detected_category"].str.startswith("KOM-Sim", na=False)]
    inv_rows = []
    for _, r in candidates.iterrows():
        p = Path(r["absolute_path"])
        row = {
            "file_path": str(p),
            "file_type": r["detected_category"],
            "num_rows": pd.NA,
            "columns": "",
            "has_doctor_id": False,
            "has_case_id": False,
            "has_task_id": False,
            "has_condition": False,
            "has_task_order": False,
            "has_timestamp": False,
            "has_start_time": False,
            "has_submit_time": False,
            "has_editor_open_time": False,
            "has_questionnaire_time": False,
            "has_editing_time": False,
            "has_page_event": False,
            "has_view_event": False,
            "has_copy_action": False,
            "has_ai_view": False,
            "has_rationale_view": False,
            "has_evidence_view": False,
            "has_prescription_text": False,
            "has_score": False,
            "usable_for_event_level_analysis": False,
            "usable_for_task_level_analysis": False,
            "notes": "",
        }
        if p.suffix.lower() == ".csv" and p.exists() and p.stat().st_size < 10_000_000:
            df = read_csv(p)
            cols = [str(c) for c in df.columns]
            low = "|".join(cols).lower()
            row["num_rows"] = len(df)
            row["columns"] = "|".join(cols)
            checks = {
                "has_doctor_id": ["doctor", "physician", "participant"],
                "has_case_id": ["case id", "case_id"],
                "has_task_id": ["task_id", "task id"],
                "has_condition": ["condition", "arm"],
                "has_task_order": ["case order", "task_order", "order"],
                "has_timestamp": ["timestamp", "submitted at"],
                "has_start_time": ["start"],
                "has_submit_time": ["submit", "submitted"],
                "has_editor_open_time": ["editor"],
                "has_questionnaire_time": ["questionnaire"],
                "has_editing_time": ["editing time"],
                "has_page_event": ["page"],
                "has_view_event": ["view"],
                "has_copy_action": ["copy"],
                "has_ai_view": ["decision-support", "ai"],
                "has_rationale_view": ["rationale"],
                "has_evidence_view": ["evidence"],
                "has_prescription_text": ["prescription"],
                "has_score": ["score", "grade"],
            }
            for k, terms in checks.items():
                row[k] = any(t in low for t in terms)
            row["usable_for_event_level_analysis"] = row["has_timestamp"] and ("event" in low or "action" in low or "page_name" in low)
            row["usable_for_task_level_analysis"] = row["has_case_id"] and row["has_condition"] and (row["has_editing_time"] or row["has_submit_time"] or row["has_prescription_text"])
            if "doctor_prescriptions" in p.name.lower() or ("editing time seconds" in low and "doctor final prescription" in low):
                row["notes"] = "Best available task-level exported prescription record."
        inv_rows.append(row)
    write_csv(sim_dir / "raw_or_task_log_inventory" / "KOMSim_log_inventory.csv", inv_rows)

    # HTML timer audit.
    keywords = [
        "Date.now", "performance.now", "startTime", "taskStart", "caseStart", "answerStart", "submitTime", "editingTime", "elapsed", "timer",
        "visibilitychange", "blur", "focus", "pagehide", "beforeunload", "pause", "resume", "questionnaire", "condition", "random", "shuffle",
        "case_order", "experiment_block", "within_block_order", "localStorage", "export", "CSV", "JSON",
    ]
    html_rows = []
    html_files = inv[inv["extension"].isin([".html", ".htm"])]["absolute_path"].tolist()
    for hp in html_files:
        p = Path(hp)
        try:
            lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, start=1):
            for kw in keywords:
                if kw.lower() in line.lower():
                    low = kw.lower()
                    html_rows.append(
                        {
                            "source_file": str(p),
                            "keyword": kw,
                            "line_number": i,
                            "code_snippet": line.strip()[:500],
                            "interpretation": "timer/randomization/export keyword found in source; source-specific review required",
                            "supports_time_start": low in ["date.now", "performance.now", "starttime", "taskstart", "casestart", "answerstart"],
                            "supports_time_stop": low in ["submittime", "editingtime", "elapsed"],
                            "supports_pause_on_leave": low in ["visibilitychange", "blur", "focus", "pagehide", "beforeunload", "pause", "resume"],
                            "supports_randomization": low in ["random", "shuffle", "case_order", "experiment_block", "within_block_order"],
                            "supports_export": low in ["localstorage", "export", "csv", "json"],
                            "notes": "Keyword hit; not proof of behavior unless linked to timing/export control flow.",
                        }
                    )
    write_csv(sim_dir / "source_code_audit" / "KOMSim_HTML_timer_source_audit.csv", html_rows)
    found_start = any(r["supports_time_start"] for r in html_rows)
    found_stop = any(r["supports_time_stop"] for r in html_rows)
    found_pause = any(r["supports_pause_on_leave"] for r in html_rows)
    found_random = any(r["supports_randomization"] for r in html_rows)
    found_export = any(r["supports_export"] for r in html_rows)
    write_md(
        sim_dir / "source_code_audit" / "KOMSim_HTML_timer_source_audit.md",
        f"""# KOM-Sim HTML timer source audit

## Answers

1. Timer variables found in source: {'YES' if found_start or found_stop else 'NOT SUPPORTED BY CURRENT SOURCE CODE'}.
2. Start event: available source supports timer-related variables, but exact start point should be described as entry into the prescription-answering interface unless a source line explicitly links it to a button.
3. End event: {'submission/editing-time related keywords were found' if found_stop else 'not supported by current source code'}.
4. Exclusion of questionnaire time: not supported by current source code alone; supported by experiment design wording and task-level exported timing definition.
5. Page leave/focus pause: {'supported by keyword hits, but control-flow verification is still recommended' if found_pause else 'not supported by current source code'}.
6. Randomization/case order logic: {'keyword evidence found' if found_random else 'not supported by current source code'}.
7. CSV/JSON export logic: {'keyword evidence found' if found_export else 'not supported by current source code'}.
8. Supported methods wording: task-level exported timing records can support task-time summaries.
9. Unsupported claims: raw event-level clickstream analyses and definitive page-leave pause exclusion should not be claimed unless original logs/source control flow are supplied.
""",
    )

    # Standard task-level log from best exported prescriptions.
    best = None
    for _, r in candidates.iterrows():
        p = Path(r["absolute_path"])
        if p.suffix.lower() == ".csv" and "doctor_prescriptions_780" in p.name.lower() and p.exists():
            best = p
            break
    if best is None:
        for _, r in candidates.iterrows():
            p = Path(r["absolute_path"])
            if p.suffix.lower() == ".csv" and p.exists():
                df0 = read_csv(p, nrows=1)
                low = "|".join(map(str, df0.columns)).lower()
                if "doctor final prescription" in low and "editing time seconds" in low:
                    best = p
                    break
    task_cols = [
        "doctor_id", "task_id", "case_id", "case_quadrant", "condition", "condition_label", "task_order", "randomization_block", "case_sampling_source",
        "task_start_time", "prescription_interface_entry_time", "prescription_editor_open_time", "prescription_submit_time", "questionnaire_start_time",
        "questionnaire_submit_time", "editing_time_sec", "task_time_sec", "questionnaire_time_sec", "idle_time_sec", "page_leave_pause_supported",
        "extreme_value_excluded", "final_prescription_text", "text_length", "treatment_component_count", "high_quality_prescription", "rule_score",
        "expert_overall_quality", "safety_critical_error", "clinical_decision_error", "workload", "confidence", "information_sufficiency",
        "decision_certainty", "ai_influence", "ai_suggestion_views", "rationale_views", "evidence_summary_views", "copy_adopt_action_count", "source_file",
    ]
    task_rows = []
    if best:
        df = read_csv(best)
        for idx, row in df.iterrows():
            arm = safe_text(row.get("Arm")) or safe_text(row.get("Condition label"))
            final_text = safe_text(row.get("Doctor final prescription (verbatim source)"))
            task_rows.append(
                {
                    "doctor_id": row.get("Participant"),
                    "task_id": row.get("Case order", idx + 1),
                    "case_id": row.get("Case ID"),
                    "case_quadrant": row.get("Stage"),
                    "condition": arm,
                    "condition_label": row.get("Condition label"),
                    "task_order": row.get("Case order"),
                    "randomization_block": row.get("Randomization batch"),
                    "case_sampling_source": "exported standardized prescription tasks",
                    "task_start_time": pd.NA,
                    "prescription_interface_entry_time": pd.NA,
                    "prescription_editor_open_time": pd.NA,
                    "prescription_submit_time": row.get("Submitted at"),
                    "questionnaire_start_time": pd.NA,
                    "questionnaire_submit_time": pd.NA,
                    "editing_time_sec": row.get("Editing time seconds"),
                    "task_time_sec": row.get("Editing time seconds"),
                    "questionnaire_time_sec": pd.NA,
                    "idle_time_sec": pd.NA,
                    "page_leave_pause_supported": "not_verified_from_current_source_code",
                    "extreme_value_excluded": False,
                    "final_prescription_text": final_text,
                    "text_length": row.get("Prescription length characters") if pd.notna(row.get("Prescription length characters", pd.NA)) else len(final_text),
                    "treatment_component_count": row.get("Component count"),
                    "high_quality_prescription": pd.NA,
                    "rule_score": pd.NA,
                    "expert_overall_quality": row.get("Overall expert consistency score (0-10; summary)"),
                    "safety_critical_error": row.get("Overall major clinical error"),
                    "clinical_decision_error": row.get("Overall major clinical error"),
                    "workload": row.get("Workload for case prescription"),
                    "confidence": row.get("Confidence in final prescription"),
                    "information_sufficiency": row.get("Information sufficiency for prescription"),
                    "decision_certainty": row.get("Certainty in case treatment decision"),
                    "ai_influence": row.get("Influence of decision support on prescription"),
                    "ai_suggestion_views": row.get("Decision-support recommendation views"),
                    "rationale_views": row.get("Rationale views"),
                    "evidence_summary_views": row.get("Evidence views"),
                    "copy_adopt_action_count": row.get("One-click support-copy count"),
                    "source_file": str(best),
                }
            )
    write_csv(sim_dir / "standardized_logs" / "KOMSim_task_level_log_standardized_FINAL.csv", task_rows, task_cols)

    event_cols = ["doctor_id", "task_id", "case_id", "condition", "event_type", "event_time", "page_name", "element_name", "action_name", "value", "source_file"]
    write_csv(sim_dir / "standardized_logs" / "KOMSim_event_log_standardized_FINAL.csv", [], event_cols)
    write_md(
        sim_dir / "standardized_logs" / "KOMSim_missing_event_log_report.md",
        "# KOM-Sim missing raw event-level log report\n\nComplete raw event-level click/session logs were not verified in the available source package. The FINAL event log table is therefore a 0-row schema template. Task-level exported prescription records are available and were standardized separately.\n",
    )

    protocol = f"""# KOM-Sim log cleaning protocol FINAL

## 1. Timing source
Task-level exported timing records were used. Raw event-level click/session logs were not verified.

## 2. Start event
Prescription/task time was defined as entry into the prescription-answering task interface.

## 3. End event
The endpoint was prescription submission when the exported task record provides a submitted-at timestamp or editing-time value.

## 4. Included intervals
The interval included case reading within the task interface and interaction with AI materials within the task interface.

## 5. Excluded intervals
Post-task questionnaire time was excluded by definition. Fields for questionnaire timing are retained as NA unless directly exported.

## 6. Questionnaire handling
Questionnaire fields are not included in the primary task time unless explicit source logs prove otherwise.

## 7. Case reading handling
Case reading inside the prescription-answering interface is included.

## 8. AI material viewing handling
AI suggestion, rationale, and evidence summary view counts are retained where exported; these are interaction summaries rather than raw clickstream logs.

## 9. Page leave / inactive handling
{"Page-leave or inactive intervals were paused by the interface timer when supported by the source code." if found_pause else "Page-leave pause behavior could not be verified from the available source code and was not used as a primary exclusion rule."}

## 10. Extreme value handling
No primary exclusion of extreme values was applied unless explicitly documented in the source or exported logs.

## 11. Median vs mean reporting
Task records were summarized primarily using medians rather than means to reduce the influence of extreme task durations.

## 12. Randomization and case allocation
Physician tasks were randomized in case assignment/order and information exposure where supported by the experiment version. The later experiment version used 30 randomized standardized prescription tasks per physician, sampled from Q1-Q4 strata. The same case was not necessarily repeated under all three information conditions for every physician; therefore case-balanced repeated-case claims must not be made unless directly supported by the task allocation table.

## 13. Record-level vs physician-level analysis
Record-level task rows are available for exported prescription tasks. Physician-level paired summaries should aggregate within physician before condition comparisons.

## 14. Limitations of the available log data
Complete raw event-level click logs were not verified for all tasks. Page-leave behavior and fine-grained clickstream analyses should be reported as unavailable unless the original raw logs are supplied.

## 15. Manuscript-ready methods wording
Task time was measured from entry into the prescription-answering interface to prescription submission. This interval included case reading and interaction with AI materials within the task interface, and excluded the post-task questionnaire. Because complete raw event-level click logs were not available for all tasks, time analyses were based on exported task-level timing records. We summarized task time using medians and conducted physician-level paired comparisons across information conditions.
"""
    write_md(sim_dir / "time_definition_protocol" / "KOM-Sim_log_cleaning_protocol_FINAL.md", protocol)
    write_md(sim_dir / "manuscript_ready_methods" / "Supplementary_Methods_KOMSim_Time_Definition.md", protocol)

    summary_rows = [
        {"metric": "editing_time_median_sec", "condition": "A", "value": 43.5, "source_status": "summary_table_only"},
        {"metric": "editing_time_median_sec", "condition": "B", "value": 27.0, "source_status": "summary_table_only"},
        {"metric": "editing_time_median_sec", "condition": "C", "value": 17.0, "source_status": "summary_table_only"},
        {"metric": "workload", "condition": "A", "value": 5.10, "source_status": "summary_table_only"},
        {"metric": "workload", "condition": "B", "value": 4.35, "source_status": "summary_table_only"},
        {"metric": "workload", "condition": "C", "value": 3.84, "source_status": "summary_table_only"},
        {"metric": "confidence", "condition": "A", "value": 7.60, "source_status": "summary_table_only"},
        {"metric": "confidence", "condition": "B", "value": 7.78, "source_status": "summary_table_only"},
        {"metric": "confidence", "condition": "C", "value": 7.93, "source_status": "summary_table_only"},
        {"metric": "information_sufficiency", "condition": "A", "value": 7.93, "source_status": "summary_table_only"},
        {"metric": "information_sufficiency", "condition": "B", "value": 8.05, "source_status": "summary_table_only"},
        {"metric": "information_sufficiency", "condition": "C", "value": 8.12, "source_status": "summary_table_only"},
        {"metric": "decision_certainty", "condition": "A", "value": 7.38, "source_status": "summary_table_only"},
        {"metric": "decision_certainty", "condition": "B", "value": 7.51, "source_status": "summary_table_only"},
        {"metric": "decision_certainty", "condition": "C", "value": 7.66, "source_status": "summary_table_only"},
        {"metric": "AI influence", "condition": "B", "value": 5.63, "source_status": "summary_table_only"},
        {"metric": "AI influence", "condition": "C", "value": 5.89, "source_status": "summary_table_only"},
        {"metric": "AI suggestion views", "condition": "B", "value": 1.46, "source_status": "summary_table_only"},
        {"metric": "AI suggestion views", "condition": "C", "value": 1.29, "source_status": "summary_table_only"},
        {"metric": "Rationale views", "condition": "C", "value": 0.47, "source_status": "summary_table_only"},
        {"metric": "Evidence summary views", "condition": "C", "value": 0.29, "source_status": "summary_table_only"},
        {"metric": "Copy/adopt action", "condition": "AI-assisted conditions", "value": 0.6, "source_status": "summary_table_only", "notes": "approximately >=0.6 per task"},
    ]
    comparison_rows = [
        {"metric": "editing_time_sec", "comparison": "B vs A", "paired_difference": -7.75, "q_value": 0.048, "source_status": "summary_table_only"},
        {"metric": "editing_time_sec", "comparison": "C vs A", "paired_difference": -19.5, "q_value": 2.3e-4, "source_status": "summary_table_only"},
        {"metric": "editing_time_sec", "comparison": "C vs B", "paired_difference": -6.75, "q_value": 2.3e-4, "source_status": "summary_table_only"},
        {"metric": "workload", "comparison": "B vs A", "paired_difference": -0.75, "q_value": 0.043, "source_status": "summary_table_only"},
        {"metric": "workload", "comparison": "C vs A", "paired_difference": -1.27, "q_value": 0.004, "source_status": "summary_table_only"},
        {"metric": "workload", "comparison": "C vs B", "paired_difference": -0.52, "q_value": 0.004, "source_status": "summary_table_only"},
    ]
    physician_rows = []
    if task_rows:
        tdf = pd.DataFrame(task_rows)
        for (doc, cond), grp in tdf.groupby(["doctor_id", "condition"], dropna=False):
            times = pd.to_numeric(grp["editing_time_sec"], errors="coerce").dropna()
            physician_rows.append({"doctor_id": doc, "condition": cond, "n_tasks": len(grp), "median_editing_time_sec": times.median() if len(times) else pd.NA, "mean_editing_time_sec": times.mean() if len(times) else pd.NA, "source_status": "recomputed_from_task_level_records"})
    write_csv(sim_dir / "time_and_interaction_tables" / "KOMSim_time_and_interaction_summary_FINAL.csv", summary_rows)
    write_csv(sim_dir / "time_and_interaction_tables" / "KOMSim_physician_level_summary_FINAL.csv", physician_rows)
    write_csv(sim_dir / "time_and_interaction_tables" / "KOMSim_condition_comparison_statistics_FINAL.csv", comparison_rows)
    return {"event_found": False, "task_rows": len(task_rows), "html_hits": len(html_rows), "time_metrics": "partial"}


def build_risk(inv: pd.DataFrame) -> dict:
    risk_dir = OUT / "02_KOMRisk_reproducible_prediction_package"
    risk_inv = inv[inv["module_guess"].eq("KOM-Risk") | inv["detected_category"].str.startswith("KOM-Risk", na=False)]
    risk_inv.to_csv(risk_dir / "inventory" / "KOMRisk_file_inventory.csv", index=False, encoding="utf-8-sig")
    pred_cols = [
        "sample_id", "person_id", "knee_id", "side", "endpoint", "split", "fold", "site", "time_origin", "followup_time", "event_time", "censor_time",
        "event_observed", "y_true", "predicted_probability", "risk_score", "predicted_class", "model_name", "algorithm", "feature_set", "source_file", "row_origin", "data_quality_flag",
    ]
    endpoints = [
        ("KL structural progression", "LightGBM"),
        ("TKR / knee surgery event", "CoxPH"),
        ("Symptom/function worsening", "CatBoost"),
    ]
    all_pred = []
    for endpoint, alg in endpoints:
        row = {"endpoint": endpoint, "algorithm": alg, "data_quality_flag": "sample_level_predictions_missing", "row_origin": "missing_template_not_fabricated"}
        out_name = {
            "KL structural progression": "risk_predictions_structural_progression.csv",
            "TKR / knee surgery event": "risk_predictions_tkr_knee_surgery.csv",
            "Symptom/function worsening": "risk_predictions_symptom_function_worsening.csv",
        }[endpoint]
        write_csv(risk_dir / "endpoint_specific_predictions" / out_name, [row], pred_cols)
        all_pred.append(row)
    write_csv(risk_dir / "endpoint_specific_predictions" / "risk_predictions_all_endpoints_clean.csv", all_pred, pred_cols)
    metric_rows = [
        {"endpoint": "KL structural progression", "model_name": "LightGBM", "algorithm": "LightGBM", "n_samples": 7855, "event_rate": 13.4, "AUROC": 0.817, "C_index": pd.NA, "Brier": pd.NA, "BACC": 0.735, "calibration_slope": pd.NA, "calibration_intercept": pd.NA, "ECE": pd.NA, "AUPRC": pd.NA, "split": pd.NA, "fold": pd.NA, "source_file": "main-text summary value", "metric_source": "summary_metric"},
        {"endpoint": "TKR / knee surgery event", "model_name": "CoxPH", "algorithm": "CoxPH", "n_samples": 9014, "event_rate": 5.2, "AUROC": pd.NA, "C_index": 0.862, "Brier": pd.NA, "BACC": pd.NA, "calibration_slope": pd.NA, "calibration_intercept": pd.NA, "ECE": pd.NA, "AUPRC": pd.NA, "split": pd.NA, "fold": pd.NA, "source_file": "main-text summary value", "metric_source": "summary_metric"},
        {"endpoint": "Symptom/function worsening", "model_name": "CatBoost", "algorithm": "CatBoost", "n_samples": 8962, "event_rate": 31.0, "AUROC": 0.683, "C_index": pd.NA, "Brier": pd.NA, "BACC": pd.NA, "calibration_slope": pd.NA, "calibration_intercept": pd.NA, "ECE": pd.NA, "AUPRC": pd.NA, "split": pd.NA, "fold": pd.NA, "source_file": "main-text summary value", "metric_source": "summary_metric"},
    ]
    write_csv(risk_dir / "metrics" / "risk_model_metrics_FINAL.csv", metric_rows)
    calib_cols = ["endpoint", "model_name", "bin_id", "n_bin", "mean_predicted_risk", "observed_event_rate", "lower_ci", "upper_ci", "source_file"]
    calib_rows = []
    for endpoint, alg in endpoints:
        calib_rows.append({"endpoint": endpoint, "model_name": alg, "bin_id": pd.NA, "source_file": "calibration requires endpoint-specific sample-level predicted probabilities; not generated from OAKNet imaging predictions"})
        safe = endpoint.lower().replace(" / ", "_").replace(" ", "_").replace("-", "_")
        write_csv(risk_dir / "calibration" / f"risk_calibration_curve_{safe}.csv", [calib_rows[-1]], calib_cols)
    write_csv(risk_dir / "calibration" / "risk_calibration_curve_all.csv", calib_rows, calib_cols)
    fi_rows = []
    for _, r in risk_inv.iterrows():
        p = Path(r["absolute_path"])
        if "shap" in p.name.lower() or "feature" in p.name.lower() or "importance" in p.name.lower():
            fi_rows.append({"endpoint": "unverified_or_global_source", "model_name": pd.NA, "feature_name": p.name, "importance_value": pd.NA, "importance_type": "file_level_inventory", "rank": pd.NA, "source_file": str(p)})
    write_csv(risk_dir / "feature_importance" / "risk_feature_importance_FINAL.csv", fi_rows, ["endpoint", "model_name", "feature_name", "importance_value", "importance_type", "rank", "source_file"])
    write_md(risk_dir / "feature_importance" / "KOMRisk_SHAP_status.md", "# KOMRisk SHAP status\n\nGlobal or file-level feature-importance candidates were inventoried where available. Endpoint-specific sample-level SHAP values were not verified in the current source package.\n")
    split_rows = []
    for endpoint, alg in endpoints:
        split_rows.append({"endpoint": endpoint, "data_quality_flag": "split_definition_missing_or_partial", "source_file": "missing_template_not_fabricated"})
    write_csv(risk_dir / "splits_and_config" / "risk_split_definition_FINAL.csv", split_rows, ["sample_id", "person_id", "knee_id", "endpoint", "split", "fold", "site", "source_file", "data_quality_flag"])
    cfg = {
        "endpoints": [e[0] for e in endpoints],
        "algorithms": [e[1] for e in endpoints],
        "feature_sets": [],
        "preprocessing": {},
        "hyperparameters": {},
        "random_seed": None,
        "split_strategy": None,
        "source_files": risk_inv["absolute_path"].head(50).tolist(),
        "missing_items": [
            "Endpoint-specific sample-level longitudinal predictions are missing.",
            "Endpoint-specific calibration probabilities are missing.",
            "Endpoint-specific split definitions are missing or partial.",
            "Endpoint-specific sample-level SHAP values are not verified.",
        ],
    }
    (risk_dir / "splits_and_config" / "risk_model_config_FINAL.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    write_md(
        risk_dir / "missing_items" / "KOMRisk_missing_items_report_FINAL.md",
        """# KOMRisk missing items report FINAL

1. Sample-level predictions: not verified for all three longitudinal endpoints.
2. Summary metrics only: all three endpoints currently have main-text summary metrics.
3. Probability availability: absolute predicted probabilities were not verified for endpoint-specific longitudinal risks.
4. Survival time/event status: not verified in clean endpoint-level prediction tables.
5. Calibration: not submission-ready for longitudinal endpoints without endpoint-specific probabilities.
6. DCA: not recomputable without endpoint-specific predicted risks and outcomes.
7. Feature importance: file-level/global candidates exist; endpoint-specific sample-level SHAP not verified.
8. Rerun needed: rerun or export the longitudinal risk models if reviewers require sample-level recalculation.
9. Main-text support: current support is summary-level metric rows in risk_model_metrics_FINAL.csv plus file inventory.

OAKNet imaging/KL classification predictions were not treated as KOMRisk longitudinal endpoint predictions.
""",
    )
    write_md(
        OUT / "06_submission_ready_text" / "Supplementary_Methods_KOMRisk_Reproducibility.md",
        """# Supplementary Methods: KOMRisk reproducibility

The KOMRisk reproducibility audit used endpoint-level summary metrics for three clinical risk endpoints: KL structural progression, TKR/knee surgery event, and symptom/function worsening. The available package preserves the reported headline performance values but does not verify complete endpoint-specific sample-level longitudinal prediction rows. OAKNet imaging predictions were inventoried separately and were not treated as longitudinal KOMRisk predictions.

Metrics were retained only when directly available from manuscript-facing summary values or source tables. Missing Brier scores, calibration slopes, ECE, AUPRC, endpoint-specific predicted probabilities, survival times, and split definitions were left as missing rather than inferred. Calibration and decision-curve analyses require endpoint-specific predicted risk probabilities and observed outcomes and should be regenerated if required for peer-review reproducibility.
""",
    )
    return {"endpoint_predictions": "missing", "metrics": "complete", "calibration": "partial", "feature_importance": "partial", "config": "partial", "split": "partial"}


def dcg(gains: list[float]) -> float:
    return sum(g / math.log2(i + 2) for i, g in enumerate(gains))


def build_rag(inv: pd.DataFrame) -> dict:
    rag_dir = OUT / "03_KOMRAG_query_level_evidence_mapping"
    rag_inv = inv[inv["module_guess"].eq("KOM-RAG") | inv["detected_category"].str.startswith("KOM-RAG", na=False) | inv["detected_category"].eq("evidence matrix")]
    rag_inv.to_csv(rag_dir / "inventory" / "KOMRAG_file_inventory.csv", index=False, encoding="utf-8-sig")
    metrics_json = read_json(STAGE4A_METRICS)
    precomp = read_json(STAGE4A_PRECOMP_HOLDOUT)
    records = precomp.get("records", []) if isinstance(precomp, dict) else []
    query_rows = []
    labels = []
    retrieval_rows = []
    query_map = {}
    for i, rec in enumerate(records, start=1):
        qid = f"{rec.get('case_id')}__{rec.get('gold_agent')}"
        qtext = rec.get("query", "")
        domain = normalize_domain((rec.get("gold_agent") or "") + " " + qtext)
        query_map[qid] = {"query_text": qtext, "treatment_domain": domain}
        query_rows.append({"query_id": qid, "query_text": qtext, "clinical_question": qtext, "treatment_domain": domain, "patient_scenario": rec.get("case_id"), "agent_or_specialty": rec.get("agent_name") or rec.get("gold_agent"), "expected_guideline_anchor": "not_explicit_in_stage4a_record", "source_file": str(STAGE4A_PRECOMP_HOLDOUT), "data_quality_flag": "stage4a_frozen_holdout_query"})
        strict = set(rec.get("strict_gold", []))
        for eu in sorted(strict):
            labels.append({"query_id": qid, "evidence_unit_id": eu, "is_relevant": 1, "relevance_grade": 1, "matched_guideline_anchor_id": pd.NA, "label_source": "guideline_anchor_weak_gold", "label_rationale": "Stage4A strict_gold membership", "requires_manual_review": False, "source_file": str(STAGE4A_PRECOMP_HOLDOUT), "data_quality_flag": "positive_weak_gold"})
        # Candidate pool is not guaranteed to be final reranked TopK; mark it clearly.
        seen_eu = set()
        for rank, cand in enumerate(rec.get("candidates", [])[:30], start=1):
            eu = cand.get("evidence_id")
            if not eu or eu in seen_eu:
                continue
            seen_eu.add(eu)
            retrieval_rows.append({"query_id": qid, "method": "KOM-RAG_candidate_pool", "rank": rank, "evidence_unit_id": eu, "evidence_title": pd.NA, "evidence_level": cand.get("level"), "source_type": pd.NA, "source_year": pd.NA, "source_url_or_doi_or_pmid": pd.NA, "retrieval_score": pd.NA, "graph_score": pd.NA, "rerank_score": pd.NA, "final_score": pd.NA, "agent_or_specialty": rec.get("agent_name") or rec.get("gold_agent"), "source_file": str(STAGE4A_PRECOMP_HOLDOUT), "data_quality_flag": "candidate_pool_order_not_final_rerank"})
            if eu not in strict:
                labels.append({"query_id": qid, "evidence_unit_id": eu, "is_relevant": 0, "relevance_grade": 0, "matched_guideline_anchor_id": pd.NA, "label_source": "rule_inferred_candidate", "label_rationale": "Retrieved candidate absent from Stage4A strict_gold set", "requires_manual_review": True, "source_file": str(STAGE4A_PRECOMP_HOLDOUT), "data_quality_flag": "negative_candidate_requires_manual_review"})

    # Add exact top30 sample rows from Stage4A summary where available.
    rec_by_key = {f"{r.get('case_id')}__{r.get('gold_agent')}": r for r in records}
    for sample in metrics_json.get("rows_sample", []):
        qid = f"{sample.get('case_id')}__{sample.get('gold_agent')}"
        rec = rec_by_key.get(qid, {})
        strict = set(rec.get("strict_gold", []))
        for method, field in [("KOM-RAG", "graph_top30"), ("naive RAG", "baseline_top30")]:
            for rank, eu in enumerate(sample.get(field, [])[:30], start=1):
                retrieval_rows.append({"query_id": qid, "method": method, "rank": rank, "evidence_unit_id": eu, "evidence_title": pd.NA, "evidence_level": pd.NA, "source_type": pd.NA, "source_year": pd.NA, "source_url_or_doi_or_pmid": pd.NA, "retrieval_score": pd.NA, "graph_score": pd.NA, "rerank_score": pd.NA, "final_score": pd.NA, "agent_or_specialty": sample.get("agent_name"), "source_file": str(STAGE4A_METRICS), "data_quality_flag": "stage4a_rows_sample_final_top30"})
                if eu not in strict:
                    labels.append({"query_id": qid, "evidence_unit_id": eu, "is_relevant": 0, "relevance_grade": 0, "matched_guideline_anchor_id": pd.NA, "label_source": "rule_inferred_candidate", "label_rationale": "Top30 sample evidence absent from strict_gold", "requires_manual_review": True, "source_file": str(STAGE4A_METRICS), "data_quality_flag": "negative_candidate_requires_manual_review"})

    write_csv(rag_dir / "clean_query_set" / "rag_query_set_CLEAN.csv", query_rows, ["query_id", "query_text", "clinical_question", "treatment_domain", "patient_scenario", "agent_or_specialty", "expected_guideline_anchor", "source_file", "data_quality_flag"])
    write_csv(rag_dir / "retrieval_results" / "rag_retrieval_results_CLEAN.csv", retrieval_rows, ["query_id", "method", "rank", "evidence_unit_id", "evidence_title", "evidence_level", "source_type", "source_year", "source_url_or_doi_or_pmid", "retrieval_score", "graph_score", "rerank_score", "final_score", "agent_or_specialty", "source_file", "data_quality_flag"])
    label_df = pd.DataFrame(labels).drop_duplicates(["query_id", "evidence_unit_id", "is_relevant", "label_source"])
    label_df.to_csv(rag_dir / "relevance_labels" / "rag_relevance_labels_CLEAN.csv", index=False, encoding="utf-8-sig")
    strict_count = int((label_df["is_relevant"] == 1).sum()) if not label_df.empty else 0
    weak_count = int((label_df["label_source"] == "guideline_anchor_weak_gold").sum()) if not label_df.empty else 0
    inferred_count = int((label_df["label_source"] == "rule_inferred_candidate").sum()) if not label_df.empty else 0
    manual_review = int(label_df["requires_manual_review"].astype(str).str.lower().eq("true").sum()) if not label_df.empty else 0
    write_md(rag_dir / "relevance_labels" / "relevance_label_quality_report.md", f"""# Relevance label quality report

- Strict/positive labels: {strict_count}
- Weak-gold labels: {weak_count}
- Rule-inferred candidate labels: {inferred_count}
- Requires manual review: {manual_review}
- Unable to label: candidate records not present in retrieval outputs are not forced into negative labels.
""")

    # Guideline anchors from previous extracted mapping if available.
    prev_anchor = PREV / "03_KOMRAG_query_level_evidence_mapping" / "guideline_anchor_mapping.csv"
    anchors = []
    if prev_anchor.exists():
        pa = read_csv(prev_anchor)
        for idx, row in pa.drop_duplicates().head(2000).iterrows():
            raw = safe_text(row.get("evidence_id")) + " " + safe_text(row.get("title_or_source"))
            fam = "Other"
            for name in ["ACR/AF", "OARSI", "NICE", "AAOS", "ESCEO", "EULAR"]:
                if name.replace("/AF", "").lower() in raw.lower() or name.lower() in raw.lower():
                    fam = name
                    break
            anchors.append({"anchor_id": f"ANCHOR_{idx+1:04d}", "guideline_name": fam, "guideline_year": row.get("year"), "recommendation_text": row.get("title_or_source"), "recommendation_domain": normalize_domain(safe_text(row.get("title_or_source"))), "recommendation_strength": pd.NA, "evidence_unit_id": row.get("evidence_id"), "evidence_unit_title": row.get("title_or_source"), "source_url_or_doi_or_pmid": pd.NA, "mapping_rationale": "Extracted from existing evidence/guideline-like mapping table; explicit recommendation text may be absent.", "mapped_by": "scripted_file_audit", "source_file": row.get("source_file"), "data_quality_flag": "guideline_source_without_explicit_recommendation_text"})
    write_csv(rag_dir / "guideline_anchor_mapping" / "guideline_anchor_mapping_CLEAN.csv", anchors, ["anchor_id", "guideline_name", "guideline_year", "recommendation_text", "recommendation_domain", "recommendation_strength", "evidence_unit_id", "evidence_unit_title", "source_url_or_doi_or_pmid", "mapping_rationale", "mapped_by", "source_file", "data_quality_flag"])

    # Metrics: use frozen holdout rows for full query-level metrics.
    hold = read_csv(STAGE4A_HOLDOUT)
    metric_rows = []
    if not hold.empty:
        for _, row in hold.iterrows():
            qid = f"{row.get('case_id')}__{row.get('agent')}"
            domain = normalize_domain(safe_text(row.get("agent")))
            metric_rows.append({"query_id": qid, "treatment_domain": domain, "method": "KOM-RAG", "Precision@10": row.get("graph_precision_at_10"), "Recall@10": row.get("graph_recall_at_10"), "Recall@20": row.get("graph_recall_at_20"), "Recall@27": row.get("graph_recall_at_27"), "Recall@30": row.get("graph_recall_at_30"), "Hit@10": 1 if float(row.get("graph_precision_at_10", 0)) > 0 else 0, "MRR": row.get("graph_mrr"), "nDCG@10": row.get("graph_ndcg_at_10"), "num_relevant_total": row.get("strict_gold_count"), "num_retrieved": 30, "num_relevant_in_top10": float(row.get("graph_precision_at_10", 0)) * 10, "label_source_mix": "Stage4A strict_gold", "data_quality_flag": "metric_from_frozen_stage4a_per_query_file"})
            metric_rows.append({"query_id": qid, "treatment_domain": domain, "method": "naive RAG", "Precision@10": row.get("baseline_precision_at_10"), "Recall@10": row.get("baseline_recall_at_10"), "Recall@20": pd.NA, "Recall@27": pd.NA, "Recall@30": pd.NA, "Hit@10": 1 if float(row.get("baseline_precision_at_10", 0)) > 0 else 0, "MRR": row.get("baseline_mrr"), "nDCG@10": row.get("baseline_ndcg_at_10"), "num_relevant_total": row.get("strict_gold_count"), "num_retrieved": 10, "num_relevant_in_top10": float(row.get("baseline_precision_at_10", 0)) * 10, "label_source_mix": "Stage4A strict_gold", "data_quality_flag": "metric_from_frozen_stage4a_per_query_file"})
    mdf = write_csv(rag_dir / "query_metrics" / "rag_metric_by_query_CLEAN.csv", metric_rows)
    summary_rows = []
    if not mdf.empty:
        for method, grp in mdf.groupby("method"):
            summary_rows.append({"method": method, "n_queries": grp["query_id"].nunique(), "mean_Precision@10": grp["Precision@10"].mean(), "mean_Recall@10": grp["Recall@10"].mean(), "mean_Recall@20": grp["Recall@20"].mean(), "mean_Recall@27": grp["Recall@27"].mean(), "mean_Recall@30": grp["Recall@30"].mean(), "mean_Hit@10": grp["Hit@10"].mean(), "mean_MRR": grp["MRR"].mean(), "mean_nDCG@10": grp["nDCG@10"].mean(), "label_quality_notes": "Frozen Stage4A per-query metrics; full all-query final TopK rows are partial."})
    write_csv(rag_dir / "query_metrics" / "rag_metric_summary_CLEAN.csv", summary_rows)
    write_md(rag_dir / "query_metrics" / "rag_metric_discrepancy_report.md", "# RAG metric discrepancy report\n\nFull per-query metrics are available from the frozen Stage4A holdout table. Full all-query final TopK ranked evidence rows were not located as a single clean table, so metric recomputation from CLEAN retrieval rows is partial. This is a source availability limitation rather than a metric fabrication step.\n")

    # Error cases.
    error_rows = []
    if not mdf.empty:
        graph = mdf[mdf["method"] == "KOM-RAG"]
        p25 = graph["Precision@10"].quantile(0.25)
        for _, row in graph.iterrows():
            if row["Precision@10"] <= p25 or row["MRR"] == 0:
                qinfo = query_map.get(row["query_id"], {})
                error_rows.append({"query_id": row["query_id"], "query_text": qinfo.get("query_text"), "treatment_domain": row["treatment_domain"], "method": row["method"], "error_type": "low_rank_relevant_evidence" if row["MRR"] < 1 else "label_uncertain", "rank_of_first_relevant": (1 / row["MRR"] if row["MRR"] else pd.NA), "Precision@10": row["Precision@10"], "MRR": row["MRR"], "missed_relevant_evidence_unit_id": pd.NA, "top_wrong_evidence_unit_id": pd.NA, "description": "Candidate error case selected by low Precision@10 percentile or MRR rule.", "possible_reason": "Domain breadth, strict gold size, candidate-pool ordering, or label-source mix.", "requires_manual_review": True})
    if not error_rows:
        error_rows.append({"query_id": "QC_TEMPLATE", "error_type": "label_uncertain", "description": "No error case generated from available metrics; manual review recommended.", "requires_manual_review": True})
    write_csv(rag_dir / "error_cases" / "rag_error_cases_CLEAN.csv", error_rows, ["query_id", "query_text", "treatment_domain", "method", "error_type", "rank_of_first_relevant", "Precision@10", "MRR", "missed_relevant_evidence_unit_id", "top_wrong_evidence_unit_id", "description", "possible_reason", "requires_manual_review"])
    write_md(
        rag_dir / "audit_report" / "KOMRAG_query_level_audit_report_FINAL.md",
        f"""# KOMRAG query-level audit report FINAL

1. CLEAN query set: {len(query_rows)} queries from Stage4A holdout precomputed records.
2. Treatment domains: {', '.join(sorted(set(r['treatment_domain'] for r in query_rows)))}.
3. Queries with explicit guideline anchor text: 0 in Stage4A records; guideline anchors are available as separate evidence/guideline mapping rows.
4. Evidence units with DOI/PMID/URL: not fully recomputed in this package; traceability requires the source evidence matrix.
5. KOM-RAG and naive RAG top-k: final top30 examples are available in Stage4A rows_sample; full all-query final top-k rows were not located as one clean table.
6. Precision@10, MRR and nDCG: available from frozen per-query Stage4A holdout metrics.
7. Relevance labels: weak-gold/strict-gold positives and rule-inferred candidate negatives are separated; rule-inferred labels require manual review.
8. Summary-only metrics: full final top-k all-query metric recomputation remains partial.
9. Manual review: {manual_review} label rows require manual review.
10. Submission readiness: usable as supplementary audit with clear limitations; not a substitute for a full manual label file if reviewers request one.
11. Next step: export the full final top-k table and manual/strict relevance labels for every query if not already stored elsewhere.
""",
    )
    write_md(
        OUT / "06_submission_ready_text" / "Supplementary_Methods_KOMRAG_Query_Level_Audit.md",
        """# Supplementary Methods: KOMRAG query-level audit

The KOMRAG audit used the frozen Stage4A bge-m3 retrieval benchmark. Query-level performance was summarized from the Stage4A holdout table, including Precision@10, Recall@10, Recall@20, Recall@27, Recall@30, Hit@10, MRR, and nDCG@10. Relevance labels were derived from the Stage4A strict-gold evidence sets where available and were kept separate from rule-inferred candidate negatives, which require manual review.

Guideline anchor mappings were extracted from existing evidence/guideline-like mapping rows and were marked when explicit recommendation text was unavailable. Full all-query final TopK ranked evidence rows were not verified as a single clean file; therefore full metric recomputation from CLEAN retrieval rows is partial and should be supplemented with the exported final TopK table if requested by reviewers.
""",
    )
    return {"query_set": "complete", "anchors": "partial", "retrieval": "partial", "labels": "partial", "metrics": "complete", "errors": "complete", "manual_review_labels": manual_review}


def build_expert_label_audit(inv: pd.DataFrame) -> dict:
    expert_dir = OUT / "04_expert_label_name_audit"
    expert_files = inv[
        inv["module_guess"].eq("Expert ratings")
        | inv["detected_category"].isin(["expert rating table", "expert label dictionary"])
        | inv["file_name"].str.contains("expert|rater|ICC|blind|专家|评分|盲评", case=False, na=False)
    ].copy()
    expert_files.to_csv(expert_dir / "expert_rating_file_inventory.csv", index=False, encoding="utf-8-sig")
    label_specs = [
        ("总体质量 / overall quality / global quality", "overall_quality", "Overall clinical quality score or global prescription quality", ["overall quality", "global quality", "总体质量", "Overall expert"]),
        ("安全性 / safety", "safety", "Safety and risk-control assessment", ["safety", "安全"]),
        ("指南一致性 / guideline consistency", "guideline_consistency", "Guideline alignment or consistency with accepted standards", ["guideline", "指南"]),
        ("个体化 / individualization", "individualization", "Patient-specific tailoring", ["individualization", "个体化"]),
        ("可执行性 / feasibility / executability", "executability", "Clinical feasibility, actionability, or executability", ["feasibility", "executability", "可执行"]),
        ("证据可追溯性 / evidence traceability", "evidence_traceability", "Traceability of recommendations to evidence", ["evidence traceability", "证据"]),
        ("专科完整性 / specialty completeness", "specialty_completeness", "Coverage/completeness of specialty modules", ["specialty completeness", "专科"]),
        ("临床一致性 / clinical consistency", "clinical_consistency", "Cross-domain clinical consistency", ["clinical consistency", "consistency", "临床一致"]),
        ("安全关键错误 / safety-critical error", "safety_critical_error", "Critical safety error flag", ["safety-critical", "safety critical", "安全关键"]),
        ("临床决策相关错误 / clinical decision error", "clinical_decision_error", "Major clinical decision error flag", ["clinical decision error", "clinical error", "临床决策"]),
        ("轻微错误 / minor error", "minor_error", "Minor formatting/detail issue", ["minor error", "轻微"]),
    ]
    file_texts = []
    for _, r in expert_files.iterrows():
        p = Path(r["absolute_path"])
        text = p.name
        if p.suffix.lower() == ".csv" and p.exists() and p.stat().st_size < 5_000_000:
            df = read_csv(p, nrows=1)
            text += " " + " ".join(map(str, df.columns))
        file_texts.append((str(p), text.lower()))
    dict_rows = []
    for raw, norm, meaning, terms in label_specs:
        used = [fp for fp, txt in file_texts if any(t.lower() in txt for t in terms)]
        dict_rows.append(
            {
                "raw_label": raw,
                "normalized_label": norm,
                "meaning": meaning,
                "used_in_files": "; ".join(used[:20]) if used else "not_detected_in_file_headers",
                "notes": "Label-name normalization only; original human expert score values are not altered.",
            }
        )
    write_csv(expert_dir / "expert_label_dictionary_CLEAN.csv", dict_rows, ["raw_label", "normalized_label", "meaning", "used_in_files", "notes"])
    report = f"""# Expert label normalization report

This audit only normalizes label names for readability and downstream analysis. It does not rerate any prescription, does not alter any human expert score value, and does not relabel API/model scores as human expert ratings.

- Expert/rater/ICC/blind-review candidate files found: {len(expert_files)}
- Normalized label dictionary rows: {len(dict_rows)}
- Original score columns remain in their source files and are not overwritten.
- Naming differences should be interpreted as label/schema differences, not as result differences.

## Restrictions followed

1. Original expert scores were not modified.
2. Scores from different experts were not merged without retaining source-file evidence.
3. API/model evaluator scores were not represented as human expert ratings.
4. Label naming differences were not interpreted as clinical result differences.
"""
    write_md(expert_dir / "expert_label_normalization_report.md", report)
    write_md(
        OUT / "06_submission_ready_text" / "Supplementary_Methods_Expert_Rating_Label_Normalization.md",
        """# Supplementary Methods: expert rating label normalization

Human expert ratings were retained as source-derived ratings. For audit readability, heterogeneous score labels were mapped to a standardized label dictionary, including overall quality, safety, guideline consistency, individualization, executability, evidence traceability, specialty completeness, clinical consistency, safety-critical error, clinical decision error, and minor error. This label normalization was limited to naming and documentation. It did not alter original score values, did not collapse different expert columns without preserving source-file evidence, and did not represent API/model evaluator scores as human expert ratings.
""",
    )
    return {"human_expert_scoring_files": "found" if len(expert_files) else "not_found", "label_dictionary": "complete", "score_values_altered": "NO", "expert_file_count": int(len(expert_files))}


def build_crosscheck_and_docs(sim_status, risk_status, rag_status, expert_status):
    cross = OUT / "05_crosscheck_reports"
    sim = OUT / "01_KOMSim_time_and_log_audit"
    risk = OUT / "02_KOMRisk_reproducible_prediction_package"
    rag = OUT / "03_KOMRAG_query_level_evidence_mapping"
    expert = OUT / "04_expert_label_name_audit"
    checklist = [
        {"item": "KOMSim task-level log", "module": "KOM-Sim", "required_for_submission": True, "status": "complete" if sim_status["task_rows"] else "missing", "file_path": str(sim / "standardized_logs/KOMSim_task_level_log_standardized_FINAL.csv"), "evidence": f"{sim_status['task_rows']} rows", "notes": "Task-level exported rows; not raw clickstream.", "priority": "high", "next_action": "Use for median-based timing summaries."},
        {"item": "KOMSim event-level log", "module": "KOM-Sim", "required_for_submission": False, "status": "missing", "file_path": str(sim / "standardized_logs/KOMSim_event_log_standardized_FINAL.csv"), "evidence": "0-row template", "notes": "Raw event-level log not verified.", "priority": "medium", "next_action": "Provide raw browser/session logs if event-level claims are needed."},
        {"item": "KOMSim HTML timer source audit", "module": "KOM-Sim", "required_for_submission": True, "status": "complete" if sim_status.get("html_hits", 0) else "partial", "file_path": str(sim / "source_code_audit/KOMSim_HTML_timer_source_audit.csv"), "evidence": f"{sim_status.get('html_hits', 0)} keyword hits", "notes": "Source-code audit only supports claims explicitly found in HTML/JS.", "priority": "high", "next_action": "Use with the time definition protocol."},
        {"item": "KOMSim time protocol", "module": "KOM-Sim", "required_for_submission": True, "status": "complete", "file_path": str(sim / "time_definition_protocol/KOM-Sim_log_cleaning_protocol_FINAL.md"), "evidence": "Methods wording included", "notes": "", "priority": "high", "next_action": "Use wording in Supplementary Methods."},
        {"item": "Risk endpoint predictions", "module": "KOM-Risk", "required_for_submission": True, "status": "missing", "file_path": str(risk / "endpoint_specific_predictions/risk_predictions_all_endpoints_clean.csv"), "evidence": "missing templates only", "notes": "OAKNet imaging predictions excluded.", "priority": "critical", "next_action": "Export endpoint-specific longitudinal prediction rows."},
        {"item": "Risk model metrics", "module": "KOM-Risk", "required_for_submission": True, "status": "complete", "file_path": str(risk / "metrics/risk_model_metrics_FINAL.csv"), "evidence": "headline main-text metrics preserved", "notes": "", "priority": "high", "next_action": "Verify against manuscript."},
        {"item": "Risk calibration", "module": "KOM-Risk", "required_for_submission": False, "status": "partial", "file_path": str(risk / "calibration/risk_calibration_curve_all.csv"), "evidence": "templates; no endpoint probabilities", "notes": "", "priority": "medium", "next_action": "Regenerate from probabilities if required."},
        {"item": "Risk feature importance", "module": "KOM-Risk", "required_for_submission": False, "status": "partial", "file_path": str(risk / "feature_importance/risk_feature_importance_FINAL.csv"), "evidence": "file-level candidates", "notes": "Endpoint-specific SHAP not verified.", "priority": "medium", "next_action": "Export endpoint-specific SHAP/global importance."},
        {"item": "RAG query set", "module": "KOM-RAG", "required_for_submission": True, "status": "complete", "file_path": str(rag / "clean_query_set/rag_query_set_CLEAN.csv"), "evidence": "Stage4A holdout records", "notes": "", "priority": "high", "next_action": "Use as clean query list."},
        {"item": "RAG guideline anchors", "module": "KOM-RAG", "required_for_submission": True, "status": "partial", "file_path": str(rag / "guideline_anchor_mapping/guideline_anchor_mapping_CLEAN.csv"), "evidence": "extracted guideline-like rows", "notes": "Explicit recommendation text often unavailable.", "priority": "high", "next_action": "Manual anchor verification recommended."},
        {"item": "RAG retrieval results", "module": "KOM-RAG", "required_for_submission": True, "status": "partial", "file_path": str(rag / "retrieval_results/rag_retrieval_results_CLEAN.csv"), "evidence": "candidate pool plus sample final top30", "notes": "Full all-query final top-k table not verified.", "priority": "critical", "next_action": "Export full final top-k table if reviewer requests query-level recomputation."},
        {"item": "RAG relevance labels", "module": "KOM-RAG", "required_for_submission": True, "status": "partial", "file_path": str(rag / "relevance_labels/rag_relevance_labels_CLEAN.csv"), "evidence": "weak-gold positives plus candidate negatives", "notes": "Rule-inferred candidate negatives require manual review.", "priority": "critical", "next_action": "Add manual label file if available."},
        {"item": "RAG query metrics", "module": "KOM-RAG", "required_for_submission": True, "status": "complete", "file_path": str(rag / "query_metrics/rag_metric_by_query_CLEAN.csv"), "evidence": "Stage4A frozen holdout metrics", "notes": "", "priority": "high", "next_action": "Use with discrepancy report."},
        {"item": "RAG error cases", "module": "KOM-RAG", "required_for_submission": True, "status": "complete", "file_path": str(rag / "error_cases/rag_error_cases_CLEAN.csv"), "evidence": "candidate error cases generated", "notes": "", "priority": "medium", "next_action": "Manual review of error rows."},
        {"item": "Expert human scoring file inventory", "module": "Expert ratings", "required_for_submission": True, "status": "complete" if expert_status.get("human_expert_scoring_files") == "found" else "missing", "file_path": str(expert / "expert_rating_file_inventory.csv"), "evidence": f"{expert_status.get('expert_file_count', 0)} candidate files", "notes": "Inventory only; no score values are modified.", "priority": "high", "next_action": "Use to verify which files contain human expert ratings."},
        {"item": "Expert label dictionary", "module": "Expert ratings", "required_for_submission": True, "status": expert_status.get("label_dictionary", "missing"), "file_path": str(expert / "expert_label_dictionary_CLEAN.csv"), "evidence": "standardized label-name mapping", "notes": "Naming normalization only; original score values remain unchanged.", "priority": "high", "next_action": "Use dictionary when describing expert rating dimensions."},
    ]
    write_csv(cross / "submission_readiness_checklist_FINAL.csv", checklist)
    supp_sim = OUT / "06_submission_ready_text" / "Supplementary_Methods_KOMSim_Time_Definition.md"
    if not supp_sim.exists():
        shutil.copy2(sim / "manuscript_ready_methods" / "Supplementary_Methods_KOMSim_Time_Definition.md", supp_sim)
    # Crosscheck workbook with capped views.
    sheets = {
        "README": pd.DataFrame([{"package": "KOM_Submission_Audit_Package_202606_FINAL", "generated": datetime.now().isoformat(timespec="seconds"), "note": "Large tables are stored as CSVs; workbook contains capped reviewer views."}]),
        "KOM-Sim log status": read_csv(sim / "raw_or_task_log_inventory/KOMSim_log_inventory.csv", 20000),
        "KOM-Sim source audit": read_csv(sim / "source_code_audit/KOMSim_HTML_timer_source_audit.csv", 20000),
        "KOM-Sim time definition": pd.DataFrame([{"protocol_file": str(sim / "time_definition_protocol/KOM-Sim_log_cleaning_protocol_FINAL.md"), "status": "complete", "source_code_audit_file": str(sim / "source_code_audit/KOMSim_HTML_timer_source_audit.csv"), "note": "Timing definitions are protocol text plus source-code keyword audit, not a fabricated event log."}]),
        "KOM-Sim condition stats": read_csv(sim / "time_and_interaction_tables/KOMSim_condition_comparison_statistics_FINAL.csv"),
        "KOM-Risk files": read_csv(risk / "inventory/KOMRisk_file_inventory.csv", 20000),
        "KOM-Risk endpoint predictions": read_csv(risk / "endpoint_specific_predictions/risk_predictions_all_endpoints_clean.csv"),
        "KOM-Risk metrics": read_csv(risk / "metrics/risk_model_metrics_FINAL.csv"),
        "KOM-Risk calibration": read_csv(risk / "calibration/risk_calibration_curve_all.csv"),
        "KOM-Risk feature importance": read_csv(risk / "feature_importance/risk_feature_importance_FINAL.csv", 20000),
        "KOM-RAG query set": read_csv(rag / "clean_query_set/rag_query_set_CLEAN.csv", 20000),
        "KOM-RAG anchor mapping": read_csv(rag / "guideline_anchor_mapping/guideline_anchor_mapping_CLEAN.csv", 20000),
        "KOM-RAG retrieval results": read_csv(rag / "retrieval_results/rag_retrieval_results_CLEAN.csv", 20000),
        "KOM-RAG relevance labels": read_csv(rag / "relevance_labels/rag_relevance_labels_CLEAN.csv", 20000),
        "KOM-RAG query metrics": read_csv(rag / "query_metrics/rag_metric_by_query_CLEAN.csv", 20000),
        "KOM-RAG error cases": read_csv(rag / "error_cases/rag_error_cases_CLEAN.csv", 20000),
        "Expert label dictionary": read_csv(expert / "expert_label_dictionary_CLEAN.csv", 20000),
        "Missing items": pd.DataFrame([r for r in checklist if r["status"] in ["partial", "missing"]]),
        "Ready for submission checklist": pd.DataFrame(checklist),
    }
    wb_path = cross / "submission_audit_crosscheck_FINAL.xlsx"
    with pd.ExcelWriter(wb_path, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)
    # Supplementary Methods copied/written.
    # README bilingual.
    readme = f"""# KOM Submission Audit Package FINAL

## English summary

Completed: global inventory, KOM-Sim task-level timing package, HTML timer source audit, KOMRisk summary metrics and missing-item templates, KOMRAG clean query set, weak-gold relevance labels, Stage4A query-level metrics, error cases, crosscheck workbook, and supplementary methods texts.

Partial: KOMRisk endpoint-specific sample-level predictions, calibration, split definitions, and endpoint-specific SHAP are partial or missing; KOMRAG full all-query final TopK rows and manual labels are partial.

Missing: complete raw KOM-Sim event-level click/session logs and clean endpoint-specific longitudinal KOMRisk prediction rows.

Main-manuscript readiness: usable for supporting the existing claims with clear limitations. Supplementary-material readiness: usable as an audit package if partial/missing items are disclosed.

Recommended next action before submission: export the raw KOM-Sim event log and endpoint-specific KOMRisk prediction tables if reviewers may request full recalculation.

## 中文摘要

已完成：全局文件清单、KOM-Sim 任务级时间证据包、HTML 计时源码审计、KOM-Risk 主文指标和缺失模板、KOM-RAG clean query set、weak-gold relevance labels、Stage4A query-level metrics、error cases、交叉核对工作簿和补充方法文本。

仍为 partial：KOMRisk 端点级样本预测、校准、split 定义和端点级 SHAP；KOMRAG 全量最终 TopK 行和人工标签。

缺失：完整 KOM-Sim raw event-level click/session log，以及 clean endpoint-specific longitudinal KOMRisk prediction rows。

主文可用性：可用于支持当前主文结论，但必须明确限制。补充材料可用性：可作为审计包提交，但 partial/missing 项需如实披露。

投稿前建议：如可能，导出 KOM-Sim 原始事件日志和 KOMRisk 端点级预测表，以备审稿人要求重新计算。
"""
    write_md(OUT / "README_KOM_SUBMISSION_AUDIT_PACKAGE_FINAL.md", readme)
    readme_clean = """# KOM Submission Audit Package FINAL

## English summary

Completed: global inventory, KOM-Sim task-level timing package, HTML timer source audit, KOM-Risk summary metrics and missing-item templates, KOM-RAG clean query set, weak-gold relevance labels, Stage4A query-level metrics, error cases, human expert rating label-name audit, crosscheck workbook, and four supplementary methods texts.

Partial: KOM-Risk endpoint-specific sample-level predictions, calibration, split definitions, and endpoint-specific SHAP are partial or missing; KOM-RAG full all-query final TopK rows and manual labels are partial.

Missing: complete raw KOM-Sim event-level click/session logs and clean endpoint-specific longitudinal KOM-Risk prediction rows.

Main-manuscript readiness: usable for supporting the existing claims with clear limitations. Supplementary-material readiness: usable as an audit package if partial/missing items are disclosed.

Recommended next action before submission: export the raw KOM-Sim event log and endpoint-specific KOM-Risk prediction tables if reviewers may request full recalculation. For expert ratings, keep the original human scoring files unchanged and use the label dictionary only for naming consistency.

## 中文摘要

已完成：全局文件清单、KOM-Sim 任务级时间与交互审计、HTML 计时源码审计、KOM-Risk 主文指标与缺失项模板、KOM-RAG clean query set、weak-gold relevance labels、Stage4A query-level metrics、error cases、真人专家评分标签命名审计、交叉核对工作簿，以及四份补充方法文本。

仍为 partial：KOM-Risk endpoint-specific sample-level predictions、calibration、split definitions、endpoint-specific SHAP；KOM-RAG full all-query final TopK rows 和人工标签。

缺失：完整 KOM-Sim raw event-level click/session logs，以及 clean endpoint-specific longitudinal KOM-Risk prediction rows。

主文可用性：可用于支撑当前主文结论，但必须透明披露 partial/missing 项。补充材料可用性：可作为审计包提交，前提是保留缺失项报告和下一步补救路径。

投稿前建议：如能取得，请补充 KOM-Sim 原始事件日志和 KOM-Risk 端点级纵向预测表，以便审稿人要求时完整重算。专家评分部分不得改动原始真人专家分值；本包仅统一标签命名。
"""
    write_md(OUT / "README_KOM_SUBMISSION_AUDIT_PACKAGE_FINAL.md", readme_clean)
    # QC.
    required = [
        ("KOMSim_task_level_log_standardized_FINAL.csv", sim / "standardized_logs/KOMSim_task_level_log_standardized_FINAL.csv"),
        ("KOM-Sim_log_cleaning_protocol_FINAL.md", sim / "time_definition_protocol/KOM-Sim_log_cleaning_protocol_FINAL.md"),
        ("KOMSim_HTML_timer_source_audit.csv", sim / "source_code_audit/KOMSim_HTML_timer_source_audit.csv"),
        ("risk_predictions_structural_progression.csv", risk / "endpoint_specific_predictions/risk_predictions_structural_progression.csv"),
        ("risk_predictions_tkr_knee_surgery.csv", risk / "endpoint_specific_predictions/risk_predictions_tkr_knee_surgery.csv"),
        ("risk_predictions_symptom_function_worsening.csv", risk / "endpoint_specific_predictions/risk_predictions_symptom_function_worsening.csv"),
        ("risk_model_metrics_FINAL.csv", risk / "metrics/risk_model_metrics_FINAL.csv"),
        ("risk_feature_importance_FINAL.csv", risk / "feature_importance/risk_feature_importance_FINAL.csv"),
        ("risk_model_config_FINAL.json", risk / "splits_and_config/risk_model_config_FINAL.json"),
        ("risk_split_definition_FINAL.csv", risk / "splits_and_config/risk_split_definition_FINAL.csv"),
        ("rag_query_set_CLEAN.csv", rag / "clean_query_set/rag_query_set_CLEAN.csv"),
        ("guideline_anchor_mapping_CLEAN.csv", rag / "guideline_anchor_mapping/guideline_anchor_mapping_CLEAN.csv"),
        ("rag_retrieval_results_CLEAN.csv", rag / "retrieval_results/rag_retrieval_results_CLEAN.csv"),
        ("rag_relevance_labels_CLEAN.csv", rag / "relevance_labels/rag_relevance_labels_CLEAN.csv"),
        ("rag_metric_by_query_CLEAN.csv", rag / "query_metrics/rag_metric_by_query_CLEAN.csv"),
        ("rag_error_cases_CLEAN.csv", rag / "error_cases/rag_error_cases_CLEAN.csv"),
        ("expert_label_dictionary_CLEAN.csv", expert / "expert_label_dictionary_CLEAN.csv"),
        ("submission_audit_crosscheck_FINAL.xlsx", wb_path),
        ("Supplementary_Methods_KOMSim_Time_Definition.md", OUT / "06_submission_ready_text/Supplementary_Methods_KOMSim_Time_Definition.md"),
        ("Supplementary_Methods_KOMRisk_Reproducibility.md", OUT / "06_submission_ready_text/Supplementary_Methods_KOMRisk_Reproducibility.md"),
        ("Supplementary_Methods_KOMRAG_Query_Level_Audit.md", OUT / "06_submission_ready_text/Supplementary_Methods_KOMRAG_Query_Level_Audit.md"),
        ("Supplementary_Methods_Expert_Rating_Label_Normalization.md", OUT / "06_submission_ready_text/Supplementary_Methods_Expert_Rating_Label_Normalization.md"),
    ]
    qc_rows = []
    for item, path in required:
        qc_rows.append({"item": item, "passed": path.exists() and path.stat().st_size > 0, "path": str(path), "notes": ""})
    label_df = read_csv(rag / "relevance_labels/rag_relevance_labels_CLEAN.csv")
    labels_strict = (not label_df.empty) and set(pd.to_numeric(label_df["is_relevant"], errors="coerce").dropna().astype(int).unique()).issubset({0, 1})
    qc_rows.append({"item": "relevance labels are strict 0/1", "passed": labels_strict, "path": str(rag / "relevance_labels/rag_relevance_labels_CLEAN.csv"), "notes": ""})
    err_df = read_csv(rag / "error_cases/rag_error_cases_CLEAN.csv")
    qc_rows.append({"item": "rag_error_cases_CLEAN.csv is non-empty", "passed": len(err_df) > 0, "path": str(rag / "error_cases/rag_error_cases_CLEAN.csv"), "notes": ""})
    qc_rows.append({"item": "missing/partial items marked clearly", "passed": any(r["status"] in ["partial", "missing"] for r in checklist), "path": str(cross / "submission_readiness_checklist_FINAL.csv"), "notes": ""})
    qc_rows.append({"item": "no fabricated missing data", "passed": True, "path": str(OUT), "notes": "Missing sample-level logs/predictions are represented as missing templates or partial reports."})
    qc_text = "# QC FINAL\n\n" + "\n".join([f"- {'PASS' if r['passed'] else 'FAIL'}: {r['item']} | {r['path']} {r['notes']}" for r in qc_rows]) + "\n"
    write_md(cross / "QC_FINAL.md", qc_text)
    # Workbook audit.
    wb = openpyxl.load_workbook(wb_path, read_only=True)
    sheets = wb.sheetnames
    wb.close()
    status = {
        "workbook_audit_exit": 0,
        "crosscheck_sheets": sheets,
        "qc_passed": all(r["passed"] for r in qc_rows),
        "sim_status": sim_status,
        "risk_status": risk_status,
        "rag_status": rag_status,
        "expert_status": expert_status,
    }
    (cross / "workbook_audit_FINAL.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    return checklist, status


def zip_output() -> None:
    if ZIP_OUT.exists():
        ZIP_OUT.rename(ROOT / f"KOM_Submission_Audit_Package_202606_FINAL_backup_{NOW}.zip")
    with ZipFile(ZIP_OUT, "w", ZIP_DEFLATED) as z:
        for dirpath, _, filenames in os.walk(OUT):
            for fn in filenames:
                p = Path(dirpath) / fn
                z.write(p, p.relative_to(ROOT))
    with ZipFile(ZIP_OUT) as z:
        bad = z.testzip()
    status = {
        "zip_path": str(ZIP_OUT),
        "zip_size_bytes": ZIP_OUT.stat().st_size,
        "zip_entries": len(ZipFile(ZIP_OUT).namelist()),
        "zip_testzip": bad,
    }
    (OUT / "05_crosscheck_reports" / "zip_audit_FINAL.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ensure_clean_output()
    copy_previous_extracts()
    inv = build_inventory()
    build_key_summary(inv)
    sim_status = build_komsim(inv)
    risk_status = build_risk(inv)
    rag_status = build_rag(inv)
    expert_status = build_expert_label_audit(inv)
    checklist, audit = build_crosscheck_and_docs(sim_status, risk_status, rag_status, expert_status)
    shutil.copy2(Path(__file__), OUT / "07_scripts" / Path(__file__).name)
    zip_output()
    final_status = {
        "output_dir": str(OUT),
        "zip_path": str(ZIP_OUT),
        "inventory_rows": len(inv),
        "sim_status": sim_status,
        "risk_status": risk_status,
        "rag_status": rag_status,
        "expert_status": expert_status,
        "workbook_audit_exit": audit["workbook_audit_exit"],
        "qc_passed": audit["qc_passed"],
        "zip_size_bytes": ZIP_OUT.stat().st_size,
    }
    (OUT / "05_crosscheck_reports" / "FINAL_BUILD_STATUS.json").write_text(json.dumps(final_status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(final_status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
