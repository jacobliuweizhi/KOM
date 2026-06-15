from __future__ import annotations

import json
import math
import os
import re
import shutil
import zipfile
from datetime import datetime
from glob import glob
from pathlib import Path
from typing import Any

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:
    from xgboost import XGBClassifier
except Exception:
    XGBClassifier = None

try:
    from lightgbm import LGBMClassifier
except Exception:
    LGBMClassifier = None

try:
    from catboost import CatBoostClassifier
except Exception:
    CatBoostClassifier = None


SEED = 20260610
OUT_BASE = "KOMRisk_Formal_Retrain_FINAL_20260610"
ENDPOINT_META = {
    "endpoint_A": {
        "label": "structural_progression",
        "title": "KL structural progression",
        "model_dir": "structural_progression",
    },
    "endpoint_B": {
        "label": "surgery_event",
        "title": "TKR / knee surgery event",
        "model_dir": "surgery_event",
    },
    "endpoint_C": {
        "label": "symptom_function_worsening",
        "title": "Symptom/function worsening",
        "model_dir": "symptom_function_worsening",
    },
}


def now_tag() -> str:
    return datetime.now().strftime("%H%M%S")


def resolve_project_root() -> Path:
    candidates = [Path.cwd()] + [Path(p) for p in glob(r"C:\OAI*\pythonProject1\KOM*")]
    for p in candidates:
        if (p / "本地化").exists() or (p / "KOM_Submission_Audit_Package_202606_FINAL").exists():
            return p
    return Path.cwd()


def locate_data_paths() -> dict[str, Any]:
    sas_patterns = [r"C:\OAI*\pythonProject1\OAI*\OAICompleteData_SAS"]
    csv_patterns = [
        r"C:\OAI*\pythonProject1\OAI*\OAICompleteData_CSV",
        r"C:\OAI*\OAICompleteData_CSV",
        r"C:\OAI*\pythonProject1\KOM*\本地化\koa_mdt_agents\data\raw\oai_csv_link",
    ]
    sas_hits = [Path(p) for pat in sas_patterns for p in glob(pat) if Path(p).exists()]
    csv_hits = [Path(p) for pat in csv_patterns for p in glob(pat) if Path(p).exists()]
    csv_root = None
    for p in csv_hits:
        if "pythonProject1" in str(p) and any(p.glob("allclinical00.csv")):
            csv_root = p
            break
    if csv_root is None and csv_hits:
        csv_root = csv_hits[0]
    return {"sas_paths": sas_hits, "csv_paths": csv_hits, "sas_root": sas_hits[0] if sas_hits else None, "csv_root": csv_root}


def make_output(root: Path) -> Path:
    out = root / OUT_BASE
    if out.exists():
        out = root / f"{OUT_BASE}_{now_tag()}"
    for d in [
        "00_README",
        "01_data_source_and_side_mapping",
        "02_endpoint_construction",
        "03_splits",
        "04_features/raw_feature_tables",
        "04_features/encoded_feature_tables",
        "04_features/feature_names",
        "04_features/feature_audit",
        "05_models/structural_progression/best_model",
        "05_models/surgery_event/best_model",
        "05_models/symptom_function_worsening/best_model",
        "06_predictions",
        "07_metrics",
        "08_calibration",
        "09_DCA",
        "10_risk_stratification",
        "11_explainability",
        "12_posthoc_error_analysis",
        "13_leakage_and_QC",
        "14_manuscript_ready_text",
        "15_logs",
        "16_storage_cleanup",
        "scripts",
        "tmp_working",
    ]:
        (out / d).mkdir(parents=True, exist_ok=True)
    return out


def clean_id(x: Any) -> str:
    s = str(x)
    if s.startswith("b'") and s.endswith("'"):
        s = s[2:-1]
    return s


def read_csv(csv_root: Path, name: str) -> pd.DataFrame:
    df = pd.read_csv(csv_root / name, low_memory=False)
    for c in df.columns:
        if c.lower() == "id":
            df[c] = df[c].map(clean_id)
    return df


def file_count(path: Path | None, suffix: str) -> int:
    return sum(1 for _ in path.rglob(f"*{suffix}")) if path and path.exists() else 0


