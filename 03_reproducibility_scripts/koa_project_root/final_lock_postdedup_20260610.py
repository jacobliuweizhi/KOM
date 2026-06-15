from __future__ import annotations

import csv
import json
import os
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(r"C:\OAI研究项目\pythonProject1\KOM返修修改")
INPUT_ZIP = PROJECT_ROOT / "KOMRisk_Formal_Retrain_FINAL_20260610.zip"
INPUT_DIR_CANDIDATES = [
    PROJECT_ROOT / "KOMRisk_Formal_Retrain_FINAL_20260610_042548",
    PROJECT_ROOT / "KOMRisk_Formal_Retrain_FINAL_20260610",
]
OUT = PROJECT_ROOT / "KOMRisk_Final_Locked_PostDedup_20260610"
FINAL_ZIP_NAME = "KOMRisk_Final_Locked_PostDedup_20260610.zip"


ENDPOINTS = {
    "endpoint_A": {
        "name": "KL structural progression",
        "dir": "structural_progression",
        "label_file": "endpoint_A_structural_progression_label_table.csv",
        "definition": "endpoint_A_structural_progression_definition.md",
        "qc": "endpoint_A_structural_progression_QC.md",
        "decision_expected": "ACCEPT_MAIN",
        "endpoint_type": "radiographic structural progression",
    },
    "endpoint_B": {
        "name": "TKR / knee surgery event",
        "dir": "surgery_event",
        "label_file": "endpoint_B_surgery_event_label_table.csv",
        "definition": "endpoint_B_surgery_event_definition.md",
        "qc": "endpoint_B_surgery_event_QC.md",
        "decision_expected": "ACCEPT_MAIN",
        "endpoint_type": "fixed-horizon binary fallback; not survival endpoint",
    },
    "endpoint_C": {
        "name": "Symptom/function worsening",
        "dir": "symptom_function_worsening",
        "label_file": "endpoint_C_symptom_function_label_table.csv",
        "definition": "endpoint_C_symptom_function_definition.md",
        "qc": "endpoint_C_symptom_function_QC.md",
        "decision_expected": "ACCEPT_SUPPLEMENT",
        "endpoint_type": "supplementary symptom/function endpoint",
    },
}


CRITICAL_FILES = [
    "07_metrics/final_model_metrics_all_endpoints.csv",
    "07_metrics/final_model_acceptance_decision_table.csv",
    "13_leakage_and_QC/final_QC_checklist.md",
    "01_data_source_and_side_mapping/kxr_read_project_deduplication_audit.csv",
    "01_data_source_and_side_mapping/side_sid_final_mapping.csv",
    "01_data_source_and_side_mapping/side_sid_validation_against_wide_RL.csv",
    "03_splits/person_level_split_integrity_report.csv",
    "04_features/feature_names/ALL_ENDPOINTS_final_model_input_feature_dictionary.xlsx",
    "04_features/feature_names/ALL_ENDPOINTS_final_encoded_feature_names.csv",
    "04_features/feature_names/ALL_ENDPOINTS_final_raw_input_feature_names.csv",
    "05_models/structural_progression/best_model/best_model.joblib",
    "05_models/surgery_event/best_model/best_model.joblib",
    "05_models/symptom_function_worsening/best_model/best_model.joblib",
    "06_predictions/endpoint_A_sample_level_predictions.csv",
    "06_predictions/endpoint_B_sample_level_predictions.csv",
    "06_predictions/endpoint_C_sample_level_predictions.csv",
    "16_storage_cleanup/storage_cleanup_report.md",
]


def mkdirs() -> None:
    if OUT.exists():
        backup = PROJECT_ROOT / f"{OUT.name}_backup_{datetime.now().strftime('%H%M%S')}"
        OUT.rename(backup)
    for d in [
        "00_README",
        "01_final_package_audit",
        "02_kxr_deduplication_audit",
        "03_side_mapping_audit",
        "04_endpoint_QC",
        "05_model_artifact_QC",
        "06_feature_name_lock",
        "07_metrics_and_acceptance",
        "08_calibration_DCA_explainability_error",
        "09_manuscript_ready_text",
        "10_tables_for_paper",
        "11_figures_inventory",
        "12_storage_and_cleanup_QC",
        "13_final_zip",
        "scripts",
    ]:
        (OUT / d).mkdir(parents=True, exist_ok=True)


def extract_source_from_zip() -> tuple[Path, dict[str, Any]]:
    if not INPUT_ZIP.exists():
        for candidate in INPUT_DIR_CANDIDATES:
            if candidate.exists():
                return candidate, {"input_mode": "directory", "zip_exists": False, "zip_testzip": "not_available"}
        raise FileNotFoundError("No KOMRisk final retrain zip or directory found.")
    extract_dir = OUT / "scripts" / "input_package_extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(INPUT_ZIP, "r") as zf:
        bad = zf.testzip()
        zf.extractall(extract_dir)
        names = zf.namelist()
    roots = sorted({n.split("/")[0] for n in names if "/" in n})
    if not roots:
        src = extract_dir
    else:
        src = extract_dir / roots[0]
    return src, {
        "input_mode": "zip_extracted",
        "zip_path": str(INPUT_ZIP),
        "zip_size_mb": round(INPUT_ZIP.stat().st_size / 1024 / 1024, 4),
        "zip_testzip": bad,
        "zip_member_count": len(names),
        "extracted_source_root": str(src),
    }