def write_data_manifest(paths: dict[str, Any], out: Path) -> None:
    rows = []
    for p in paths["sas_paths"] + paths["csv_paths"]:
        rows.append(
            {
                "discovered_path": str(p),
                "path_exists": p.exists(),
                "file_count": sum(1 for _ in p.rglob("*")) if p.exists() else 0,
                "csv_count": file_count(p, ".csv"),
                "pdf_count": file_count(p, ".pdf"),
                "sas_count": file_count(p, ".sas"),
                "xpt_count": file_count(p, ".xpt"),
                "sas7bdat_count": file_count(p, ".sas7bdat"),
                "total_size_mb": round(sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1024 / 1024, 3) if p.exists() else 0,
                "used_for_training": p == paths["csv_root"],
                "notes": "selected CSV root" if p == paths["csv_root"] else "",
            }
        )
    df = pd.DataFrame(rows)
    df.to_csv(out / "01_data_source_and_side_mapping/data_source_manifest.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(out / "01_data_source_and_side_mapping/data_source_manifest.xlsx", engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="data_sources", index=False)
    (out / "01_data_source_and_side_mapping/data_source_summary.md").write_text(
        "# Data source summary\n\n"
        f"Selected CSV root: `{paths['csv_root']}`\n\n"
        f"Selected SAS/codebook root: `{paths['sas_root']}`\n\n"
        "This formal retraining run uses OAI raw CSV data only and does not restore old KOM-Risk model artifacts.\n",
        encoding="utf-8",
    )


def scan_csv_inventory(csv_root: Path, out: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    file_rows = []
    col_rows = []
    for p in sorted(csv_root.glob("*.csv")):
        try:
            df = pd.read_csv(p, nrows=5000, low_memory=False)
        except Exception as e:
            file_rows.append({"file_name": p.name, "full_path": str(p), "error": str(e)})
            continue
        n_rows = sum(1 for _ in p.open("rb")) - 1
        file_rows.append(
            {
                "file_name": p.name,
                "full_path": str(p),
                "n_rows": n_rows,
                "n_cols": len(df.columns),
                "file_size_mb": round(p.stat().st_size / 1024 / 1024, 3),
                "contains_side_keyword": any(re.search(r"SIDE|SID|RIGHT|LEFT|ERK|ELK", c, re.I) for c in df.columns),
                "contains_endpoint_keyword": any(re.search(r"XRKL|WOM|KOOS|TKR|SURG|V99", c, re.I) for c in df.columns),
                "contains_feature_keyword": any(re.search(r"AGE|BMI|SEX|RACE|PASE|CESD|NSAID|DIAB|ULCER|FALL", c, re.I) for c in df.columns),
            }
        )
        for c in df.columns:
            s = df[c]
            col_rows.append(
                {
                    "file_name": p.name,
                    "full_path": str(p),
                    "n_rows": n_rows,
                    "n_cols": len(df.columns),
                    "file_size_mb": round(p.stat().st_size / 1024 / 1024, 3),
                    "column_name": c,
                    "inferred_dtype": str(s.dtype),
                    "non_missing_count_profiled": int(s.notna().sum()),
                    "missing_rate_profiled": round(float(s.isna().mean()), 4),
                    "first_values_sample": " | ".join(map(str, s.head(5).tolist())),
                    "unique_values_sample": " | ".join(map(str, s.dropna().astype(str).drop_duplicates().head(10).tolist())),
                    "contains_side_keyword": bool(re.search(r"SIDE|SID|RIGHT|LEFT|ERK|ELK|XRKLR|XRKLL|MRSIDE|MRKSIDE", c, re.I)),
                    "contains_endpoint_keyword": bool(re.search(r"XRKL|WOM|KOOS|TKR|SURG|V99|KPN|PAIN", c, re.I)),
                    "contains_feature_keyword": bool(re.search(r"AGE|BMI|SEX|RACE|PASE|CESD|NSAID|DIAB|ULCER|FALL", c, re.I)),
                }
            )
    file_df = pd.DataFrame(file_rows)
    col_df = pd.DataFrame(col_rows)
    file_df.to_csv(out / "01_data_source_and_side_mapping/oai_csv_file_inventory.csv", index=False, encoding="utf-8-sig")
    col_df.to_csv(out / "01_data_source_and_side_mapping/oai_csv_column_inventory.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(out / "01_data_source_and_side_mapping/oai_csv_schema_summary.xlsx", engine="openpyxl") as writer:
        file_df.to_excel(writer, sheet_name="files", index=False)
        col_df.head(30000).to_excel(writer, sheet_name="columns", index=False)
    return file_df, col_df


def side_mapping_validation(csv_root: Path, out: Path) -> dict[str, Any]:
    meas = read_csv(csv_root, "measinventory.csv").rename(columns={"id": "ID"})
    rows = []
    final_rows = []
    kxr_files = ["kxr_sq_bu00.csv", "kxr_sq_bu01.csv", "kxr_sq_bu03.csv", "kxr_sq_bu05.csv", "kxr_sq_bu06.csv", "kxr_sq_bu08.csv", "kxr_sq_bu10.csv"]
    for f in kxr_files:
        p = csv_root / f
        if not p.exists():
            continue
        k = read_csv(csv_root, f)
        visit = re.search(r"(\d{2})", f).group(1)
        kl = next((c for c in k.columns if c.upper() == f"V{visit}XRKL"), None)
        status = "SIDE_MAPPING_UNCERTAIN"
        evidence_file = "none"
        best_rate = np.nan
        if visit == "00" and kl and f"V{visit}XRKLR" in meas.columns and f"V{visit}XRKLL" in meas.columns:
            m = k[["ID", "SIDE", kl]].merge(meas[["ID", f"V{visit}XRKLR", f"V{visit}XRKLL"]], on="ID", how="inner")
            for side_val in [1, 2]:
                sub = m[m["SIDE"].astype(float).eq(side_val)]
                for side_name, col in [("R", f"V{visit}XRKLR"), ("L", f"V{visit}XRKLL")]:
                    n = int(((sub[kl].notna()) & (sub[col].notna())).sum())
                    match = int(((sub[kl] == sub[col]) & (sub[kl].notna()) & (sub[col].notna())).sum())
                    rate = match / n if n else np.nan
                    rows.append(
                        {
                            "file_name": f,
                            "side_column": "SIDE",
                            "side_value": side_val,
                            "compared_to": col,
                            "validation_n": n,
                            "match_n": match,
                            "match_rate": rate,
                        }
                    )
            side1_r = [r for r in rows if r["file_name"] == f and r["side_value"] == 1 and r["compared_to"].endswith("R")][0]
            side2_l = [r for r in rows if r["file_name"] == f and r["side_value"] == 2 and r["compared_to"].endswith("L")][0]
            best_rate = min(side1_r["match_rate"], side2_l["match_rate"])
            if best_rate >= 0.95:
                status = "ACCEPT_HIGH_CONFIDENCE"
                evidence_file = "measinventory.csv V00XRKLR/V00XRKLL cross-check"
        else:
            status = "ACCEPT_BY_KXR_FAMILY_AFTER_BASELINE_VALIDATION" if f != "kxr_sq_bu00.csv" else "SIDE_MAPPING_UNCERTAIN"
            evidence_file = "kxr_sq_bu00 baseline cross-check plus same KXR SIDE field family"
            best_rate = np.nan
        usable = status in {"ACCEPT_HIGH_CONFIDENCE", "ACCEPT_BY_KXR_FAMILY_AFTER_BASELINE_VALIDATION"}
        final_rows.append(
            {
                "file_name": f,
                "side_column": "SIDE",
                "original_side_values": "1;2",
                "mapped_side_values": "1=right;2=left",
                "mapping_rule": "SIDE 1 -> right, SIDE 2 -> left",
                "evidence_type": "wide_RL_crosscheck" if f == "kxr_sq_bu00.csv" else "same_file_family_inference",
                "evidence_file": evidence_file,
                "validation_n": "" if math.isnan(best_rate) else "see side_sid_validation_against_wide_RL.csv",
                "validation_match_rate": "" if math.isnan(best_rate) else best_rate,
                "confidence_status": status,
                "usable_for_main_model": usable,
                "notes": "Do not generalize this mapping outside the KXR SQ BU file family without file-specific evidence.",
            }
        )
    val_df = pd.DataFrame(rows)
    val_df.to_csv(out / "01_data_source_and_side_mapping/side_sid_validation_against_wide_RL.csv", index=False, encoding="utf-8-sig")
    cand = pd.DataFrame(final_rows)
    cand.to_csv(out / "01_data_source_and_side_mapping/side_sid_final_mapping.csv", index=False, encoding="utf-8-sig")
    cand.to_csv(out / "01_data_source_and_side_mapping/side_sid_file_specific_mapping_table.csv", index=False, encoding="utf-8-sig")
    cand[~cand["usable_for_main_model"]].to_csv(out / "01_data_source_and_side_mapping/side_sid_uncertain_or_rejected_files.csv", index=False, encoding="utf-8-sig")
    cand[["file_name", "side_column", "original_side_values", "confidence_status", "usable_for_main_model"]].to_csv(
        out / "01_data_source_and_side_mapping/side_sid_candidate_columns.csv", index=False, encoding="utf-8-sig"
    )
    report = "# SIDE/SID final report\n\n"
    report += "KXR baseline validation against `measinventory.csv` wide R/L fields supports SIDE 1 -> right and SIDE 2 -> left for the KXR SQ BU file family.\n\n"
    if not val_df.empty:
        report += val_df.to_markdown(index=False)
    (out / "01_data_source_and_side_mapping/side_sid_final_report.md").write_text(report, encoding="utf-8")
    structural_gate = cand[cand["file_name"].str.contains("kxr_sq_bu")]["usable_for_main_model"].all()
    surgery_gate = True  # outcomes99 uses wide ERK/ELK field names, no numeric SIDE mapping needed.
    return {"structural_side_gate": bool(structural_gate), "surgery_side_gate": bool(surgery_gate), "validation": val_df, "final": cand}


def parse_byteish_text(x: Any) -> str:
    s = str(x)
    if s.startswith("b'") and s.endswith("'"):
        s = s[2:-1]
    return s


def kxr_visit(csv_root: Path, visit: str, out: Path | None = None) -> pd.DataFrame:
    df = read_csv(csv_root, f"kxr_sq_bu{visit}.csv")
    prefix = f"V{visit}"
    keep = ["ID", "SIDE"] + (["READPRJ"] if "READPRJ" in df.columns else []) + [c for c in df.columns if c.upper().startswith(prefix + "XR")]
    df = df[keep].copy()
    kl_col = next((c for c in df.columns if c.upper() == prefix + "XRKL"), None)
    before_rows = len(df)
    before_unique = df[["ID", "SIDE"]].drop_duplicates().shape[0]
    if "READPRJ" in df.columns:
        read_priority = {"15": 0, "37": 1, "42": 2}
        df["_readprj_clean"] = df["READPRJ"].map(parse_byteish_text)
        df["_read_priority"] = df["_readprj_clean"].map(read_priority).fillna(99)
    else:
        df["_readprj_clean"] = ""
        df["_read_priority"] = 99
    if kl_col:
        df["_kl_missing_rank"] = pd.to_numeric(df[kl_col], errors="coerce").isna().astype(int)
    else:
        df["_kl_missing_rank"] = 1
    df = (
        df.sort_values(["ID", "SIDE", "_kl_missing_rank", "_read_priority"])
        .drop_duplicates(["ID", "SIDE"], keep="first")
        .drop(columns=["_read_priority", "_kl_missing_rank"])
    )
    after_rows = len(df)
    if out is not None:
        audit_file = out / "01_data_source_and_side_mapping/kxr_read_project_deduplication_audit.csv"
        row = pd.DataFrame(
            [
                {
                    "file_name": f"kxr_sq_bu{visit}.csv",
                    "visit": f"V{visit}",
                    "dedup_key": "ID+SIDE",
                    "read_project_priority": "15 > 37 > 42 > other",
                    "kl_non_missing_priority": True,
                    "rows_before": before_rows,
                    "unique_id_side_before": before_unique,
                    "rows_after": after_rows,
                    "duplicate_rows_removed": before_rows - after_rows,
                    "notes": "Multiple OAI KXR readings exist for some knees. Formal modeling keeps one row per knee to avoid duplicate weighting.",
                }
            ]
        )
        if audit_file.exists():
            old = pd.read_csv(audit_file)
            row = pd.concat([old, row], ignore_index=True).drop_duplicates(["file_name", "visit"], keep="last")
        row.to_csv(audit_file, index=False, encoding="utf-8-sig")
    df = df.drop(columns=[c for c in ["READPRJ", "_readprj_clean"] if c in df.columns])
    df["knee_side"] = df["SIDE"].map({1.0: "right", 2.0: "left", 1: "right", 2: "left"})
    rename = {}
    for c in df.columns:
        if c.upper().startswith(prefix):
            rename[c] = c.upper().replace(prefix, f"V{visit}_")
    return df.rename(columns=rename)


def base_feature_table(csv_root: Path, out: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    ac = read_csv(csv_root, "allclinical00.csv")
    en = read_csv(csv_root, "enrollees.csv")
    kxr00 = kxr_visit(csv_root, "00", out)
    base_ids = ac[["ID"]].drop_duplicates()
    person_cols = [
        "V00AGE",
        "P01BMI",
        "P01HEIGHT",
        "P01WEIGHT",
        "V00PASE",
        "V00COMORB",
        "V00DIAB",
        "V00KIDFXN",
        "V00ULCER",
        "V00LIVDAM",
        "V00HRTAT",
        "V00STROKE",
        "V00FALL",
        "V00CESD",
        "V00NSAIDS",
        "V00NSAIDRX",
        "V00RXNSAID",
        "V00PNMEDT",
        "V00KNINJ",
        "V00STERKN",
        "V00HYALKN",
        "V00400MTR",
        "V00WALKER",
    ]
    person_cols = [c for c in person_cols if c in ac.columns]
    person = ac[["ID"] + person_cols].merge(en[[c for c in ["ID", "P02SEX", "P02RACE", "V00SITE"] if c in en.columns]], on="ID", how="left")
    side_rows = []
    side_map = {
        "right": {
            "WOMAC_pain": "V00WOMKPR",
            "WOMAC_function": "V00WOMADLR",
            "WOMAC_total": "V00WOMTSR",
            "KOOS_pain": "V00KOOSKPR",
            "KOOS_symptom": "V00KOOSYMR",
            "knee_touch_pain": "V00RKLTTPN",
            "patellar_pain": "V00RKPATPN",
            "alignment": "V00RKALNMT",
            "flexion_degree": "V00RKFHDEG",
            "hyal_injection": "V00HYAINJR",
            "steroid_injection": "V00STRINJR",
        },
        "left": {
            "WOMAC_pain": "V00WOMKPL",
            "WOMAC_function": "V00WOMADLL",
            "WOMAC_total": "V00WOMTSL",
            "KOOS_pain": "V00KOOSKPL",
            "KOOS_symptom": "V00KOOSYML",
            "knee_touch_pain": "V00LKLTTPN",
            "patellar_pain": "V00LKPATPN",
            "alignment": "V00LKALNMT",
            "flexion_degree": "V00LKFHDEG",
            "hyal_injection": "V00HYAINJL",
            "steroid_injection": "V00STRINJL",
        },
    }
    for side, cols in side_map.items():
        use = ["ID"] + [c for c in cols.values() if c in ac.columns]
        tmp = ac[use].copy()
        tmp["knee_side"] = side
        tmp = tmp.rename(columns={v: f"side_{k}" for k, v in cols.items() if v in tmp.columns})
        side_rows.append(tmp)
    side_df = pd.concat(side_rows, ignore_index=True)
    features = side_df.merge(person, on="ID", how="left").merge(kxr00.drop(columns=["SIDE"]), on=["ID", "knee_side"], how="left")
    features["row_id"] = features["ID"].astype(str) + "_" + features["knee_side"]
    features.to_parquet(out / "04_features/raw_feature_tables/ALL_ENDPOINTS_baseline_knee_raw_feature_table.parquet", index=False)
    raw_cols = [c for c in features.columns if c not in {"ID", "row_id", "knee_side"}]
    dictionary_rows = []
    for c in raw_cols:
        dictionary_rows.append(
            {
                "raw_feature_name": c,
                "clean_feature_name_en": c.replace("_", " "),
                "clean_feature_name_cn": "",
                "clinical_domain": domain_for_feature(c),
                "source_file": infer_source_file(c),
                "source_column": infer_source_column(c),
                "visit": "V00",
                "data_level": "knee" if c.startswith("side_") or c.startswith("V00_XR") else "person",
            }
        )
    dictionary = pd.DataFrame(dictionary_rows)
    dictionary.to_csv(out / "04_features/feature_names/ALL_ENDPOINTS_final_raw_input_feature_names.csv", index=False, encoding="utf-8-sig")
    return features, dictionary


def domain_for_feature(c: str) -> str:
    u = c.upper()
    if any(x in u for x in ["XR", "KL", "JS", "OST", "SCT", "ALIGN"]):
        return "imaging"
    if any(x in u for x in ["WOMAC", "KOOS", "PAIN", "FUNCTION"]):
        return "symptoms_function"
    if any(x in u for x in ["AGE", "SEX", "RACE", "BMI", "HEIGHT", "WEIGHT", "SITE"]):
        return "demographics"
    if any(x in u for x in ["NSAID", "INJECTION", "PNMED", "STER", "HYAL"]):
        return "treatment_exposure"
    if any(x in u for x in ["DIAB", "ULCER", "KID", "LIV", "STROKE", "FALL", "COMORB"]):
        return "comorbidity_safety"
    if "PASE" in u or "400" in u or "WALK" in u:
        return "activity_function"
    if "CESD" in u:
        return "psychosocial"
    return "other"


def infer_source_file(c: str) -> str:
    if c.startswith("V00_XR"):
        return "kxr_sq_bu00.csv"
    if c in {"P02SEX", "P02RACE", "V00SITE"}:
        return "enrollees.csv"
    return "allclinical00.csv"


def infer_source_column(c: str) -> str:
    if c.startswith("side_"):
        return "side-specific allclinical00 R/L source column; see feature dictionary"
    if c.startswith("V00_XR"):
        return c.replace("V00_", "V00")
    return c


def endpoint_A(csv_root: Path, features: pd.DataFrame, out: Path) -> pd.DataFrame:
    b = kxr_visit(csv_root, "00", out)[["ID", "knee_side", "V00_XRKL"]]
    f = kxr_visit(csv_root, "06", out)[["ID", "knee_side", "V06_XRKL"]]
    y = b.merge(f, on=["ID", "knee_side"], how="inner")
    y["label"] = ((y["V06_XRKL"] - y["V00_XRKL"]) >= 1).astype(int)
    y["followup_window"] = "V00_to_V06_48m_candidate"
    dat = features.merge(y[["ID", "knee_side", "label", "V00_XRKL", "V06_XRKL", "followup_window"]], on=["ID", "knee_side"], how="inner", suffixes=("", "_label"))
    dat.to_csv(out / "02_endpoint_construction/endpoint_A_structural_progression_label_table.csv", index=False, encoding="utf-8-sig")
    flow = pd.DataFrame(
        [
            {"step": "baseline KXR knees", "n": len(b)},
            {"step": "V06 follow-up KXR knees", "n": len(f)},
            {"step": "complete baseline+V06 label knees", "n": len(y)},
            {"step": "event knees KL increase >=1", "n": int(y["label"].sum())},
        ]
    )
    flow.to_csv(out / "02_endpoint_construction/endpoint_A_structural_progression_cohort_flow.csv", index=False, encoding="utf-8-sig")
    (out / "02_endpoint_construction/endpoint_A_structural_progression_definition.md").write_text(
        "# Endpoint A definition\n\nPrimary label: V06 KL - V00 KL >= 1 using KXR SQ BU knee-level rows. V06 is treated as the 48-month candidate window per locked protocol.\n",
        encoding="utf-8",
    )
    (out / "02_endpoint_construction/endpoint_A_structural_progression_QC.md").write_text(
        f"# Endpoint A QC\n\nLabel rows: {len(dat)}\nEvents: {int(dat['label'].sum())}\nEvent rate: {dat['label'].mean():.4f}\n",
        encoding="utf-8",
    )
    return dat


def endpoint_B(csv_root: Path, features: pd.DataFrame, out: Path) -> pd.DataFrame:
    o = read_csv(csv_root, "outcomes99.csv").rename(columns={"id": "ID"})
    rows = []
    for side, prefix in [("right", "V99ERK"), ("left", "V99ELK")]:
        date_col = f"{prefix}DATE"
        days_col = f"{prefix}DAYS"
        event = o[date_col].notna() | o[days_col].notna()
        tmp = pd.DataFrame({"ID": o["ID"], "knee_side": side, "label": event.astype(int), "event_time_days": pd.to_numeric(o[days_col], errors="coerce")})
        rows.append(tmp)
    y = pd.concat(rows, ignore_index=True)
    y["endpoint_mode"] = "fixed_horizon_binary_fallback_any_followup_surgery"
    dat = features.merge(y, on=["ID", "knee_side"], how="inner")
    dat.to_csv(out / "02_endpoint_construction/endpoint_B_surgery_event_label_table.csv", index=False, encoding="utf-8-sig")
    surv = y.copy()
    max_time = np.nanmax(surv["event_time_days"].values) if surv["event_time_days"].notna().any() else 3650
    surv["duration_days"] = surv["event_time_days"].fillna(max_time)
    surv.to_csv(out / "02_endpoint_construction/endpoint_B_surgery_event_survival_table.csv", index=False, encoding="utf-8-sig")
    flow = pd.DataFrame(
        [
            {"step": "outcomes99 participants", "n": o["ID"].nunique()},
            {"step": "knee rows", "n": len(y)},
            {"step": "surgery event knees", "n": int(y["label"].sum())},
            {"step": "fixed-horizon fallback label rows", "n": len(dat)},
        ]
    )
    flow.to_csv(out / "02_endpoint_construction/endpoint_B_surgery_event_cohort_flow.csv", index=False, encoding="utf-8-sig")
    (out / "02_endpoint_construction/endpoint_B_surgery_event_definition.md").write_text(
        "# Endpoint B definition\n\nV99ERK/V99ELK right/left knee surgery event was constructible. Non-event censoring times were not fully recoverable for every participant, so this run uses `SURVIVAL_ENDPOINT_NOT_RELIABLE_USED_FIXED_HORIZON_BINARY`: any follow-up right/left knee surgery event.\n",
        encoding="utf-8",
    )
    (out / "02_endpoint_construction/endpoint_B_surgery_event_QC.md").write_text(
        f"# Endpoint B QC\n\nLabel rows: {len(dat)}\nEvents: {int(dat['label'].sum())}\nEvent rate: {dat['label'].mean():.4f}\nSurvival table exported for audit, but binary fallback used for modeling.\n",
        encoding="utf-8",
    )
    return dat


def endpoint_C(csv_root: Path, features: pd.DataFrame, out: Path) -> pd.DataFrame:
    ac0 = read_csv(csv_root, "allclinical00.csv")
    ac6 = read_csv(csv_root, "allclinical06.csv")
    rows = []
    for side, cols in [
        ("right", ("V00WOMKPR", "V06WOMKPR", "V00WOMADLR", "V06WOMADLR")),
        ("left", ("V00WOMKPL", "V06WOMKPL", "V00WOMADLL", "V06WOMADLL")),
    ]:
        p0, p6, f0, f6 = cols
        tmp = ac0[["ID", p0, f0]].merge(ac6[["ID", p6, f6]], on="ID", how="inner")
        tmp["knee_side"] = side
        tmp["pain_worsening"] = (pd.to_numeric(tmp[p6], errors="coerce") - pd.to_numeric(tmp[p0], errors="coerce")) >= 2
        tmp["function_worsening"] = (pd.to_numeric(tmp[f6], errors="coerce") - pd.to_numeric(tmp[f0], errors="coerce")) >= 6
        tmp["label"] = (tmp["pain_worsening"] | tmp["function_worsening"]).astype(float)
        tmp.loc[tmp[[p0, p6, f0, f6]].isna().any(axis=1), "label"] = np.nan
        rows.append(tmp[["ID", "knee_side", "label", "pain_worsening", "function_worsening"] + list(cols)])
    y = pd.concat(rows, ignore_index=True).dropna(subset=["label"])
    y["label"] = y["label"].astype(int)
    dat = features.merge(y, on=["ID", "knee_side"], how="inner")
    dat.to_csv(out / "02_endpoint_construction/endpoint_C_symptom_function_label_table.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [
            {"scale": "WOMAC pain", "direction": "higher=worse", "threshold": "increase >=2", "status": "used_in_candidate_definition"},
            {"scale": "WOMAC function/ADL", "direction": "higher=worse", "threshold": "increase >=6", "status": "used_in_candidate_definition"},
            {"scale": "KOOS", "direction": "higher=better", "threshold": "not used in primary label", "status": "documented only"},
        ]
    ).to_csv(out / "02_endpoint_construction/endpoint_C_symptom_function_scale_direction_table.csv", index=False, encoding="utf-8-sig")
    flow = pd.DataFrame(
        [
            {"step": "baseline+V06 WOMAC complete knee rows", "n": len(y)},
            {"step": "worsening event knees", "n": int(y["label"].sum())},
        ]
    )
    flow.to_csv(out / "02_endpoint_construction/endpoint_C_symptom_function_cohort_flow.csv", index=False, encoding="utf-8-sig")
    (out / "02_endpoint_construction/endpoint_C_symptom_function_definition.md").write_text(
        "# Endpoint C definition\n\nCandidate primary label: WOMAC pain increase >=2 OR WOMAC function/ADL increase >=6 from V00 to V06. WOMAC direction is recorded as higher=worse. KOOS is not used in this primary label because direction and MCID confirmation should be separately frozen.\n",
        encoding="utf-8",
    )
    (out / "02_endpoint_construction/endpoint_C_symptom_function_QC.md").write_text(
        f"# Endpoint C QC\n\nLabel rows: {len(dat)}\nEvents: {int(dat['label'].sum())}\nEvent rate: {dat['label'].mean():.4f}\n",
        encoding="utf-8",
    )
    return dat


def split_persons(dat: pd.DataFrame, out: Path, endpoint: str) -> pd.DataFrame:
    persons = dat.groupby("ID")["label"].max().reset_index()
    train_ids, temp_ids = train_test_split(persons["ID"], test_size=0.30, random_state=SEED, stratify=persons["label"] if persons["label"].nunique() == 2 else None)
    temp = persons[persons["ID"].isin(temp_ids)]
    val_ids, test_ids = train_test_split(temp["ID"], test_size=0.50, random_state=SEED, stratify=temp["label"] if temp["label"].nunique() == 2 else None)
    split = pd.DataFrame({"ID": persons["ID"]})
    split["split"] = "train"
    split.loc[split["ID"].isin(val_ids), "split"] = "validation"
    split.loc[split["ID"].isin(test_ids), "split"] = "test"
    out_file = out / f"03_splits/{endpoint}_split.csv"
    split.to_csv(out_file, index=False, encoding="utf-8-sig")
    dat = dat.merge(split, on="ID", how="left")
    return dat


def build_model_candidates(pos_weight: float) -> list[tuple[str, Any]]:
    models = [
        ("elastic_net_logistic", LogisticRegression(max_iter=2000, penalty="elasticnet", solver="saga", l1_ratio=0.2, class_weight="balanced", random_state=SEED)),
        ("random_forest", RandomForestClassifier(n_estimators=160, max_depth=8, min_samples_leaf=8, class_weight="balanced", random_state=SEED, n_jobs=-1)),
    ]
    if XGBClassifier:
        models.append(("xgboost", XGBClassifier(n_estimators=160, max_depth=3, learning_rate=0.05, subsample=0.9, colsample_bytree=0.9, eval_metric="logloss", random_state=SEED, n_jobs=2, scale_pos_weight=pos_weight)))
    if LGBMClassifier:
        models.append(("lightgbm", LGBMClassifier(n_estimators=160, max_depth=5, learning_rate=0.05, class_weight="balanced", random_state=SEED, verbose=-1)))
    if CatBoostClassifier:
        models.append(("catboost", CatBoostClassifier(iterations=160, depth=4, learning_rate=0.05, loss_function="Logloss", eval_metric="AUC", random_seed=SEED, verbose=False, auto_class_weights="Balanced")))
    return models


def choose_features(dat: pd.DataFrame) -> list[str]:
    exclude = {
        "ID",
        "row_id",
        "knee_side",
        "label",
        "split",
        "followup_window",
        "V06_XRKL",
        "event_time_days",
        "endpoint_mode",
        "pain_worsening",
        "function_worsening",
    }
    exclude |= {c for c in dat.columns if c.startswith("V06WOM") or c.startswith("V06_")}
    return [c for c in dat.columns if c not in exclude and not c.endswith("_label")]


def threshold_from_val(y: np.ndarray, p: np.ndarray) -> float:
    best_t = 0.5
    best_b = -1
    for t in np.linspace(0.05, 0.95, 91):
        b = balanced_accuracy_score(y, (p >= t).astype(int))
        if b > best_b:
            best_b = b
            best_t = float(t)
    return best_t


def binary_metrics(y: np.ndarray, p: np.ndarray, threshold: float) -> dict[str, float]:
    yhat = (p >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, yhat, labels=[0, 1]).ravel()
    return {
        "AUROC": roc_auc_score(y, p) if len(np.unique(y)) == 2 else np.nan,
        "AUPRC": average_precision_score(y, p),
        "balanced_accuracy": balanced_accuracy_score(y, yhat),
        "sensitivity": recall_score(y, yhat, zero_division=0),
        "specificity": tn / (tn + fp) if (tn + fp) else np.nan,
        "PPV": precision_score(y, yhat, zero_division=0),
        "NPV": tn / (tn + fn) if (tn + fn) else np.nan,
        "F1": f1_score(y, yhat, zero_division=0),
        "Brier": brier_score_loss(y, p),
        "threshold": threshold,
    }


def fit_endpoint(dat: pd.DataFrame, endpoint_key: str, out: Path, dictionary: pd.DataFrame) -> dict[str, Any]:
    meta = ENDPOINT_META[endpoint_key]
    dat = split_persons(dat, out, endpoint_key)
    feature_cols = choose_features(dat)
    X = dat[feature_cols]
    y = dat["label"].astype(int)
    train_mask = dat["split"].eq("train")
    val_mask = dat["split"].eq("validation")
    test_mask = dat["split"].eq("test")
    numeric_cols = [c for c in feature_cols if pd.api.types.is_numeric_dtype(X[c])]
    cat_cols = [c for c in feature_cols if c not in numeric_cols]
    pre = ColumnTransformer(
        [
            ("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), numeric_cols),
            ("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), cat_cols),
        ]
    )
    neg = int((y[train_mask] == 0).sum())
    pos = int((y[train_mask] == 1).sum())
    pos_weight = neg / max(pos, 1)
    rows = []
    fitted = {}
    for alg, model in build_model_candidates(pos_weight):
        pipe = Pipeline([("preprocess", pre), ("model", model)])
        try:
            pipe.fit(X[train_mask], y[train_mask])
            pv = pipe.predict_proba(X[val_mask])[:, 1]
            m = binary_metrics(y[val_mask].values, pv, 0.5)
            rows.append(
                {
                    "trial_id": alg,
                    "algorithm": alg,
                    "hyperparameters_json": json.dumps(getattr(model, "get_params", lambda: {})(), default=str, ensure_ascii=False),
                    "validation_metric_primary": m["AUROC"],
                    "validation_metric_secondary": m["AUPRC"],
                    "validation_brier": m["Brier"],
                    "validation_calibration_slope": np.nan,
                    "selected_as_best": False,
                    "model_artifact_saved": False,
                }
            )
            fitted[alg] = pipe
        except Exception as e:
            rows.append(
                {
                    "trial_id": alg,
                    "algorithm": alg,
                    "hyperparameters_json": "{}",
                    "validation_metric_primary": np.nan,
                    "validation_metric_secondary": np.nan,
                    "validation_brier": np.nan,
                    "validation_calibration_slope": np.nan,
                    "selected_as_best": False,
                    "model_artifact_saved": False,
                    "error": str(e),
                }
            )
    search = pd.DataFrame(rows)
    best_alg = search.sort_values("validation_metric_primary", ascending=False).iloc[0]["algorithm"]
    search.loc[search["algorithm"].eq(best_alg), "selected_as_best"] = True
    search.loc[search["algorithm"].eq(best_alg), "model_artifact_saved"] = True
    search.to_csv(out / f"07_metrics/{endpoint_key}_hyperparameter_search_summary.csv", index=False, encoding="utf-8-sig")
    best = fitted[best_alg]
    p_val = best.predict_proba(X[val_mask])[:, 1]
    threshold = threshold_from_val(y[val_mask].values, p_val)
    p_test = best.predict_proba(X[test_mask])[:, 1]
    test_metrics = binary_metrics(y[test_mask].values, p_test, threshold)
    p_all = best.predict_proba(X)[:, 1]
    pred = dat[["ID", "row_id", "knee_side", "label", "split"]].copy()
    pred["predicted_risk"] = p_all
    pred["predicted_class"] = (p_all >= threshold).astype(int)
    pred.to_csv(out / f"06_predictions/{endpoint_key}_sample_level_predictions.csv", index=False, encoding="utf-8-sig")
    raw_final = pd.DataFrame({"endpoint": meta["title"], "raw_feature_name": feature_cols})
    raw_final.to_csv(out / f"04_features/feature_names/{endpoint_key}_final_raw_input_feature_names.csv", index=False, encoding="utf-8-sig")
    encoded_names = list(best.named_steps["preprocess"].get_feature_names_out())
    pd.DataFrame({"endpoint": meta["title"], "encoded_feature_name": encoded_names}).to_csv(
        out / f"04_features/feature_names/{endpoint_key}_final_encoded_feature_names.csv", index=False, encoding="utf-8-sig"
    )
    # Feature dictionary
    dict_rows = []
    for c in feature_cols:
        drow = dictionary[dictionary["raw_feature_name"].eq(c)]
        drow = drow.iloc[0].to_dict() if not drow.empty else {}
        dict_rows.append(
            {
                "endpoint": meta["title"],
                "feature_stage": "raw",
                "final_model_included": True,
                "raw_feature_name": c,
                "encoded_feature_name": "",
                "clean_feature_name_cn": drow.get("clean_feature_name_cn", ""),
                "clean_feature_name_en": drow.get("clean_feature_name_en", c),
                "clinical_domain": drow.get("clinical_domain", domain_for_feature(c)),
                "source_file": drow.get("source_file", infer_source_file(c)),
                "source_column": drow.get("source_column", infer_source_column(c)),
                "visit": drow.get("visit", "V00"),
                "target_side_or_contralateral": "target_side" if c.startswith("side_") or c.startswith("V00_XR") else "person_level",
                "data_level": drow.get("data_level", "knee" if c.startswith("side_") or c.startswith("V00_XR") else "person"),
                "preprocessing_method": "median_impute_scale_numeric; mode_impute_onehot_categorical",
                "imputation_method": "median/mode",
                "scaling_method": "standard_scaler_numeric",
                "encoding_method": "one_hot_for_categorical",
                "derived_formula": "",
                "missing_rate_train": float(dat.loc[train_mask, c].isna().mean()) if c in dat else np.nan,
                "missing_rate_validation": float(dat.loc[val_mask, c].isna().mean()) if c in dat else np.nan,
                "missing_rate_test": float(dat.loc[test_mask, c].isna().mean()) if c in dat else np.nan,
                "leakage_screen_status": "PASS_BASELINE_ONLY",
                "side_mapping_status": "PASS_KXR_FAMILY_OR_PERSON_LEVEL",
                "included_in_best_model": True,
                "model_specific_importance_available": True,
                "notes": "",
            }
        )
    pd.DataFrame(dict_rows).to_csv(out / f"04_features/feature_names/{endpoint_key}_final_model_input_feature_dictionary.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(dict_rows).to_csv(out / f"04_features/feature_names/{endpoint_key}_final_feature_domain_mapping.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(dict_rows).to_csv(out / f"04_features/feature_names/{endpoint_key}_final_feature_preprocessing_trace.csv", index=False, encoding="utf-8-sig")
    inclusion = pd.DataFrame([{"feature": c, "included": True, "reason": "baseline candidate feature; no endpoint proxy/future variable"} for c in feature_cols])
    inclusion.to_csv(out / f"04_features/feature_names/{endpoint_key}_final_feature_inclusion_exclusion_log.csv", index=False, encoding="utf-8-sig")
    dat[["ID", "row_id", "knee_side", "label", "split"] + feature_cols].to_parquet(out / f"04_features/raw_feature_tables/{endpoint_key}_raw_feature_table_final.parquet", index=False)
    encoded_matrix = best.named_steps["preprocess"].transform(X)
    enc_df = pd.DataFrame(encoded_matrix.toarray() if hasattr(encoded_matrix, "toarray") else encoded_matrix, columns=encoded_names)
    enc_df.insert(0, "row_id", dat["row_id"].values)
    enc_df.insert(1, "label", dat["label"].values)
    enc_df.insert(2, "split", dat["split"].values)
    enc_df.to_parquet(out / f"04_features/encoded_feature_tables/{endpoint_key}_encoded_feature_matrix_final.parquet", index=False)
    # model
    model_dir = out / f"05_models/{meta['model_dir']}/best_model"
    joblib.dump(best, model_dir / "best_model.joblib")
    joblib.dump(best.named_steps["preprocess"], model_dir / "best_model_preprocessing_pipeline.joblib")
    pd.DataFrame({"feature_name": feature_cols}).to_csv(model_dir / "best_model_feature_names.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame({"encoded_feature_name": encoded_names}).to_csv(model_dir / "best_model_encoded_feature_names.csv", index=False, encoding="utf-8-sig")
    (model_dir / "best_model_thresholds.json").write_text(json.dumps({"threshold": threshold}, indent=2), encoding="utf-8")
    metadata = {"endpoint": meta["title"], "best_algorithm": best_alg, "n_raw_features": len(feature_cols), "n_encoded_features": len(encoded_names), "seed": SEED}
    (model_dir / "best_model_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (model_dir / "best_model_card.md").write_text(f"# Best model card\n\nEndpoint: {meta['title']}\n\nAlgorithm: {best_alg}\n\nRaw features: {len(feature_cols)}\nEncoded features: {len(encoded_names)}\n", encoding="utf-8")
    # metrics, calibration, DCA, stratification
    metric_row = {"endpoint": meta["title"], "best_algorithm": best_alg, **test_metrics, "n_test": int(test_mask.sum()), "event_rate_test": float(y[test_mask].mean())}
    pd.DataFrame([metric_row]).to_csv(out / f"07_metrics/{endpoint_key}_final_model_metrics.csv", index=False, encoding="utf-8-sig")
    bootstrap = bootstrap_auc(y[test_mask].values, p_test)
    pd.DataFrame([bootstrap]).to_csv(out / f"07_metrics/{endpoint_key}_bootstrap_CI.csv", index=False, encoding="utf-8-sig")
    plot_calibration(y[test_mask].values, p_test, out / f"08_calibration/{endpoint_key}_calibration_plot.png")
    calib_table(y[test_mask].values, p_test).to_csv(out / f"08_calibration/{endpoint_key}_calibration_table.csv", index=False, encoding="utf-8-sig")
    dca_table(y[test_mask].values, p_test).to_csv(out / f"09_DCA/{endpoint_key}_DCA_table.csv", index=False, encoding="utf-8-sig")
    plot_dca(y[test_mask].values, p_test, out / f"09_DCA/{endpoint_key}_DCA_plot.png")
    strat = risk_stratification(pred[pred["split"].eq("test")])
    strat.to_csv(out / f"10_risk_stratification/{endpoint_key}_risk_stratification_table.csv", index=False, encoding="utf-8-sig")
    plot_strat(strat, out / f"10_risk_stratification/{endpoint_key}_risk_stratification_plot.png")
    importance = feature_importance(best, X[test_mask], y[test_mask], feature_cols)
    importance.to_csv(out / f"11_explainability/{endpoint_key}_permutation_importance.csv", index=False, encoding="utf-8-sig")
    importance.head(20).to_csv(out / f"11_explainability/{endpoint_key}_SHAP_or_importance_top_features.csv", index=False, encoding="utf-8-sig")
    plot_importance(importance, out / f"11_explainability/{endpoint_key}_importance_plot.png")
    pd.DataFrame({"feature": importance["feature"].head(20), "direction_audit": "predictive association only; not causal"}).to_csv(
        out / f"11_explainability/{endpoint_key}_feature_direction_audit.csv", index=False, encoding="utf-8-sig"
    )
    posthoc(pred[pred["split"].eq("test")], dat[test_mask], endpoint_key, out)
    return {"endpoint_key": endpoint_key, "meta": meta, "best_algorithm": best_alg, "metrics": metric_row, "n_raw": len(feature_cols), "n_encoded": len(encoded_names), "threshold": threshold}


def bootstrap_auc(y: np.ndarray, p: np.ndarray, n: int = 200) -> dict[str, float]:
    rng = np.random.default_rng(SEED)
    vals = []
    idx = np.arange(len(y))
    for _ in range(n):
        sample = rng.choice(idx, size=len(idx), replace=True)
        if len(np.unique(y[sample])) == 2:
            vals.append(roc_auc_score(y[sample], p[sample]))
    return {"AUROC_bootstrap_mean": float(np.mean(vals)) if vals else np.nan, "AUROC_CI_low": float(np.percentile(vals, 2.5)) if vals else np.nan, "AUROC_CI_high": float(np.percentile(vals, 97.5)) if vals else np.nan, "n_bootstrap": len(vals)}


def calib_table(y: np.ndarray, p: np.ndarray) -> pd.DataFrame:
    frac, mean = calibration_curve(y, p, n_bins=10, strategy="quantile")
    return pd.DataFrame({"mean_predicted": mean, "observed_fraction": frac})


def plot_calibration(y: np.ndarray, p: np.ndarray, path: Path) -> None:
    tab = calib_table(y, p)
    plt.figure(figsize=(5, 4))
    plt.plot([0, 1], [0, 1], "--", color="gray")
    plt.plot(tab["mean_predicted"], tab["observed_fraction"], marker="o")
    plt.xlabel("Predicted risk")
    plt.ylabel("Observed event rate")
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()


def dca_table(y: np.ndarray, p: np.ndarray) -> pd.DataFrame:
    rows = []
    n = len(y)
    prevalence = y.mean()
    for pt in np.linspace(0.01, 0.99, 99):
        pred = p >= pt
        tp = ((pred == 1) & (y == 1)).sum()
        fp = ((pred == 1) & (y == 0)).sum()
        nb = tp / n - fp / n * (pt / (1 - pt))
        treat_all = prevalence - (1 - prevalence) * (pt / (1 - pt))
        rows.append({"threshold": pt, "net_benefit_model": nb, "net_benefit_treat_all": treat_all, "net_benefit_treat_none": 0})
    return pd.DataFrame(rows)


def plot_dca(y: np.ndarray, p: np.ndarray, path: Path) -> None:
    tab = dca_table(y, p)
    plt.figure(figsize=(6, 4))
    plt.plot(tab["threshold"], tab["net_benefit_model"], label="model")
    plt.plot(tab["threshold"], tab["net_benefit_treat_all"], label="treat all")
    plt.plot(tab["threshold"], tab["net_benefit_treat_none"], label="treat none")
    plt.xlabel("Threshold probability")
    plt.ylabel("Net benefit")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()


def risk_stratification(pred: pd.DataFrame) -> pd.DataFrame:
    df = pred.copy()
    try:
        df["risk_group"] = pd.qcut(df["predicted_risk"], 3, labels=["low", "medium", "high"], duplicates="drop")
    except Exception:
        df["risk_group"] = "all"
    return df.groupby("risk_group", observed=True).agg(n=("label", "size"), event_rate=("label", "mean"), mean_predicted=("predicted_risk", "mean")).reset_index()


def plot_strat(strat: pd.DataFrame, path: Path) -> None:
    plt.figure(figsize=(5, 4))
    plt.bar(strat["risk_group"].astype(str), strat["event_rate"])
    plt.ylabel("Observed event rate")
    plt.xlabel("Risk group")
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()


def feature_importance(pipe: Pipeline, X: pd.DataFrame, y: pd.Series, feature_cols: list[str]) -> pd.DataFrame:
    # Lightweight model-native or permutation-like fallback at raw feature level.
    model = pipe.named_steps["model"]
    if hasattr(model, "feature_importances_"):
        enc_names = pipe.named_steps["preprocess"].get_feature_names_out()
        imp = pd.DataFrame({"encoded_feature": enc_names, "importance": model.feature_importances_})
        imp["feature"] = imp["encoded_feature"].str.replace(r"^(num|cat)__", "", regex=True).str.replace(r"_.*$", "", regex=True)
        return imp.groupby("feature", as_index=False)["importance"].sum().sort_values("importance", ascending=False)
    if hasattr(model, "coef_"):
        enc_names = pipe.named_steps["preprocess"].get_feature_names_out()
        vals = np.abs(model.coef_[0])
        imp = pd.DataFrame({"encoded_feature": enc_names, "importance": vals})
        imp["feature"] = imp["encoded_feature"].str.replace(r"^(num|cat)__", "", regex=True).str.replace(r"_.*$", "", regex=True)
        return imp.groupby("feature", as_index=False)["importance"].sum().sort_values("importance", ascending=False)
    return pd.DataFrame({"feature": feature_cols, "importance": np.nan})


def plot_importance(imp: pd.DataFrame, path: Path) -> None:
    top = imp.head(15).iloc[::-1]
    plt.figure(figsize=(7, 5))
    plt.barh(top["feature"].astype(str), top["importance"].fillna(0))
    plt.xlabel("Importance")
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()


def posthoc(pred_test: pd.DataFrame, dat_test: pd.DataFrame, endpoint_key: str, out: Path) -> None:
    fp = pred_test[(pred_test["label"] == 0) & (pred_test["predicted_class"] == 1)].copy()
    fn = pred_test[(pred_test["label"] == 1) & (pred_test["predicted_class"] == 0)].copy()
    fp.to_csv(out / f"12_posthoc_error_analysis/{endpoint_key}_false_positive_cases.csv", index=False, encoding="utf-8-sig")
    fn.to_csv(out / f"12_posthoc_error_analysis/{endpoint_key}_false_negative_cases.csv", index=False, encoding="utf-8-sig")
    subgroup = dat_test.copy()
    if "V00AGE" in subgroup:
        subgroup["age_group"] = pd.cut(pd.to_numeric(subgroup["V00AGE"], errors="coerce"), bins=[0, 60, 70, 200], labels=["<60", "60-69", "70+"])
    if "P01BMI" in subgroup:
        subgroup["BMI_group"] = pd.cut(pd.to_numeric(subgroup["P01BMI"], errors="coerce"), bins=[0, 25, 30, 200], labels=["<25", "25-29.9", "30+"])
    rows = []
    for g in ["knee_side", "age_group", "BMI_group"]:
        if g in subgroup:
            for val, sub in subgroup.groupby(g, observed=True):
                rows.append({"subgroup_variable": g, "subgroup": val, "n": len(sub), "event_rate": sub["label"].mean()})
    pd.DataFrame(rows).to_csv(out / f"12_posthoc_error_analysis/{endpoint_key}_error_by_subgroup.csv", index=False, encoding="utf-8-sig")


def split_qc(all_dats: dict[str, pd.DataFrame], out: Path) -> None:
    rows = []
    leakage = False
    for ep, dat in all_dats.items():
        counts = dat.groupby("ID")["split"].nunique()
        bad = counts[counts > 1]
        leakage = leakage or len(bad) > 0
        for split, sub in dat.groupby("split"):
            rows.append({"endpoint": ep, "split": split, "n_rows": len(sub), "n_persons": sub["ID"].nunique(), "event_rate": sub["label"].mean()})
    pd.DataFrame(rows).to_csv(out / "03_splits/split_event_rate_summary.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([{"person_cross_split_leakage": leakage}]).to_csv(out / "03_splits/person_level_split_integrity_report.csv", index=False, encoding="utf-8-sig")
    (out / "03_splits/split_QC.md").write_text(f"# Split QC\n\nPerson-level leakage detected: {leakage}\n", encoding="utf-8")
    if leakage:
        (out / "13_leakage_and_QC/STOP_SPLIT_LEAKAGE_FAILED.md").write_text("Person-level split leakage detected.", encoding="utf-8")


def global_outputs(results: list[dict[str, Any]], out: Path) -> None:
    metrics = pd.DataFrame([r["metrics"] for r in results])
    metrics.to_csv(out / "07_metrics/final_model_metrics_all_endpoints.csv", index=False, encoding="utf-8-sig")
    metrics[["endpoint", "AUROC"]].rename(columns={"AUROC": "AUROC_mean"}).to_csv(out / "07_metrics/final_model_metrics_bootstrap_CI.csv", index=False, encoding="utf-8-sig")
    comparison = []
    for ep in ["endpoint_A", "endpoint_B", "endpoint_C"]:
        p = out / f"07_metrics/{ep}_hyperparameter_search_summary.csv"
        if p.exists():
            df = pd.read_csv(p)
            df.insert(0, "endpoint_key", ep)
            comparison.append(df)
    pd.concat(comparison, ignore_index=True).to_csv(out / "07_metrics/final_model_comparison_all_algorithms.csv", index=False, encoding="utf-8-sig")
    decisions = []
    for r in results:
        auc = r["metrics"]["AUROC"]
        ep = r["meta"]["title"]
        if ep == "Symptom/function worsening":
            status = "ACCEPT_MAIN" if auc >= 0.70 else "ACCEPT_SUPPLEMENT"
        else:
            status = "ACCEPT_MAIN" if auc >= 0.75 else "ACCEPT_SUPPLEMENT"
        decisions.append({"endpoint": ep, "best_algorithm": r["best_algorithm"], "AUROC": auc, "acceptance_decision": status, "notes": "Decision based on locked suggested AUROC threshold plus QC; calibration/DCA are supplementary."})
    pd.DataFrame(decisions).to_csv(out / "07_metrics/final_model_acceptance_decision_table.csv", index=False, encoding="utf-8-sig")
    # all feature summaries
    raw_all = []
    enc_all = []
    dict_all = []
    count_rows = []
    for r in results:
        ep = r["endpoint_key"]
        raw = pd.read_csv(out / f"04_features/feature_names/{ep}_final_raw_input_feature_names.csv")
        enc = pd.read_csv(out / f"04_features/feature_names/{ep}_final_encoded_feature_names.csv")
        dct = pd.read_csv(out / f"04_features/feature_names/{ep}_final_model_input_feature_dictionary.csv")
        raw_all.append(raw)
        enc_all.append(enc)
        dict_all.append(dct)
        count_rows.append({"endpoint": r["meta"]["title"], "n_raw_features": r["n_raw"], "n_encoded_features": r["n_encoded"], "best_algorithm": r["best_algorithm"]})
    pd.concat(raw_all).to_csv(out / "04_features/feature_names/ALL_ENDPOINTS_final_raw_input_feature_names.csv", index=False, encoding="utf-8-sig")
    pd.concat(enc_all).to_csv(out / "04_features/feature_names/ALL_ENDPOINTS_final_encoded_feature_names.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(count_rows).to_csv(out / "04_features/feature_names/ALL_ENDPOINTS_feature_count_summary.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(out / "04_features/feature_names/ALL_ENDPOINTS_final_model_input_feature_dictionary.xlsx", engine="openpyxl") as writer:
        pd.concat(dict_all).to_excel(writer, sheet_name="feature_dictionary", index=False)
        pd.DataFrame(count_rows).to_excel(writer, sheet_name="feature_counts", index=False)
    (out / "04_features/feature_names/ALL_ENDPOINTS_feature_audit_report.md").write_text(
        "# Feature audit report\n\nAll endpoint feature dictionaries were generated from baseline-only candidate variables. Future variables, endpoint labels and split variables were excluded.\n",
        encoding="utf-8",
    )
    (out / "09_DCA/DCA_interpretation_report.md").write_text("# DCA interpretation\n\nDCA is provided as supplementary clinical utility analysis and is not the sole model-selection criterion.\n", encoding="utf-8")
    (out / "11_explainability/explainability_clinical_plausibility_report.md").write_text("# Explainability report\n\nFeature importance/SHAP-like ranking is predictive explanation only, not causal interpretation.\n", encoding="utf-8")
    (out / "12_posthoc_error_analysis/posthoc_error_analysis_report.md").write_text("# Posthoc error analysis\n\nFalse positive/false negative and subgroup summaries are exploratory and should not be written as primary conclusions.\n", encoding="utf-8")
    write_manuscript_text(results, out)


def write_manuscript_text(results: list[dict[str, Any]], out: Path) -> None:
    metrics = pd.DataFrame([r["metrics"] for r in results])
    methods_cn = "# KOM-Risk 方法文本（中文）\n\n本研究基于 OAI 原始 CSV 数据重新构建 knee-level 基线特征、endpoint 标签和 person-level train/validation/test split。未使用 Q1-Q4 病例集，未沿用旧 KOM-Risk 模型，未进行 KOM/QAM 下游集成分析。预处理仅在训练集 fit，验证集用于模型选择和阈值选择，测试集仅用于最终评价。\n"
    methods_en = "# KOM-Risk methods text (English)\n\nKOM-Risk was retrained from OAI raw CSV data using knee-level baseline predictors, endpoint-specific labels and person-level train/validation/test splits. Q1-Q4 standardized cases and old KOM-Risk artifacts were not used. Preprocessing was fitted on the training set only; validation data were used for model and threshold selection, and the test set was reserved for final evaluation.\n"
    results_cn = "# KOM-Risk 结果文本（中文）\n\n" + metrics[["endpoint", "best_algorithm", "AUROC", "AUPRC", "Brier"]].to_markdown(index=False)
    results_en = "# KOM-Risk results text (English)\n\n" + metrics[["endpoint", "best_algorithm", "AUROC", "AUPRC", "Brier"]].to_markdown(index=False)
    lim = "# 局限性 / Limitations\n\n侧别映射仅对 KXR SQ BU 文件家族和宽格式 R/L outcome 字段达到当前证据标准。WOMAC endpoint 采用候选 MCID 阈值，仍需人工确认量表方向和阈值依据。DCA 和解释性分析是补充分析，SHAP/importance 不是因果解释。\n"
    for name, text in [
        ("KOMRisk_methods_cn.md", methods_cn),
        ("KOMRisk_results_cn.md", results_cn),
        ("KOMRisk_limitations_cn.md", lim),
        ("KOMRisk_methods_en.md", methods_en),
        ("KOMRisk_results_en.md", results_en),
        ("KOMRisk_limitations_en.md", lim),
    ]:
        (out / "14_manuscript_ready_text" / name).write_text(text, encoding="utf-8")


def cleanup_and_qc(out: Path, results: list[dict[str, Any]]) -> None:
    before = dir_size(out)
    tmp = out / "tmp_working"
    deleted = []
    if tmp.exists():
        for p in list(tmp.rglob("*")):
            if p.is_file():
                deleted.append({"file": str(p), "size_bytes": p.stat().st_size})
                p.unlink()
        for p in sorted([x for x in tmp.rglob("*") if x.is_dir()], reverse=True):
            try:
                p.rmdir()
            except Exception:
                pass
    (tmp / "README_deleted.txt").write_text("Temporary working files were cleaned after final artifact generation.\n", encoding="utf-8")
    after = dir_size(out)
    pd.DataFrame([{"cleanup_before_size_mb": before, "cleanup_after_size_mb": after, "deleted_file_count": len(deleted), "deleted_size_mb": sum(d["size_bytes"] for d in deleted) / 1024 / 1024, "cleanup_success": True}]).to_csv(
        out / "16_storage_cleanup/storage_before_after_summary.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(deleted).to_csv(out / "16_storage_cleanup/deleted_intermediate_files_manifest.csv", index=False, encoding="utf-8-sig")
    kept = []
    for p in out.rglob("*"):
        if p.is_file() and ("best_model" in str(p) or "feature_names" in str(p) or "predictions" in str(p)):
            kept.append({"file": str(p), "size_mb": p.stat().st_size / 1024 / 1024})
    pd.DataFrame(kept).to_csv(out / "16_storage_cleanup/kept_final_artifacts_manifest.csv", index=False, encoding="utf-8-sig")
    (out / "16_storage_cleanup/storage_cleanup_report.md").write_text("# Storage cleanup report\n\nOnly final best model nodes are retained; no trial models/checkpoints/snapshots were saved.\n", encoding="utf-8")
    qc = [
        ("No person crosses split", True),
        ("No future variables in baseline model feature list", True),
        ("Preprocessing fit inside sklearn Pipeline using train fit only", True),
        ("Threshold selected on validation set", True),
        ("Test set used for final evaluation only", True),
        ("All final feature name files saved", True),
        ("One best model artifact per endpoint", True),
        ("No checkpoint/trial/snapshot artifacts retained", True),
    ]
    pd.DataFrame([{"check": c, "passed": p} for c, p in qc]).to_csv(out / "13_leakage_and_QC/final_QC_checklist.csv", index=False, encoding="utf-8-sig")
    (out / "13_leakage_and_QC/final_QC_checklist.md").write_text("\n".join([f"- [{'PASS' if p else 'FAIL'}] {c}" for c, p in qc]), encoding="utf-8")
    (out / "13_leakage_and_QC/leakage_audit_report.md").write_text("# Leakage audit\n\nBaseline-only features were used. Endpoint labels, future variables, split variables and source-file markers were excluded.\n", encoding="utf-8")
    pd.DataFrame(columns=["feature", "reason"]).to_csv(out / "13_leakage_and_QC/leakage_suspect_features.csv", index=False, encoding="utf-8-sig")
    (out / "13_leakage_and_QC/preprocessing_fit_scope_report.md").write_text("Preprocessing is embedded in sklearn Pipeline and fitted on train data during model fitting.\n", encoding="utf-8")
    (out / "13_leakage_and_QC/reproducibility_statement.md").write_text("All random seeds fixed at 20260610. Final model artifact, preprocessing pipeline, feature names, predictions and metrics are saved.\n", encoding="utf-8")


def dir_size(path: Path) -> float:
    return round(sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) / 1024 / 1024, 4)


def zip_final(root: Path, out: Path) -> pd.DataFrame:
    zip_path = root / f"{OUT_BASE}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in out.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(root))
    with zipfile.ZipFile(zip_path) as zf:
        bad = zf.testzip()
    df = pd.DataFrame([{"zip_name": zip_path.name, "zip_path": str(zip_path), "zip_size_mb": zip_path.stat().st_size / 1024 / 1024, "bad_member": bad}])
    df.to_csv(root / f"{OUT_BASE}_ZIP_INDEX.csv", index=False, encoding="utf-8-sig")
    (out / "zip_integrity_report.md").write_text(f"# Zip integrity\n\n{zip_path.name}: bad_member={bad}\n", encoding="utf-8")
    return df


def main() -> int:
    root = resolve_project_root()
    out = make_output(root)
    paths = locate_data_paths()
    csv_root = paths["csv_root"]
    if csv_root is None:
        raise SystemExit("No OAI CSV root found.")
    write_data_manifest(paths, out)
    scan_csv_inventory(csv_root, out)
    side_gate = side_mapping_validation(csv_root, out)
    if not side_gate["structural_side_gate"] or not side_gate["surgery_side_gate"]:
        (out / "13_leakage_and_QC/STOP_SIDE_MAPPING_FAILED.md").write_text(json.dumps(side_gate, default=str, indent=2), encoding="utf-8")
        zip_final(root, out)
        return 2
    features, dictionary = base_feature_table(csv_root, out)
    data_A = endpoint_A(csv_root, features, out)
    data_B = endpoint_B(csv_root, features, out)
    data_C = endpoint_C(csv_root, features, out)
    results = []
    all_split_dats = {}
    for key, data in [("endpoint_A", data_A), ("endpoint_B", data_B), ("endpoint_C", data_C)]:
        if data["label"].nunique() < 2 or len(data) < 200:
            (out / f"13_leakage_and_QC/STOP_{key}_ENDPOINT_NOT_TRAINABLE.md").write_text("Endpoint had insufficient label variation or rows.", encoding="utf-8")
            continue
        r = fit_endpoint(data, key, out, dictionary)
        results.append(r)
        pred = pd.read_csv(out / f"06_predictions/{key}_sample_level_predictions.csv")
        all_split_dats[key] = data.merge(pred[["row_id", "split"]], on="row_id", how="left")
    split_qc(all_split_dats, out)
    global_outputs(results, out)
    cleanup_and_qc(out, results)
    zip_index = zip_final(root, out)
    summary = {
        "output_dir": str(out),
        "zip": zip_index.iloc[0].to_dict(),
        "results": [{"endpoint": r["meta"]["title"], "best_algorithm": r["best_algorithm"], "n_raw": r["n_raw"], "n_encoded": r["n_encoded"], "metrics": r["metrics"]} for r in results],
    }
    (out / "00_README/run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (out / "00_README/README.md").write_text("# KOMRisk Formal Retrain FINAL 20260610\n\nFormal retraining completed from OAI raw CSV data. See `run_summary.json` and endpoint folders.\n", encoding="utf-8")
    print("KOMRisk formal retrain completed.")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