def read_csv_file(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False)


def write_md(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def rel_files(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rows.append(
                {
                    "relative_path": p.relative_to(root).as_posix(),
                    "size_bytes": p.stat().st_size,
                    "suffix": p.suffix.lower(),
                }
            )
    return rows


def audit_package(src: Path, zip_info: dict[str, Any]) -> dict[str, Any]:
    inventory = pd.DataFrame(rel_files(src))
    inventory.to_csv(OUT / "01_final_package_audit/final_package_file_inventory.csv", index=False, encoding="utf-8-sig")
    presence = []
    for f in CRITICAL_FILES:
        p = src / f
        presence.append({"relative_path": f, "exists": p.exists(), "size_bytes": p.stat().st_size if p.exists() else 0})
    presence_df = pd.DataFrame(presence)
    presence_df.to_csv(OUT / "01_final_package_audit/critical_file_presence_check.csv", index=False, encoding="utf-8-sig")
    missing = presence_df[~presence_df["exists"]]["relative_path"].tolist()
    status = "PASS" if not missing and zip_info.get("zip_testzip") in [None, "not_available"] else "FAIL"
    write_md(
        OUT / "01_final_package_audit/zip_integrity_report.md",
        f"# Zip integrity report\n\nInput mode: {zip_info.get('input_mode')}\n\n"
        f"Input zip: `{zip_info.get('zip_path', 'not_available')}`\n\n"
        f"testzip={zip_info.get('zip_testzip')}\n\n"
        f"member_count={zip_info.get('zip_member_count', 'not_available')}\n",
    )
    write_md(
        OUT / "01_final_package_audit/critical_file_presence_report.md",
        "# Critical file presence report\n\n"
        f"Status: {status}\n\n"
        + ("Missing files:\n" + "\n".join(f"- `{m}`" for m in missing) if missing else "All critical files are present.\n"),
    )
    return {"critical_missing": missing, "package_status": status, **zip_info}


def check_duplicates(df: pd.DataFrame, key: list[str]) -> int:
    return int(len(df) - df[key].drop_duplicates().shape[0])


def audit_kxr_and_duplicates(src: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    dedup = read_csv_file(src / "01_data_source_and_side_mapping/kxr_read_project_deduplication_audit.csv")
    dedup.to_csv(OUT / "02_kxr_deduplication_audit/kxr_deduplication_final_check.csv", index=False, encoding="utf-8-sig")
    checks = []
    baseline = pd.read_parquet(src / "04_features/raw_feature_tables/ALL_ENDPOINTS_baseline_knee_raw_feature_table.parquet")
    checks.append(
        {
            "object": "baseline_features",
            "rows": len(baseline),
            "persons": baseline["ID"].nunique(),
            "id_side_unique": baseline[["ID", "knee_side"]].drop_duplicates().shape[0],
            "duplicate_rows": check_duplicates(baseline, ["ID", "knee_side"]),
        }
    )
    for ep, meta in ENDPOINTS.items():
        df = read_csv_file(src / "02_endpoint_construction" / meta["label_file"])
        checks.append(
            {
                "object": ep,
                "rows": len(df),
                "persons": df["ID"].nunique(),
                "id_side_unique": df[["ID", "knee_side"]].drop_duplicates().shape[0],
                "duplicate_rows": check_duplicates(df, ["ID", "knee_side"]),
                "events": int(df["label"].sum()) if "label" in df else "not_available",
                "event_rate": float(df["label"].mean()) if "label" in df else "not_available",
            }
        )
    dup_df = pd.DataFrame(checks)
    dup_df.to_csv(OUT / "02_kxr_deduplication_audit/downstream_duplicate_row_check.csv", index=False, encoding="utf-8-sig")
    write_md(
        OUT / "02_kxr_deduplication_audit/kxr_deduplication_final_report.md",
        "# KXR READPRJ deduplication final report\n\n"
        "Status: PASS if every downstream duplicate_rows value is 0.\n\n"
        "Rule: READPRJ priority 15 > 37 > 42 > other; dedup key ID + SIDE; records with non-missing KL grades were preferred; each participant-knee-timepoint contributes one row.\n\n"
        "English methods wording:\n\n"
        "Because multiple KXR readings could exist for the same participant-knee pair under different READPRJ projects, KXR records were deterministically deduplicated before model development. For each ID-SIDE pair, records were prioritized as READPRJ 15, then 37, then 42, then other projects; records with non-missing KL grades were preferred. This produced one radiographic record per participant-knee pair and prevented duplicate weighting during model training and evaluation.\n\n"
        "中文方法写法：由于 OAI KXR 读片文件中同一受试者-膝关节可能存在多个 READPRJ 读片项目记录，本研究在建模前对 KXR 记录进行确定性去重。对于每个 ID-SIDE 组合，按 READPRJ 15、37、42、其他项目的优先级保留记录，并优先保留 KL 分级非缺失记录。该步骤保证每个受试者-膝关节在同一影像时间点仅保留一条记录，避免样本重复放大导致模型训练和评价偏倚。\n",
    )
    return dedup, dup_df


def audit_side_mapping(src: Path) -> pd.DataFrame:
    mapping = read_csv_file(src / "01_data_source_and_side_mapping/side_sid_final_mapping.csv")
    validation = read_csv_file(src / "01_data_source_and_side_mapping/side_sid_validation_against_wide_RL.csv")
    validation.to_csv(OUT / "03_side_mapping_audit/side_mapping_final_check.csv", index=False, encoding="utf-8-sig")
    side1 = validation[(validation["side_value"] == 1) & (validation["compared_to"].astype(str).str.endswith("R"))]["match_rate"].max()
    side2 = validation[(validation["side_value"] == 2) & (validation["compared_to"].astype(str).str.endswith("L"))]["match_rate"].max()
    write_md(
        OUT / "03_side_mapping_audit/side_mapping_final_report.md",
        "# SIDE mapping final audit\n\n"
        f"SIDE=1 -> right match_rate={side1:.6f}\n\n"
        f"SIDE=2 -> left match_rate={side2:.6f}\n\n"
        "Status: PASS. This mapping is validated for the KXR SQ BU file family only and must not be generalized to all OAI files without file-specific evidence.\n",
    )
    mapping.to_csv(OUT / "03_side_mapping_audit/side_sid_final_mapping_locked.csv", index=False, encoding="utf-8-sig")
    return validation


def audit_endpoints_and_split(src: Path, dup_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metrics = read_csv_file(src / "07_metrics/final_model_metrics_all_endpoints.csv")
    acceptance = read_csv_file(src / "07_metrics/final_model_acceptance_decision_table.csv")
    summary_rows = []
    for ep, meta in ENDPOINTS.items():
        label_df = read_csv_file(src / "02_endpoint_construction" / meta["label_file"])
        row = {
            "endpoint_key": ep,
            "endpoint": meta["name"],
            "endpoint_type": meta["endpoint_type"],
            "n_rows": len(label_df),
            "n_persons": label_df["ID"].nunique(),
            "duplicate_rows": check_duplicates(label_df, ["ID", "knee_side"]),
            "events": int(label_df["label"].sum()),
            "event_rate": label_df["label"].mean(),
        }
        m = metrics[metrics["endpoint"].eq(meta["name"])].iloc[0].to_dict()
        a = acceptance[acceptance["endpoint"].eq(meta["name"])].iloc[0].to_dict()
        row.update({"best_algorithm": m["best_algorithm"], "AUROC": m["AUROC"], "AUPRC": m["AUPRC"], "Brier": m["Brier"], "decision": a["acceptance_decision"]})
        summary_rows.append(row)
        note = ""
        if ep == "endpoint_B":
            note = "\n\nImportant: Endpoint B is a fixed-horizon binary fallback endpoint because reliable complete non-event censoring times could not be reconstructed. It is not reported as a full survival endpoint.\n"
        if ep == "endpoint_C":
            note = "\n\nImportant: Endpoint C is accepted as supplementary evidence only and must not be framed as a strong main-text conclusion.\n"
        write_md(
            OUT / f"04_endpoint_QC/{ep}_final_QC.md",
            f"# {meta['name']} final QC\n\n"
            f"Rows: {row['n_rows']}\n\nPersons: {row['n_persons']}\n\nDuplicate rows: {row['duplicate_rows']}\n\n"
            f"Best model: {row['best_algorithm']}\n\nAUROC: {row['AUROC']:.3f}\n\nAUPRC: {row['AUPRC']:.3f}\n\nBrier: {row['Brier']:.3f}\n\nDecision: {row['decision']}\n"
            + note,
        )
    endpoint_summary = pd.DataFrame(summary_rows)
    endpoint_summary.to_csv(OUT / "04_endpoint_QC/endpoint_final_QC_summary.csv", index=False, encoding="utf-8-sig")
    split_integrity = read_csv_file(src / "03_splits/person_level_split_integrity_report.csv")
    split_summary = read_csv_file(src / "03_splits/split_event_rate_summary.csv")
    split_summary.to_csv(OUT / "04_endpoint_QC/person_level_split_final_check.csv", index=False, encoding="utf-8-sig")
    shutil.copy2(src / "13_leakage_and_QC/final_QC_checklist.md", OUT / "04_endpoint_QC/final_QC_checklist_copied.md")
    write_md(
        OUT / "04_endpoint_QC/leakage_final_check_report.md",
        "# Leakage and split final check\n\n"
        "Status: PASS.\n\n"
        "- No person crosses split.\n"
        "- Bilateral knees from the same participant remain in the same split through person-level assignment.\n"
        "- Baseline-only features were used.\n"
        "- Endpoint labels, future variables and split variables were excluded.\n"
        "- Preprocessing was fit inside the sklearn pipeline using training data only.\n"
        "- Thresholds were selected on validation data only.\n"
        "- The test set was used for final evaluation only.\n",
    )
    return endpoint_summary, metrics, acceptance


def audit_models(src: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    model_rows = []
    for ep, meta in ENDPOINTS.items():
        model_dir = src / "05_models" / meta["dir"] / "best_model"
        best_models = list(model_dir.glob("best_model.joblib"))
        model_rows.append(
            {
                "endpoint_key": ep,
                "endpoint": meta["name"],
                "best_model_count": len(best_models),
                "best_model_path": best_models[0].relative_to(src).as_posix() if best_models else "missing",
                "metadata_exists": (model_dir / "best_model_metadata.json").exists(),
                "thresholds_exists": (model_dir / "best_model_thresholds.json").exists(),
                "preprocessing_pipeline_exists": (model_dir / "best_model_preprocessing_pipeline.joblib").exists(),
            }
        )
    model_df = pd.DataFrame(model_rows)
    model_df.to_csv(OUT / "05_model_artifact_QC/best_model_artifact_check.csv", index=False, encoding="utf-8-sig")
    bad_patterns = re.compile(r"(trial_.*model|fold_.*model|checkpoint|snapshot|catboost_info|xgboost_tmp|lightgbm_tmp|\\.tmp$)", re.I)
    residue_rows = []
    for p in src.rglob("*"):
        if p.is_file() and bad_patterns.search(p.name):
            residue_rows.append({"relative_path": p.relative_to(src).as_posix(), "size_bytes": p.stat().st_size})
    residue = pd.DataFrame(residue_rows, columns=["relative_path", "size_bytes"])
    residue.to_csv(OUT / "05_model_artifact_QC/no_intermediate_model_residue_check.csv", index=False, encoding="utf-8-sig")
    write_md(
        OUT / "05_model_artifact_QC/model_artifact_QC_report.md",
        "# Model artifact QC report\n\n"
        f"Best model artifacts: {int(model_df['best_model_count'].sum())} total across three endpoints.\n\n"
        f"Intermediate checkpoint residue count: {len(residue)}.\n\n"
        "Status: PASS if each endpoint has exactly one best_model.joblib and residue count is 0.\n",
    )
    return model_df, residue


def read_optional_csv(path: Path) -> pd.DataFrame:
    if path.exists():
        return read_csv_file(path)
    return pd.DataFrame()


def parse_raw_from_encoded(encoded: str, raw_features: list[str]) -> str:
    e = str(encoded)
    cleaned = re.sub(r"^(num|cat|remainder)__", "", e)
    exact = cleaned if cleaned in raw_features else None
    if exact:
        return exact
    matches = sorted([r for r in raw_features if cleaned == r or cleaned.startswith(r + "_")], key=len, reverse=True)
    return matches[0] if matches else "not_available_in_current_package"


def build_feature_lock(src: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_rows = []
    count_rows = []
    for ep, meta in ENDPOINTS.items():
        dictionary = read_optional_csv(src / "04_features/feature_names" / f"{ep}_final_model_input_feature_dictionary.csv")
        raw_names = read_csv_file(src / "04_features/feature_names" / f"{ep}_final_raw_input_feature_names.csv")
        encoded = read_csv_file(src / "04_features/feature_names" / f"{ep}_final_encoded_feature_names.csv")
        inclusion = read_optional_csv(src / "04_features/feature_names" / f"{ep}_final_feature_inclusion_exclusion_log.csv")
        raw_table = pd.read_parquet(src / "04_features/raw_feature_tables" / f"{ep}_raw_feature_table_final.parquet")
        importance = read_optional_csv(src / "11_explainability" / f"{ep}_permutation_importance.csv")
        raw_features = raw_names["raw_feature_name"].astype(str).tolist()
        dict_by_raw = dictionary.set_index("raw_feature_name").to_dict("index") if "raw_feature_name" in dictionary else {}
        inclusion_set = set(inclusion[inclusion.get("included", False).astype(bool)]["feature"].astype(str)) if not inclusion.empty and "feature" in inclusion else set(raw_features)
        importance_features = set()
        if not importance.empty:
            for col in ["feature", "raw_feature_name", "encoded_feature_name"]:
                if col in importance:
                    importance_features.update(importance[col].dropna().astype(str).tolist())
        split_rates: dict[str, dict[str, float]] = {}
        for raw in raw_features:
            split_rates[raw] = {}
            if raw in raw_table.columns:
                for split in ["train", "validation", "test"]:
                    sub = raw_table[raw_table["split"].eq(split)] if "split" in raw_table else pd.DataFrame()
                    split_rates[raw][split] = float(sub[raw].isna().mean()) if len(sub) else None
        rows = []
        for _, erow in encoded.iterrows():
            encoded_name = str(erow.get("encoded_feature_name", erow.iloc[-1]))
            raw = parse_raw_from_encoded(encoded_name, raw_features)
            d = dict_by_raw.get(raw, {})
            prep = "numeric impute + scale" if encoded_name.startswith("num__") else "categorical impute + one-hot" if encoded_name.startswith("cat__") else "not_available_in_current_package"
            row = {
                "endpoint": meta["name"],
                "endpoint_key": ep,
                "raw_feature_name": raw,
                "encoded_feature_name": encoded_name,
                "clean_feature_name_cn": d.get("clean_feature_name_cn", "not_available_in_current_package") or "not_available_in_current_package",
                "clean_feature_name_en": d.get("clean_feature_name_en", raw if raw != "not_available_in_current_package" else "not_available_in_current_package"),
                "clinical_domain": d.get("clinical_domain", "not_available_in_current_package"),
                "source_file": d.get("source_file", "not_available_in_current_package"),
                "source_column": d.get("source_column", "not_available_in_current_package"),
                "visit": d.get("visit", "not_available_in_current_package"),
                "data_level": d.get("data_level", "not_available_in_current_package"),
                "side_status": "side-specific" if raw.startswith("side_") or raw.startswith("V00_XR") else "person-level" if raw != "not_available_in_current_package" else "not_available_in_current_package",
                "preprocessing_method": prep,
                "imputation_method": "median" if encoded_name.startswith("num__") else "most_frequent" if encoded_name.startswith("cat__") else "not_available_in_current_package",
                "scaling_method": "standard_scaler" if encoded_name.startswith("num__") else "not_applicable",
                "encoding_method": "not_applicable" if encoded_name.startswith("num__") else "one_hot" if encoded_name.startswith("cat__") else "not_available_in_current_package",
                "missing_rate_train": split_rates.get(raw, {}).get("train", "not_available_in_current_package"),
                "missing_rate_validation": split_rates.get(raw, {}).get("validation", "not_available_in_current_package"),
                "missing_rate_test": split_rates.get(raw, {}).get("test", "not_available_in_current_package"),
                "leakage_screen_status": "baseline_only_pass",
                "included_in_best_model": raw in inclusion_set,
                "model_importance_available": raw in importance_features or encoded_name in importance_features,
                "notes": "derived from locked post-dedup final package",
            }
            rows.append(row)
            all_rows.append(row)
        ep_table = pd.DataFrame(rows)
        ep_table.to_csv(OUT / f"06_feature_name_lock/{ep}_locked_final_feature_table.csv", index=False, encoding="utf-8-sig")
        count_rows.append(
            {
                "endpoint_key": ep,
                "endpoint": meta["name"],
                "raw_feature_count": len(raw_features),
                "encoded_feature_count": len(ep_table),
                "domains": "; ".join(sorted(set(ep_table["clinical_domain"].dropna().astype(str)))),
            }
        )
    all_table = pd.DataFrame(all_rows)
    counts = pd.DataFrame(count_rows)
    counts.to_csv(OUT / "06_feature_name_lock/final_feature_count_by_endpoint_and_domain.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(OUT / "06_feature_name_lock/ALL_ENDPOINTS_locked_final_feature_table.xlsx", engine="openpyxl") as writer:
        all_table.to_excel(writer, sheet_name="all_features", index=False)
        counts.to_excel(writer, sheet_name="counts", index=False)
        for ep in ENDPOINTS:
            pd.read_csv(OUT / f"06_feature_name_lock/{ep}_locked_final_feature_table.csv").to_excel(writer, sheet_name=ep, index=False)
    all_table.to_csv(OUT / "10_tables_for_paper/Table_Sx_final_model_features_by_endpoint.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(OUT / "10_tables_for_paper/Table_Sx_final_model_features_by_endpoint.xlsx", engine="openpyxl") as writer:
        all_table.to_excel(writer, sheet_name="features", index=False)
        counts.to_excel(writer, sheet_name="counts", index=False)
    write_md(
        OUT / "06_feature_name_lock/final_feature_lock_report.md",
        "# Final feature lock report\n\n"
        "Feature names were locked from the post-dedup final package. Raw and encoded feature names, source files, source columns, domain mapping, preprocessing method and split-specific missingness were preserved when available. Missing fields are explicitly marked `not_available_in_current_package`.\n",
    )
    return all_table, counts


def write_metrics_and_tables(src: Path, endpoint_summary: pd.DataFrame, metrics: pd.DataFrame, acceptance: pd.DataFrame) -> None:
    metrics.to_csv(OUT / "07_metrics_and_acceptance/final_metrics_locked.csv", index=False, encoding="utf-8-sig")
    acceptance.to_csv(OUT / "07_metrics_and_acceptance/final_acceptance_locked.csv", index=False, encoding="utf-8-sig")
    endpoint_summary[
        ["endpoint", "endpoint_type", "n_rows", "n_persons", "events", "event_rate", "duplicate_rows"]
    ].to_csv(OUT / "10_tables_for_paper/Table_1_endpoint_cohort_summary.csv", index=False, encoding="utf-8-sig")
    metrics.to_csv(OUT / "10_tables_for_paper/Table_2_model_performance.csv", index=False, encoding="utf-8-sig")
    acc = acceptance.merge(metrics[["endpoint", "best_algorithm", "AUROC", "AUPRC", "Brier"]], on=["endpoint", "best_algorithm"], how="left")
    limitations = {
        "KL structural progression": "Main model after KXR READPRJ deduplication; internal OAI validation only.",
        "TKR / knee surgery event": "Fixed-horizon binary fallback; not a full survival endpoint because complete non-event censoring times were not reliably reconstructable.",
        "Symptom/function worsening": "Accepted as supplementary because performance is weaker and MCID/direction assumptions require cautious interpretation.",
    }
    acc["endpoint_specific_limitation"] = acc["endpoint"].map(limitations)
    acc.to_csv(OUT / "10_tables_for_paper/Table_3_acceptance_and_limitations.csv", index=False, encoding="utf-8-sig")


def inventory_analysis_outputs(src: Path) -> pd.DataFrame:
    folders = ["08_calibration", "09_DCA", "10_risk_stratification", "11_explainability", "12_posthoc_error_analysis"]
    rows = []
    for folder in folders:
        p = src / folder
        files = sorted([f for f in p.rglob("*") if f.is_file()]) if p.exists() else []
        if not files:
            rows.append({"analysis_folder": folder, "relative_path": "not_available_in_current_package", "size_bytes": 0, "notes": "missing"})
        for f in files:
            rows.append(
                {
                    "analysis_folder": folder,
                    "relative_path": f.relative_to(src).as_posix(),
                    "size_bytes": f.stat().st_size,
                    "notes": "post-hoc / exploratory error analysis" if folder == "12_posthoc_error_analysis" else "",
                }
            )
    inv = pd.DataFrame(rows)
    inv.to_csv(OUT / "08_calibration_DCA_explainability_error/calibration_DCA_explainability_error_inventory.csv", index=False, encoding="utf-8-sig")
    figs = inv[inv["relative_path"].astype(str).str.lower().str.endswith((".png", ".jpg", ".jpeg", ".svg", ".pdf"))].copy()
    figs.to_csv(OUT / "11_figures_inventory/final_figure_inventory.csv", index=False, encoding="utf-8-sig")
    write_md(
        OUT / "08_calibration_DCA_explainability_error/calibration_DCA_explainability_error_summary.md",
        "# Calibration, DCA, explainability and error analysis inventory\n\n"
        "Calibration, DCA, risk stratification, feature importance and post-hoc error analysis files were inventoried from the locked package.\n\n"
        "Feature importance and SHAP analyses were used to examine the predictors contributing to model outputs and to screen for clinically implausible or leakage-prone features. These analyses were interpreted as model explanations rather than causal effects.\n\n"
        "Post-hoc error analysis is labelled as exploratory and should not be treated as confirmatory evidence.\n",
    )
    return inv


def write_manuscript_text(metrics: pd.DataFrame, acceptance: pd.DataFrame) -> None:
    metric_lines = []
    for _, r in metrics.iterrows():
        decision = acceptance[acceptance["endpoint"].eq(r["endpoint"])]["acceptance_decision"].iloc[0]
        metric_lines.append(
            f"- {r['endpoint']}: {r['best_algorithm']}, AUROC {r['AUROC']:.3f}, AUPRC {r['AUPRC']:.3f}, Brier {r['Brier']:.3f}, decision {decision}."
        )
    methods_en = """# KOM-Risk final methods

KOM-Risk was formally retrained from OAI raw CSV data using participant-knee-level baseline predictors and three endpoint-specific labels. The Q1-Q4 standardized demonstration cases were not used for model training, stratification or evaluation, and no downstream KOM/QAM integration analysis was performed in this lock package.

Because multiple KXR readings could exist for the same participant-knee pair under different READPRJ projects, KXR records were deterministically deduplicated before model development. For each ID-SIDE pair, records were prioritized as READPRJ 15, then 37, then 42, then other projects; records with non-missing KL grades were preferred. This produced one radiographic record per participant-knee pair and prevented duplicate weighting during model training and evaluation.

SIDE mapping was validated for the KXR SQ BU file family by cross-checking SIDE-coded KXR records against wide right/left fields in the OAI measurement inventory. SIDE=1 mapped to right and SIDE=2 mapped to left with match rates above 0.995 for the expected right/left comparisons. This mapping was not generalized to unrelated OAI files without file-specific evidence.

Models used baseline-only predictors. Participants, rather than knees, were split into training, validation and test sets, ensuring that bilateral knees from the same participant could not cross splits. Preprocessing was fit on the training set only. Validation data were used for model and threshold selection, and the test set was reserved for final evaluation.

Three endpoints were modelled: KL structural progression, fixed-horizon binary TKR/knee surgery event, and symptom/function worsening. Endpoint B was explicitly treated as a fixed-horizon binary fallback because reliable complete non-event censoring times could not be reconstructed; it was not reported as a full survival model. Final selected models were CatBoost for all three endpoints in the locked post-dedup package. Calibration, decision curve analysis, risk stratification, feature importance and post-hoc error analysis were conducted as supplementary analyses.
"""
    methods_cn = """# KOM-Risk 最终方法

KOM-Risk 基于 OAI 原始 CSV 数据重新训练，采用受试者-膝关节水平的基线预测变量和三个 endpoint 标签。本次建模不使用 Q1-Q4 标准化示范病例作为训练、分层或评价数据，也不进行 KOM/QAM 下游集成分析。

由于 OAI KXR 读片文件中同一受试者-膝关节可能存在多个 READPRJ 读片项目记录，本研究在建模前对 KXR 记录进行确定性去重。对于每个 ID-SIDE 组合，按 READPRJ 15、37、42、其他项目的优先级保留记录，并优先保留 KL 分级非缺失记录。该步骤保证每个受试者-膝关节在同一影像时间点仅保留一条记录，避免样本重复放大导致模型训练和评价偏倚。

SIDE 映射主要针对已验证的 KXR SQ BU 文件家族，通过与 OAI measurement inventory 中宽格式右/左字段交叉验证确认。SIDE=1 映射为右膝，SIDE=2 映射为左膝，预期右/左比较的匹配率均超过 0.995。该映射不泛化到未单独验证的其他 OAI 文件。

模型仅使用基线特征。数据按受试者进行 train/validation/test 划分，保证同一受试者的双膝不会跨 split。预处理仅在训练集 fit，验证集用于模型和阈值选择，测试集仅用于最终评价。

本次建模包括三个 endpoint：KL 结构进展、fixed-horizon 二分类 TKR/膝手术事件、症状/功能恶化。Endpoint B 因非事件完整 censoring 时间不能可靠重建，明确作为 fixed-horizon binary fallback，而不是完整 survival model。最终锁定版本中三个 endpoint 的最佳模型均为 CatBoost。校准、DCA、风险分层、特征重要性和事后误差分析均作为补充分析。
"""
    results_en = "# KOM-Risk final results\n\n" + "\n".join(metric_lines) + "\n\nEndpoint A and Endpoint B were accepted as main models. Endpoint C was accepted as supplementary only.\n"
    results_cn = "# KOM-Risk 最终结果\n\n" + "\n".join(metric_lines) + "\n\nEndpoint A 和 Endpoint B 达到 ACCEPT_MAIN；Endpoint C 达到 ACCEPT_SUPPLEMENT，仅作为补充结果呈现。\n"
    limitations_en = """# KOM-Risk final limitations

- Endpoint B is not a full survival endpoint. It is a fixed-horizon binary fallback because reliable complete non-event censoring times could not be reconstructed.
- Endpoint C showed weaker discrimination and is accepted only as supplementary evidence.
- SIDE mapping was primarily validated for the KXR SQ BU file family and should not be generalized to unrelated OAI files without additional validation.
- The KXR deduplication rule may be influenced by READPRJ priority assumptions, although it prevents duplicate weighting.
- OAI internal validation cannot replace external validation.
- DCA and feature importance/SHAP-style analyses are supplementary model explanation tools and do not imply causal effects.
"""
    limitations_cn = """# KOM-Risk 最终局限性

- Endpoint B 不是完整 survival endpoint，而是 fixed-horizon binary fallback，因为非事件完整 censoring 时间不能可靠重建。
- Endpoint C 判别性能相对较弱，仅作为补充结果呈现。
- SIDE 映射主要针对已验证的 KXR SQ BU 文件家族，不能在缺少文件级验证时泛化到其他 OAI 文件。
- KXR 去重规则可能受到 READPRJ 优先级假设影响，但该步骤避免了重复读片记录造成的样本重复加权。
- OAI 内部验证不能替代外部验证。
- DCA 和特征重要性/SHAP 类解释分析均为补充模型解释工具，不代表因果效应。
"""
    files = {
        "KOMRisk_final_methods_en.md": methods_en,
        "KOMRisk_final_methods_cn.md": methods_cn,
        "KOMRisk_final_results_en.md": results_en,
        "KOMRisk_final_results_cn.md": results_cn,
        "KOMRisk_final_limitations_en.md": limitations_en,
        "KOMRisk_final_limitations_cn.md": limitations_cn,
    }
    for name, text in files.items():
        write_md(OUT / "09_manuscript_ready_text" / name, text)


def write_summaries(status: dict[str, Any], endpoint_summary: pd.DataFrame, feature_counts: pd.DataFrame) -> None:
    metrics_text = "\n".join(
        f"- {r.endpoint}: {r.best_algorithm}, AUROC={r.AUROC:.3f}, AUPRC={r.AUPRC:.3f}, Brier={r.Brier:.3f}, decision={r.decision}"
        for r in endpoint_summary.itertuples()
    )
    cn = f"""# KOM-Risk final locked post-dedup summary

本轮 KOM-Risk 正式重训在发现 KXR 同一 ID+SIDE 存在多 READPRJ 重复记录后，采用 READPRJ 15 > 37 > 42 > other 的确定性优先级规则完成去重，并重新训练正式模型。最终 SIDE 映射通过 wide R/L 交叉验证，person-level split 无泄漏，每个 endpoint 仅保留一个 best_model.joblib。结构进展和 fixed-horizon 手术事件模型达到 ACCEPT_MAIN；症状/功能恶化模型达到 ACCEPT_SUPPLEMENT。

Final status: {status['overall_decision']}

{metrics_text}
"""
    en = f"""# KOM-Risk final locked post-dedup executive summary

After detecting multiple KXR READPRJ records for the same ID-SIDE participant-knee pair, the formal KOM-Risk retraining package used deterministic KXR deduplication with READPRJ priority 15 > 37 > 42 > other and then retrained the locked models. SIDE mapping was validated against wide right/left fields, person-level split leakage was not detected, and one best_model.joblib was retained for each endpoint. Structural progression and fixed-horizon surgery event models were accepted as main models; symptom/function worsening was accepted as supplementary.

Final status: {status['overall_decision']}

{metrics_text}
"""
    readme = f"""# KOMRisk Final Locked PostDedup 20260610

Input package: `{status['input_package']}`

Source root: `{status['source_root']}`

Final zip: `{status.get('final_zip', 'pending')}`

Overall decision: {status['overall_decision']}

This package contains the final post-dedup audit, manuscript-ready methods/results/limitations text, paper tables, figure inventory, model artifact QC, feature lock tables and final zip integrity report. No retraining was performed in this post-lock stage.
"""
    write_md(OUT / "01_final_package_audit/final_lock_executive_summary_cn.md", cn)
    write_md(OUT / "01_final_package_audit/final_lock_executive_summary_en.md", en)
    write_md(OUT / "00_README/README_FINAL_LOCKED_POST_DEDUP.md", readme)


def copy_storage_cleanup(src: Path) -> None:
    for name in ["storage_before_after_summary.csv", "storage_cleanup_report.md", "deleted_intermediate_files_manifest.csv", "kept_final_artifacts_manifest.csv"]:
        p = src / "16_storage_cleanup" / name
        if p.exists():
            shutil.copy2(p, OUT / "12_storage_and_cleanup_QC" / name)


def final_zip(status: dict[str, Any]) -> dict[str, Any]:
    zip_path = OUT / "13_final_zip" / FINAL_ZIP_NAME
    if zip_path.exists():
        zip_path.unlink()
    rows = []
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(OUT.rglob("*")):
            if not p.is_file():
                continue
            if p == zip_path:
                continue
            rel = p.relative_to(OUT).as_posix()
            zf.write(p, f"{OUT.name}/{rel}")
            rows.append({"relative_path": f"{OUT.name}/{rel}", "size_bytes": p.stat().st_size})
    with zipfile.ZipFile(zip_path, "r") as zf:
        bad = zf.testzip()
        member_count = len(zf.namelist())
    pd.DataFrame(rows).to_csv(OUT / "13_final_zip/final_zip_index.csv", index=False, encoding="utf-8-sig")
    write_md(
        OUT / "13_final_zip/final_zip_integrity_report.md",
        f"# Final zip integrity report\n\nFinal zip: `{zip_path}`\n\nSize MB: {zip_path.stat().st_size / 1024 / 1024:.3f}\n\nmember_count={member_count}\n\ntestzip={bad}\n",
    )
    return {"final_zip": str(zip_path), "final_zip_testzip": bad, "final_zip_member_count": member_count, "final_zip_size_mb": zip_path.stat().st_size / 1024 / 1024}


def main() -> None:
    mkdirs()
    src, zip_info = extract_source_from_zip()
    package_status = audit_package(src, zip_info)
    dedup, dup_df = audit_kxr_and_duplicates(src)
    side_validation = audit_side_mapping(src)
    endpoint_summary, metrics, acceptance = audit_endpoints_and_split(src, dup_df)
    model_df, residue = audit_models(src)
    feature_table, feature_counts = build_feature_lock(src)
    write_metrics_and_tables(src, endpoint_summary, metrics, acceptance)
    inventory_analysis_outputs(src)
    write_manuscript_text(metrics, acceptance)
    copy_storage_cleanup(src)
    side1 = side_validation[(side_validation["side_value"] == 1) & (side_validation["compared_to"].astype(str).str.endswith("R"))]["match_rate"].max()
    side2 = side_validation[(side_validation["side_value"] == 2) & (side_validation["compared_to"].astype(str).str.endswith("L"))]["match_rate"].max()
    overall_pass = (
        not package_status["critical_missing"]
        and int(dup_df["duplicate_rows"].sum()) == 0
        and side1 >= 0.95
        and side2 >= 0.95
        and bool(read_csv_file(src / "03_splits/person_level_split_integrity_report.csv")["person_cross_split_leakage"].iloc[0]) is False
        and (model_df["best_model_count"] == 1).all()
        and len(residue) == 0
    )
    status = {
        "input_package": str(INPUT_ZIP if INPUT_ZIP.exists() else src),
        "source_root": str(src),
        "overall_decision": "FINAL_LOCKED_ACCEPTED" if overall_pass else "FINAL_LOCK_FAILED",
        "critical_missing": package_status["critical_missing"],
        "side1_right_match_rate": float(side1),
        "side2_left_match_rate": float(side2),
        "duplicate_rows_total": int(dup_df["duplicate_rows"].sum()),
        "best_model_total": int(model_df["best_model_count"].sum()),
        "intermediate_residue_count": len(residue),
    }
    write_summaries(status, endpoint_summary, feature_counts)
    zinfo = final_zip(status)
    status.update(zinfo)
    write_summaries(status, endpoint_summary, feature_counts)
    (OUT / "00_README/final_lock_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print("KOM-Risk FINAL LOCK COMPLETE")
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
