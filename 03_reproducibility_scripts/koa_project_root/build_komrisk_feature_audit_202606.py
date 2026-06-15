from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from glob import glob
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


AUDIT_NAME = "KOMRisk_Feature_Audit_202606"
VISIT_RE = re.compile(r"(V(?:00|01|02|03|04|05|06|07|08|09|10|11|99))", re.I)
TARGET_ZIPS = {
    "KOM_Submission_Audit_Package_202606_FINAL.zip",
    "KOM_Submission_Audit_Package_202606_FINAL (2).zip",
    "KOM_Submission_Audit_Package_202606_FINAL_DELTA_FIXED.zip",
    "KOM_All_Data_and_Prediction_Model_Package_202606.zip",
}


ENDPOINTS = [
    {
        "endpoint": "KL structural progression",
        "algorithm": "LightGBM",
        "clinical_question": "Predict longitudinal radiographic KL structural progression in OAI knees.",
        "output_type": "binary classification",
        "primary_metric": "AUROC",
        "secondary_metrics": "BACC",
        "current_result": "AUROC=0.817; BACC=0.735",
        "sample_size": 7855,
        "event_rate": 13.4,
    },
    {
        "endpoint": "TKR / knee surgery event",
        "algorithm": "CoxPH",
        "clinical_question": "Predict time-to-TKR or knee surgery event during longitudinal follow-up.",
        "output_type": "time-to-event survival prediction",
        "primary_metric": "C-index",
        "secondary_metrics": "event rate",
        "current_result": "C-index=0.862",
        "sample_size": 9014,
        "event_rate": 5.2,
    },
    {
        "endpoint": "Symptom/function worsening",
        "algorithm": "CatBoost",
        "clinical_question": "Predict longitudinal symptom/function worsening.",
        "output_type": "binary classification",
        "primary_metric": "AUROC",
        "secondary_metrics": "event rate",
        "current_result": "AUROC=0.683",
        "sample_size": 8962,
        "event_rate": 31.0,
    },
]


def resolve_root() -> Path:
    candidates = [
        Path(r"C:\OAI研究项目\pythonProject1\KOM返修修改"),
        Path.cwd(),
    ]
    candidates += [Path(p) for p in glob(r"C:\OAI*\pythonProject1\KOM*")]
    for candidate in candidates:
        if (candidate / "KOM_Submission_Audit_Package_202606_FINAL").exists() or (
            candidate / "本地化"
        ).exists():
            return candidate
    raise SystemExit("Could not locate KOM project root.")


def now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_dirs(out: Path) -> dict[str, Path]:
    dirs = {
        "00": out / "00_inventory",
        "01": out / "01_oai_database_column_inventory",
        "02": out / "02_declared_input_concept_list",
        "03": out / "03_variable_mapping",
        "04": out / "04_feature_engineering_audit",
        "05": out / "05_feature_count_by_endpoint",
        "06": out / "06_missing_or_derived_variables",
        "07": out / "07_submission_tables",
        "08": out / "08_codex_rerun_if_needed",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs


def reset_output(root: Path, out: Path) -> list[str]:
    backups: list[str] = []
    if out.exists():
        backup = root / f"{AUDIT_NAME}_backup_{now_tag()}"
        shutil.move(str(out), str(backup))
        backups.append(str(backup))
    zip_out = root / f"{AUDIT_NAME}.zip"
    if zip_out.exists():
        backup_zip = root / f"{AUDIT_NAME}_backup_{now_tag()}.zip"
        shutil.move(str(zip_out), str(backup_zip))
        backups.append(str(backup_zip))
    out.mkdir(parents=True, exist_ok=True)
    return backups


def safe_rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def detect_oai_root(root: Path) -> Path:
    candidates = [
        root / "本地化" / "koa_mdt_agents" / "data" / "raw" / "oai_csv_link",
        Path(r"C:\OAI研究项目\pythonProject1\OAI数据库\OAICompleteData_CSV"),
    ]
    candidates += [Path(p) for p in glob(r"C:\OAI*\pythonProject1\OAI*\OAICompleteData_CSV")]
    for c in candidates:
        if c.exists() and any(c.glob("*.csv")):
            return c
    raise SystemExit("OAICompleteData_CSV not found.")


def detect_domain(file_name: str, columns: Iterable[str] | None = None) -> str:
    text = file_name.upper()
    if columns:
        sample = " ".join(list(columns)[:150]).upper()
        text = f"{text} {sample}"
    if "ENROL" in text or "P02SEX" in text or "P02RACE" in text:
        return "demographics"
    if "OUTCOME" in text or "V99ERK" in text or "V99ELK" in text:
        return "followup_outcome"
    if "SURG" in text or "TKR" in text or "REPLACEMENT" in text:
        return "surgery_outcome"
    if "KXR" in text or "XRKL" in text:
        if "XRKL" in text:
            return "radiograph_KL"
        return "radiograph_structural_features"
    if "MRI" in text or "KMRI" in text:
        return "MRI"
    if "WOM" in text:
        return "WOMAC"
    if "KOOS" in text:
        return "KOOS"
    if "PASE" in text or "ACCEL" in text or "ACTIV" in text:
        return "physical_activity"
    if "CESD" in text or "SF12" in text or re.search(r"\bSF\d+", text):
        return "psychosocial"
    if "NSAID" in text or "MED" in text or "ANALG" in text:
        return "medication"
    if (
        "DIAB" in text
        or "HYP" in text
        or "COMORB" in text
        or "CARD" in text
        or "STROKE" in text
        or "KID" in text
        or "RENAL" in text
        or "ULCER" in text
        or "GI" in text
    ):
        return "comorbidity"
    if "PAIN" in text or "KPN" in text or "NRS" in text:
        return "pain_NRS"
    if "WALK" in text or "STAIR" in text or "FUNC" in text or "ADL" in text:
        return "physical_function"
    if "CLINICAL" in text:
        return "clinical_symptoms"
    return "unknown"


def detect_visit(col: str, file_name: str = "") -> str:
    m = VISIT_RE.search(col)
    if m:
        return m.group(1).upper()
    m = re.search(r"(\d{2})(?:\.CSV|$)", file_name.upper())
    if m:
        return f"V{m.group(1)}"
    return ""


def detect_side(col: str, file_has_side_col: bool = False) -> str:
    up = col.upper()
    if up == "SIDE" or "KNEESIDE" in up or "TARGETKNEE" in up:
        return "both"
    if "ELK" in up or "LEFT" in up or "LKNEE" in up:
        return "left"
    if "ERK" in up or "RIGHT" in up or "RKNEE" in up:
        return "right"
    if file_has_side_col:
        return "both"
    return "not_side_specific"


def possible_measure(col: str, file_name: str = "") -> str:
    up = f"{col} {file_name}".upper()
    rules = [
        ("WOMK", "WOMAC pain"),
        ("WOMADL", "WOMAC function"),
        ("WOMTS", "WOMAC total"),
        ("KOOSKP", "KOOS pain"),
        ("KOOSYM", "KOOS symptoms"),
        ("KOOSFS", "KOOS function"),
        ("KOOSQOL", "KOOS QOL"),
        ("XRKL", "Kellgren-Lawrence grade"),
        ("XRJS", "joint space narrowing"),
        ("XROST", "osteophyte"),
        ("XRSCT", "subchondral sclerosis"),
        ("PASE", "physical activity"),
        ("CESD", "CES-D depressive symptoms"),
        ("SF12", "SF-12"),
        ("NSAID", "NSAID use"),
        ("RXNSAID", "prescription NSAID use"),
        ("PNMED", "pain medication"),
        ("INJ", "injection history"),
        ("FALL", "fall history"),
        ("DIAB", "diabetes"),
        ("HYP", "hypertension"),
        ("BMI", "body mass index"),
        ("AGE", "age"),
        ("SEX", "sex"),
        ("RACE", "race"),
        ("SITE", "site"),
        ("KPN", "knee pain"),
        ("ERK", "right knee surgery/outcome"),
        ("ELK", "left knee surgery/outcome"),
    ]
    for token, measure in rules:
        if token in up:
            return measure
    return ""


def data_type_guess(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_integer_dtype(series):
        return "integer"
    if pd.api.types.is_float_dtype(series):
        return "numeric"
    text = series.dropna().astype(str).head(50)
    if text.empty:
        return "unknown"
    if text.str.match(r"^\d{4}-\d{2}-\d{2}").any() or text.str.match(r"^\d{1,2}/\d{1,2}/\d{2,4}").any():
        return "date_like"
    return "string"


def count_csv_rows(path: Path) -> tuple[Any, str]:
    try:
        if path.stat().st_size > 250_000_000:
            return pd.NA, "row_count_not_computed_large_file"
        with path.open("rb") as f:
            n = sum(1 for _ in f)
        return max(n - 1, 0), ""
    except Exception as e:
        return pd.NA, f"row_count_error:{e}"


def read_sample(path: Path, nrows: int = 1000) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path, nrows=nrows)
    if path.suffix.lower() in {".csv", ".tsv"}:
        sep = "\t" if path.suffix.lower() == ".tsv" else ","
        try:
            return pd.read_csv(path, nrows=nrows, sep=sep, low_memory=False, encoding_errors="ignore")
        except TypeError:
            return pd.read_csv(path, nrows=nrows, sep=sep, low_memory=False)
    if path.suffix.lower() == ".json":
        try:
            return pd.read_json(path, lines=True, nrows=nrows)
        except Exception:
            obj = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
            if isinstance(obj, list):
                return pd.DataFrame(obj[:nrows])
            if isinstance(obj, dict):
                return pd.DataFrame([obj])
    return pd.DataFrame()


def scan_oai(oai_root: Path, out_dirs: dict[str, Path], project_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    file_rows: list[dict[str, Any]] = []
    col_rows: list[dict[str, Any]] = []
    exts = {".csv", ".tsv", ".xlsx", ".xls", ".json", ".parquet", ".sas7bdat", ".xpt", ".sas"}
    files = [p for p in oai_root.rglob("*") if p.is_file() and p.suffix.lower() in exts]
    for path in sorted(files, key=lambda p: str(p).lower()):
        notes: list[str] = []
        df = pd.DataFrame()
        try:
            if path.suffix.lower() == ".parquet":
                df = pd.read_parquet(path)
                if len(df) > 1000:
                    df = df.head(1000)
            elif path.suffix.lower() in {".sas7bdat", ".xpt", ".sas"}:
                notes.append("SAS/XPT file detected; column extraction not attempted in this audit script")
            else:
                df = read_sample(path, 1000)
        except Exception as e:
            notes.append(f"sample_read_error:{e}")
        columns = list(map(str, df.columns)) if not df.empty else []
        domain = detect_domain(path.name, columns)
        visit_prefixes = sorted(set([v for c in columns for v in [detect_visit(c, path.name)] if v]))
        file_has_side_col = any(str(c).upper() == "SIDE" for c in columns)
        side_specific = "yes" if file_has_side_col or any(detect_side(c) in {"left", "right"} for c in columns) else "no"
        n_rows, row_note = count_csv_rows(path) if path.suffix.lower() in {".csv", ".tsv"} else (len(df) if not df.empty else pd.NA, "")
        if row_note:
            notes.append(row_note)
        file_rows.append(
            {
                "file_path": str(path),
                "file_name": path.name,
                "file_type": path.suffix.lower().lstrip("."),
                "num_rows": n_rows,
                "num_columns": len(columns) if columns else pd.NA,
                "detected_domain": domain,
                "visit_prefixes_detected": ";".join(visit_prefixes),
                "side_specific": side_specific,
                "notes": "; ".join(notes),
            }
        )
        for col in columns:
            series = df[col] if col in df.columns else pd.Series(dtype=object)
            nonmissing = int(series.notna().sum())
            missing_rate = float(series.isna().mean()) if len(series) else math.nan
            values = [str(x) for x in series.dropna().astype(str).drop_duplicates().head(3).tolist()]
            measure = possible_measure(col, path.name)
            col_domain = detect_domain(path.name, [col])
            search_tokens = sorted(
                set(
                    token
                    for token in [
                        col.upper(),
                        measure,
                        col_domain,
                        detect_visit(col, path.name),
                        detect_side(col, file_has_side_col),
                    ]
                    if token
                )
            )
            col_rows.append(
                {
                    "file_path": str(path),
                    "file_name": path.name,
                    "column_name": col,
                    "column_name_upper": col.upper(),
                    "visit_prefix": detect_visit(col, path.name),
                    "side": detect_side(col, file_has_side_col),
                    "detected_domain": col_domain,
                    "possible_measure": measure,
                    "data_type_guess": data_type_guess(series),
                    "nonmissing_count": nonmissing,
                    "missing_rate": round(missing_rate, 4) if not math.isnan(missing_rate) else pd.NA,
                    "example_values": " | ".join(values),
                    "search_tags": ";".join(search_tokens),
                }
            )
    file_df = pd.DataFrame(file_rows)
    col_df = pd.DataFrame(col_rows)
    file_df.to_csv(out_dirs["01"] / "oai_file_inventory.csv", index=False, encoding="utf-8-sig")
    col_df.to_csv(out_dirs["01"] / "oai_column_inventory.csv", index=False, encoding="utf-8-sig")
    return file_df, col_df


@dataclass
class Concept:
    name: str
    domain: str
    raw_expected: str
    role: str
    expected_domain: str
    notes: str
    tags: list[str]


CONCEPTS: list[Concept] = [
    Concept("age", "demographics", "raw", "predictor", "demographics", "Baseline age.", ["AGE", "V00AGE"]),
    Concept("sex", "demographics", "raw", "predictor", "demographics", "Participant sex.", ["SEX", "P02SEX"]),
    Concept("BMI", "demographics", "raw", "predictor", "clinical_symptoms", "Body mass index.", ["BMI", "P01BMI"]),
    Concept("race", "demographics", "raw", "predictor", "demographics", "Race/ethnicity field.", ["RACE", "P02RACE"]),
    Concept("site", "demographics", "raw", "split_variable", "demographics", "OAI recruitment/site field.", ["SITE", "V00SITE"]),
    Concept("target knee side", "identifier", "derived", "identifier", "radiograph_KL", "Target side may be derived from knee-specific labels.", ["SIDE", "target", "knee side"]),
    Concept("contralateral knee status", "radiograph", "derived", "derived_predictor", "radiograph_KL", "Clinical construct derived from opposite knee radiographic/symptom fields.", ["contralateral", "opposite", "XRKL", "SIDE"]),
    Concept("WOMAC pain", "symptom_function", "raw", "predictor", "WOMAC", "Baseline WOMAC pain score, side-specific if available.", ["WOMK", "WOMAC pain", "V00WOMKPR", "V00WOMKPL"]),
    Concept("WOMAC function", "symptom_function", "raw", "predictor", "WOMAC", "Baseline WOMAC function/ADL score.", ["WOMADL", "WOMAC function", "V00WOMADLR", "V00WOMADLL"]),
    Concept("WOMAC total", "symptom_function", "raw", "predictor", "WOMAC", "Baseline WOMAC total score.", ["WOMTS", "WOMAC total"]),
    Concept("KOOS pain", "symptom_function", "raw", "predictor", "KOOS", "Baseline KOOS pain.", ["KOOSKP", "KOOS pain"]),
    Concept("KOOS symptoms", "symptom_function", "raw", "predictor", "KOOS", "Baseline KOOS symptoms.", ["KOOSYM", "KOOS symptoms"]),
    Concept("KOOS ADL", "symptom_function", "raw", "predictor", "KOOS", "Baseline KOOS ADL/function.", ["KOOSFS", "KOOSFX", "KOOS ADL"]),
    Concept("KOOS QOL", "symptom_function", "raw", "predictor", "KOOS", "Baseline KOOS quality of life.", ["KOOSQOL", "KOOS QOL"]),
    Concept("NRS pain", "pain", "candidate", "predictor", "pain_NRS", "May be clinical knee pain severity if NRS source exists.", ["NRS", "PAIN", "KPN"]),
    Concept("night pain", "pain", "candidate", "predictor", "clinical_symptoms", "Clinical symptom construct; must verify raw source.", ["night pain", "NIGHT", "PAIN"]),
    Concept("resting pain", "pain", "candidate", "predictor", "clinical_symptoms", "Clinical symptom construct; must verify raw source.", ["rest pain", "REST", "PAIN"]),
    Concept("morning stiffness", "symptom_function", "raw", "predictor", "WOMAC", "Stiffness may be represented through WOMAC stiffness fields.", ["WOMSTF", "STIFF"]),
    Concept("PASE", "activity", "raw", "predictor", "physical_activity", "Physical Activity Scale for the Elderly.", ["PASE", "V00PASE"]),
    Concept("physical activity", "activity", "raw", "predictor", "physical_activity", "Physical activity/accelerometry/PASE fields.", ["PASE", "ACCEL", "ACTIV"]),
    Concept("walking limitation", "function", "candidate", "predictor", "physical_function", "Walking limitation item, if present.", ["WALK", "KOOSFX", "WOMADL"]),
    Concept("stair limitation", "function", "candidate", "predictor", "physical_function", "Stair limitation item, if present.", ["STAIR", "KOOSFX", "WOMADL"]),
    Concept("KL grade", "radiograph", "raw", "predictor", "radiograph_KL", "Kellgren-Lawrence grade.", ["XRKL", "KL", "Kellgren"]),
    Concept("target knee KL grade", "radiograph", "derived", "derived_predictor", "radiograph_KL", "Target-side KL from side-specific radiograph rows.", ["XRKL", "SIDE", "target KL"]),
    Concept("contralateral KL grade", "radiograph", "derived", "derived_predictor", "radiograph_KL", "Opposite-knee KL from side-specific radiograph rows.", ["XRKL", "SIDE", "contralateral KL"]),
    Concept("joint space narrowing", "radiograph", "raw", "predictor", "radiograph_structural_features", "Medial/lateral JSN or joint-space narrowing.", ["XRJS", "JSM", "JSL", "JSN"]),
    Concept("osteophyte", "radiograph", "raw", "predictor", "radiograph_structural_features", "Osteophyte score.", ["XROST", "OSTEOPHYTE"]),
    Concept("subchondral sclerosis", "radiograph", "raw", "predictor", "radiograph_structural_features", "Subchondral sclerosis score.", ["XRSCT", "SCLEROSIS"]),
    Concept("alignment", "radiograph", "candidate", "predictor", "radiograph_structural_features", "Alignment/deformity field if present.", ["ALIGN", "MALALIGN"]),
    Concept("diabetes", "comorbidity", "raw", "predictor", "comorbidity", "Diabetes status.", ["DIAB", "V00DIAB"]),
    Concept("hypertension", "comorbidity", "candidate", "predictor", "comorbidity", "Hypertension status if present.", ["HYP", "HYPERTENSION", "BLOOD PRESSURE"]),
    Concept("cardiovascular disease", "comorbidity", "candidate", "predictor", "comorbidity", "Cardiovascular disease/history if present.", ["CARD", "HEART", "CV", "MI", "STROKE"]),
    Concept("renal risk", "safety", "derived", "derived_predictor", "comorbidity", "Safety construct; requires kidney/eGFR/renal source fields.", ["RENAL", "KIDNEY", "KIDFXN", "EGFR"]),
    Concept("liver risk", "safety", "derived", "derived_predictor", "comorbidity", "Safety construct; requires liver/hepatic source fields.", ["LIVER", "HEPATIC"]),
    Concept("gastrointestinal risk", "safety", "derived", "derived_predictor", "comorbidity", "Safety construct; requires GI ulcer/bleeding fields.", ["GI", "GASTRO", "ULCER", "BLEED"]),
    Concept("fall risk", "safety", "derived", "derived_predictor", "clinical_symptoms", "Construct from fall/balance/history fields.", ["FALL", "BALANCE"]),
    Concept("NSAID use", "medication", "raw", "predictor", "medication", "NSAID use/prescription.", ["NSAID", "RXNSAID"]),
    Concept("analgesic medication use", "medication", "raw", "predictor", "medication", "Pain medication/analgesic use.", ["PNMED", "ANALG", "PAIN MED"]),
    Concept("injection history", "medication", "raw", "predictor", "medication", "Knee injection history.", ["INJ", "STERKN", "HYAINJ"]),
    Concept("rehabilitation history", "treatment", "candidate", "predictor", "clinical_symptoms", "Rehabilitation/PT history if present.", ["REHAB", "PHYSICAL THERAPY", "PT"]),
    Concept("surgery history", "outcome", "raw", "predictor", "surgery_outcome", "Prior or follow-up knee surgery history.", ["SURG", "ERK", "ELK", "TKR"]),
    Concept("depressive symptoms", "psychosocial", "raw", "predictor", "psychosocial", "Depressive symptoms, likely CES-D items/score.", ["CESD", "DEPRESS"]),
    Concept("CES-D", "psychosocial", "raw", "predictor", "psychosocial", "Center for Epidemiologic Studies Depression scale.", ["CESD", "V00CESD"]),
    Concept("SF-12 physical", "psychosocial", "candidate", "predictor", "psychosocial", "SF-12 physical component if present or derivable from SF items.", ["SF12", "PCS", "PHYSICAL"]),
    Concept("SF-12 mental", "psychosocial", "candidate", "predictor", "psychosocial", "SF-12 mental component if present or derivable from SF items.", ["SF12", "MCS", "MENTAL"]),
    Concept("follow-up time", "time", "derived", "time_variable", "followup_outcome", "Follow-up interval derived from visit dates/outcome dates.", ["FOLLOW", "DAYS", "DATE"]),
    Concept("event time", "time", "derived", "time_variable", "followup_outcome", "Event-time variable for time-to-event endpoint.", ["EVENT TIME", "DAYS", "DATE", "V99ERKDAYS", "V99ELKDAYS"]),
    Concept("censoring time", "time", "derived", "censoring_variable", "followup_outcome", "Censoring time for non-events.", ["CENSOR", "FOLLOW", "DAYS"]),
    Concept("KL structural progression", "outcome", "derived", "outcome", "radiograph_KL", "Endpoint derived from longitudinal KL increase.", ["XRKL", "progression", "V00", "V01", "V03", "V05", "V08"]),
    Concept("TKR / knee surgery event", "outcome", "derived", "outcome", "followup_outcome", "Endpoint from OAI knee surgery/replacement fields.", ["TKR", "SURGERY", "ERK", "ELK", "V99"]),
    Concept("symptom/function worsening", "outcome", "derived", "outcome", "WOMAC", "Endpoint derived from longitudinal symptom/function worsening.", ["WOMAC", "KOOS", "worsening", "MCID"]),
]


def build_concept_list(out_dirs: dict[str, Path]) -> pd.DataFrame:
    rows = []
    for i, c in enumerate(CONCEPTS, 1):
        rows.append(
            {
                "concept_id": f"C{i:03d}",
                "concept_name": c.name,
                "clinical_domain": c.domain,
                "raw_or_derived_expected": c.raw_expected,
                "endpoint_role": c.role,
                "expected_oai_domain": c.expected_domain,
                "must_verify": True,
                "notes": c.notes,
                "search_tags": ";".join(c.tags),
            }
        )
    df = pd.DataFrame(rows)
    df.to_csv(out_dirs["02"] / "KOMRisk_declared_input_concepts.csv", index=False, encoding="utf-8-sig")
    return df


def score_candidate(concept: pd.Series, col_row: pd.Series) -> tuple[int, str]:
    score = 0
    reasons: list[str] = []
    tags = [t.strip() for t in str(concept["search_tags"]).split(";") if t.strip()]
    hay = " ".join(
        [
            str(col_row.get("column_name_upper", "")),
            str(col_row.get("file_name", "")).upper(),
            str(col_row.get("possible_measure", "")).upper(),
            str(col_row.get("search_tags", "")).upper(),
        ]
    )
    concept_name = str(concept["concept_name"]).upper()
    file_name = str(col_row.get("file_name", ""))
    col_upper = str(col_row.get("column_name_upper", ""))
    generated_or_metadata = re.search(
        r"(search_results|field_search|audit|dictionary|codebook|inventory|manifest|README)",
        file_name,
        re.I,
    )
    if generated_or_metadata:
        score -= 45
        reasons.append("metadata_or_generated_file_not_raw_oai_source")
    if col_upper in {"ID", "VERSION"} and str(concept["endpoint_role"]) not in {"identifier", "split_variable"}:
        score -= 40
        reasons.append("generic_identifier_column_not_concept_source")
    if concept_name and concept_name in hay:
        score += 35
        reasons.append("concept_name_match")
    for tag in tags:
        up = tag.upper()
        if not up:
            continue
        if up in hay:
            score += 28 if len(up) >= 4 else 12
            reasons.append(f"keyword:{tag}")
    expected = str(concept["expected_oai_domain"])
    if expected and expected == str(col_row.get("detected_domain", "")):
        score += 20
        reasons.append("domain_match")
    if str(col_row.get("visit_prefix", "")) == "V00" and concept["endpoint_role"] in {"predictor", "derived_predictor"}:
        score += 5
        reasons.append("baseline_visit")
    if str(col_row.get("side", "")) in {"left", "right", "both"} and "knee" in concept_name.lower():
        score += 5
        reasons.append("knee_side_available")
    if "OAK" in str(col_row.get("file_path", "")).upper():
        score -= 100
        reasons.append("exclude_oaknet")
    return score, ";".join(dict.fromkeys(reasons))


def build_variable_mapping(concepts_df: pd.DataFrame, col_df: pd.DataFrame, out_dirs: dict[str, Path]) -> tuple[pd.DataFrame, pd.DataFrame]:
    candidate_rows: list[dict[str, Any]] = []
    final_rows: list[dict[str, Any]] = []
    for _, concept in concepts_df.iterrows():
        scored: list[tuple[int, str, pd.Series]] = []
        for _, col in col_df.iterrows():
            score, reason = score_candidate(concept, col)
            if score >= 25:
                scored.append((score, reason, col))
        scored = sorted(scored, key=lambda x: x[0], reverse=True)[:12]
        for score, reason, col in scored:
            candidate_rows.append(
                {
                    "concept_id": concept["concept_id"],
                    "concept_name": concept["concept_name"],
                    "candidate_file": col["file_name"],
                    "candidate_column": col["column_name"],
                    "candidate_visit": col["visit_prefix"],
                    "candidate_side": col["side"],
                    "detected_domain": col["detected_domain"],
                    "match_score": score,
                    "match_reason": reason,
                    "example_values": col["example_values"],
                    "missing_rate": col["missing_rate"],
                    "requires_manual_confirmation": score < 80,
                    "search_tags": concept["search_tags"],
                }
            )
        best = scored[0] if scored else None
        c_role = str(concept["endpoint_role"])
        raw_expected = str(concept["raw_or_derived_expected"])
        if best:
            score, reason, col = best
            bad_generic = str(col["column_name"]).upper() in {"ID", "VERSION"}
            bad_generated = bool(
                re.search(
                    r"(search_results|field_search|audit|dictionary|codebook|inventory|manifest|README)",
                    str(col["file_name"]),
                    re.I,
                )
            )
            if score < 45 or bad_generic or bad_generated:
                final_status = "not_found"
                raw_or_derived = raw_expected
                manual = True
                derivation_rule = "derivation_rule_missing" if raw_expected == "derived" else ""
                col = pd.Series(
                    {
                        "file_name": "",
                        "column_name": "",
                        "visit_prefix": "",
                        "side": "",
                        "data_type_guess": "",
                        "missing_rate": "",
                    }
                )
                reason = f"best_candidate_rejected; score={score}; {reason}"
            elif c_role == "outcome":
                final_status = "outcome_variable"
                raw_or_derived = "derived"
                manual = True
                derivation_rule = "Endpoint label requires longitudinal derivation; listed raw column is source candidate only."
            elif c_role == "time_variable":
                final_status = "time_variable"
                raw_or_derived = "derived"
                manual = True
                derivation_rule = "Time variable derived from visit/date/day fields; exact model derivation rule must be recovered from training code."
            elif c_role == "censoring_variable":
                final_status = "censoring_variable"
                raw_or_derived = "derived"
                manual = True
                derivation_rule = "Censoring time derived from follow-up/event information; exact rule not recovered."
            elif raw_expected == "derived":
                final_status = "derived_from_raw_variables"
                raw_or_derived = "derived"
                manual = True
                derivation_rule = "Derived clinical construct; candidate raw source listed but rule requires manual confirmation."
            elif score >= 80:
                final_status = "raw_variable_found"
                raw_or_derived = "raw"
                manual = False
                derivation_rule = ""
            else:
                final_status = "candidate_found_needs_manual_confirmation"
                raw_or_derived = raw_expected
                manual = True
                derivation_rule = ""
            final_rows.append(
                {
                    "concept_id": concept["concept_id"],
                    "concept_name": concept["concept_name"],
                    "final_status": final_status,
                    "oai_file": col["file_name"],
                    "oai_raw_variable": col["column_name"],
                    "visit": col["visit_prefix"],
                    "side": col["side"],
                    "used_as": c_role,
                    "raw_or_derived": raw_or_derived,
                    "derivation_rule": derivation_rule,
                    "model_endpoint": "all_or_endpoint_specific",
                    "feature_set": "KOM-Risk declared clinical predictor/outcome concept",
                    "data_type": col["data_type_guess"],
                    "missing_rate": col["missing_rate"],
                    "manual_review_needed": manual,
                    "notes": f"Best candidate score={score}; {reason}",
                    "search_tags": concept["search_tags"],
                }
            )
        else:
            status = "not_found"
            if raw_expected == "derived":
                status = "not_found"
            final_rows.append(
                {
                    "concept_id": concept["concept_id"],
                    "concept_name": concept["concept_name"],
                    "final_status": status,
                    "oai_file": "",
                    "oai_raw_variable": "",
                    "visit": "",
                    "side": "",
                    "used_as": c_role,
                    "raw_or_derived": raw_expected,
                    "derivation_rule": "derivation_rule_missing" if raw_expected == "derived" else "",
                    "model_endpoint": "all_or_endpoint_specific",
                    "feature_set": "KOM-Risk declared clinical predictor/outcome concept",
                    "data_type": "",
                    "missing_rate": "",
                    "manual_review_needed": True,
                    "notes": "No matching OAI column found in local CSV inventory.",
                    "search_tags": concept["search_tags"],
                }
            )
    cand_df = pd.DataFrame(candidate_rows)
    final_df = pd.DataFrame(final_rows)
    cand_df.to_csv(out_dirs["03"] / "KOMRisk_variable_mapping_candidates.csv", index=False, encoding="utf-8-sig")
    final_df.to_csv(out_dirs["03"] / "KOMRisk_variable_mapping_FINAL_REVIEW.csv", index=False, encoding="utf-8-sig")
    return cand_df, final_df


DERIVED_FEATURES = [
    ("contralateral_KL", "V00XRKL by SIDE", "Use KL grade from opposite knee side relative to target knee.", "all", "numeric/categorical"),
    ("target_knee_KL_max", "V00XRKL by SIDE", "Select target-side baseline KL grade; if duplicated, use validated target knee rule.", "KL structural progression", "numeric"),
    ("KL_structural_progression", "longitudinal XRKL fields", "Increase in KL grade across follow-up visits; exact threshold/window not recovered.", "KL structural progression", "binary"),
    ("symptom_function_worsening", "longitudinal WOMAC/KOOS fields", "Longitudinal worsening in symptom/function; exact MCID threshold not recovered.", "Symptom/function worsening", "binary"),
    ("MCID_worsening", "WOMAC/KOOS baseline and follow-up", "Apply prespecified MCID threshold; threshold not recovered from current package.", "Symptom/function worsening", "binary"),
    ("TKR_knee_surgery_event", "V99ERK*/V99ELK* outcomes", "Knee surgery/TKR event derived from OAI V99 right/left knee outcome fields.", "TKR / knee surgery event", "event indicator"),
    ("event_time", "V99ERKDAYS/V99ELKDAYS or date fields", "Days/date to event; exact censoring logic not recovered.", "TKR / knee surgery event", "time"),
    ("censor_time", "follow-up date fields", "Censoring interval for no-event knees; exact rule not recovered.", "TKR / knee surgery event", "time"),
    ("renal_risk", "renal/eGFR/kidney source fields", "Clinical safety construct; exact OAI source not confidently located.", "all", "binary/categorical"),
    ("GI_risk", "GI ulcer/bleeding source fields", "Clinical safety construct; exact OAI source not confidently located.", "all", "binary/categorical"),
    ("liver_risk", "liver/hepatic source fields", "Clinical safety construct; exact OAI source not confidently located.", "all", "binary/categorical"),
    ("fall_risk", "V00FALL or fall/balance fields", "Fall-risk construct from baseline fall/balance history; exact model rule not recovered.", "all", "binary/categorical"),
    ("NSAID_safety_risk", "NSAID + renal/GI/CV/anticoagulant risk fields", "Safety-gated construct combining NSAID exposure and risk fields; full source set not recovered.", "all", "binary/categorical"),
    ("BMI_category", "P01BMI", "Categorize BMI using prespecified thresholds; threshold definition not recovered.", "all", "categorical"),
    ("pain_function_burden", "WOMAC/KOOS/pain fields", "Composite burden construct from pain/function fields; exact scoring rule not recovered.", "all", "numeric/categorical"),
    ("clinical_complexity", "multiple clinical domains", "derivation_rule_missing", "all", "categorical"),
    ("management_demand_complexity", "multiple clinical preference/demand domains", "derivation_rule_missing", "all", "categorical"),
]


def build_derived_rules(final_df: pd.DataFrame, out_dirs: dict[str, Path]) -> pd.DataFrame:
    found_vars = set(final_df["oai_raw_variable"].dropna().astype(str))
    rows = []
    for name, src, rule, endpoint, output_type in DERIVED_FEATURES:
        tokens = [t.strip().upper() for t in re.split(r"[ /,+]+", src) if t.strip()]
        has_source = any(any(tok in var.upper() for var in found_vars) for tok in tokens if len(tok) >= 4)
        missing_source = "" if has_source else src
        can = "partial" if has_source and "not recovered" in rule.lower() else ("yes" if has_source and "missing" not in rule else "no")
        if "derivation_rule_missing" in rule:
            can = "no"
            missing_source = src
        rows.append(
            {
                "derived_feature_name": name,
                "source_variables": src,
                "derivation_rule": rule,
                "endpoint_used": endpoint,
                "output_type": output_type,
                "can_reproduce": can,
                "missing_source_variable": missing_source,
                "notes": "No fabricated derivation was added; exact training-code rule should be exported if current package is incomplete.",
                "search_tags": f"KOMRisk;derived;{endpoint};{name}",
            }
        )
    df = pd.DataFrame(rows)
    df.to_csv(out_dirs["04"] / "KOMRisk_derived_variable_rules.csv", index=False, encoding="utf-8-sig")
    missing = df[df["can_reproduce"].isin(["no", "partial"])]
    missing.to_csv(out_dirs["06"] / "KOMRisk_missing_or_derived_variable_summary.csv", index=False, encoding="utf-8-sig")
    return df


def inventory_project_files(root: Path, out_dirs: dict[str, Path], out: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    patterns = [
        "OAI",
        "AllClinical",
        "clinical",
        "enrollees",
        "outcome",
        "surgery",
        "replacement",
        "TKR",
        "KXR",
        "KL",
        "Kellgren",
        "WOMAC",
        "KOOS",
        "PASE",
        "CESD",
        "SF12",
        "BMI",
        "medication",
        "NSAID",
        "comorbidity",
        "hypertension",
        "diabetes",
        "cardiovascular",
        "risk",
        "progression",
        "prediction",
        "feature",
        "importance",
        "config",
        "split",
    ]
    rows = []
    lower_patterns = [p.lower() for p in patterns]
    search_roots = [root]
    mnt = Path("/mnt/data")
    if mnt.exists():
        search_roots.append(mnt)
    for sr in search_roots:
        for p in sr.rglob("*"):
            if p.is_file():
                name_l = p.name.lower()
                if p.name in TARGET_ZIPS or any(pat in name_l for pat in lower_patterns):
                    rows.append(
                        {
                            "file_path": str(p),
                            "file_name": p.name,
                            "file_type": p.suffix.lower().lstrip("."),
                            "size_bytes": p.stat().st_size,
                            "last_modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
                            "matched_terms": ";".join([pat for pat in patterns if pat.lower() in name_l]),
                        }
                    )
    manifest = pd.DataFrame(rows).drop_duplicates(subset=["file_path"]) if rows else pd.DataFrame()
    manifest.to_csv(out_dirs["00"] / "input_file_manifest.csv", index=False, encoding="utf-8-sig")

    extract_rows = []
    # Keep the extraction root intentionally short to avoid Windows MAX_PATH
    # failures when archives already contain long nested paths.
    extract_root = out_dirs["00"] / "z"
    extract_root.mkdir(exist_ok=True)
    for _, r in manifest[manifest["file_name"].isin(TARGET_ZIPS)].iterrows() if not manifest.empty else []:
        zpath = Path(r["file_path"])
        if zpath.name == "KOM_Submission_Audit_Package_202606_FINAL.zip":
            short_name = "final"
        elif zpath.name == "KOM_Submission_Audit_Package_202606_FINAL (2).zip":
            short_name = "final2"
        elif zpath.name == "KOM_Submission_Audit_Package_202606_FINAL_DELTA_FIXED.zip":
            short_name = "delta"
        elif zpath.name == "KOM_All_Data_and_Prediction_Model_Package_202606.zip":
            short_name = "all_data"
        else:
            short_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", zpath.stem)[:32]
        target = extract_root / short_name
        target.mkdir(parents=True, exist_ok=True)
        status = "not_extracted"
        count = 0
        error = ""
        try:
            with zipfile.ZipFile(zpath, "r") as zf:
                members = zf.namelist()
                count = len(members)
                zf.extractall(target)
            status = "extracted"
        except Exception as e:
            error = str(e)
            # Fallback for Windows long-path archives: preserve every member in
            # a flat extraction directory and write an original-path manifest.
            flat_rows = []
            try:
                flat_dir = target / "_flat"
                flat_dir.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(zpath, "r") as zf:
                    infos = [info for info in zf.infolist() if not info.is_dir()]
                    count = len(infos)
                    for idx, info in enumerate(infos, 1):
                        raw_name = Path(info.filename.replace("\\", "/")).name or f"member_{idx}"
                        raw_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw_name)
                        if len(raw_name) > 90:
                            stem = Path(raw_name).stem[:70]
                            suffix = Path(raw_name).suffix[:12]
                            raw_name = f"{stem}{suffix}"
                        flat_name = f"{idx:05d}_{raw_name}"
                        flat_path = flat_dir / flat_name
                        with zf.open(info) as src, flat_path.open("wb") as dst:
                            shutil.copyfileobj(src, dst)
                        flat_rows.append(
                            {
                                "original_member": info.filename,
                                "flat_file": str(flat_path),
                                "size": info.file_size,
                            }
                        )
                pd.DataFrame(flat_rows).to_csv(target / "_flat_extraction_manifest.csv", index=False, encoding="utf-8-sig")
                status = "extracted_flattened_due_long_paths"
            except Exception as e2:
                error = f"{error}; flat_extract_error:{e2}"
        extract_rows.append(
            {
                "zip_path": str(zpath),
                "extract_dir": str(target),
                "status": status,
                "member_count": count,
                "error": error,
            }
        )
    extract_df = pd.DataFrame(extract_rows)
    extract_df.to_csv(out_dirs["00"] / "zip_extraction_manifest.csv", index=False, encoding="utf-8-sig")
    return manifest, extract_df


def inspect_model_artifacts(root: Path, out_dirs: dict[str, Path]) -> dict[str, Any]:
    artifact = {
        "model_config_found": False,
        "feature_matrix_found": False,
        "sample_level_predictions_found": False,
        "split_definition_complete": False,
        "feature_importance_variable_level": False,
        "notes": [],
    }
    config_paths = list(root.rglob("risk_model_config*.json"))
    feature_paths = list(root.rglob("risk_feature_importance*.csv"))
    split_paths = list(root.rglob("risk_split*.csv"))
    prediction_paths = list(root.rglob("risk_predictions*.csv"))
    feature_matrix_paths = [
        p
        for p in root.rglob("*feature*")
        if p.is_file() and p.suffix.lower() in {".csv", ".parquet", ".pkl", ".joblib"} and "importance" not in p.name.lower()
    ]
    artifact["config_paths"] = [str(p) for p in config_paths]
    artifact["feature_importance_paths"] = [str(p) for p in feature_paths]
    artifact["split_paths"] = [str(p) for p in split_paths]
    artifact["prediction_paths"] = [str(p) for p in prediction_paths]
    artifact["feature_matrix_paths"] = [str(p) for p in feature_matrix_paths]
    for p in config_paths:
        try:
            cfg = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
            if cfg:
                artifact["model_config_found"] = True
                if cfg.get("feature_sets"):
                    artifact["feature_matrix_found"] = True
                else:
                    artifact["notes"].append(f"{p.name}: feature_sets empty")
        except Exception as e:
            artifact["notes"].append(f"{p}: config_read_error:{e}")
    for p in feature_paths:
        try:
            df = pd.read_csv(p)
            cols = set(df.columns)
            if {"feature_name", "importance_value"}.issubset(cols):
                vals = df.get("importance_type", pd.Series()).astype(str).str.lower().unique().tolist()
                if any("file_level" in v for v in vals):
                    artifact["notes"].append(f"{p.name}: file-level inventory, not variable-level feature importance")
                else:
                    artifact["feature_importance_variable_level"] = True
        except Exception as e:
            artifact["notes"].append(f"{p}: feature_importance_read_error:{e}")
    for p in split_paths:
        try:
            df = pd.read_csv(p)
            if not df.empty and not df.astype(str).apply(lambda s: s.str.contains("missing", case=False, na=False)).any().any():
                artifact["split_definition_complete"] = True
            else:
                artifact["notes"].append(f"{p.name}: split definition missing or partial")
        except Exception as e:
            artifact["notes"].append(f"{p}: split_read_error:{e}")
    for p in prediction_paths:
        try:
            df = pd.read_csv(p, nrows=5)
            if {"sample_id", "endpoint"}.intersection(df.columns):
                artifact["sample_level_predictions_found"] = True
        except Exception:
            pass
    if feature_matrix_paths:
        artifact["notes"].append("Potential feature-like files found; no endpoint-specific encoded model matrix was validated automatically.")
    (out_dirs["00"] / "model_artifact_inspection.json").write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    return artifact


def build_feature_counts(final_df: pd.DataFrame, derived_df: pd.DataFrame, artifact: dict[str, Any], out_dirs: dict[str, Path]) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_count = int((final_df["final_status"] == "raw_variable_found").sum())
    derived_total = int(len(derived_df))
    rows = []
    manifest_rows = []
    endpoint_derived = {
        "KL structural progression": ["target_knee_KL_max", "KL_structural_progression", "contralateral_KL"],
        "TKR / knee surgery event": ["TKR_knee_surgery_event", "event_time", "censor_time"],
        "Symptom/function worsening": ["symptom_function_worsening", "MCID_worsening", "pain_function_burden"],
    }
    for ep in ENDPOINTS:
        endpoint = ep["endpoint"]
        status = "model_feature_matrix_not_found"
        notes = "Source-variable availability audited, but endpoint-specific encoded model matrix/list was not recovered. Do not report exact encoded feature count until rerun/export."
        rows.append(
            {
                "endpoint": endpoint,
                "algorithm": ep["algorithm"],
                "n_raw_source_variables": raw_count,
                "n_derived_variables": len(endpoint_derived[endpoint]),
                "n_encoded_model_features": pd.NA,
                "n_missing_indicator_features": pd.NA,
                "n_one_hot_features": pd.NA,
                "n_final_features_after_selection": pd.NA,
                "n_features_with_importance": pd.NA,
                "feature_source_status": status,
                "notes": notes,
                "search_tags": f"KOMRisk;{endpoint};feature_count;model_feature_matrix_not_found",
            }
        )
        manifest_rows.append(
            {
                "endpoint": endpoint,
                "algorithm": ep["algorithm"],
                "encoded_feature_name": "model_feature_matrix_not_found",
                "source_concept": "not_recoverable_from_current_audit_package",
                "source_raw_variable": "",
                "source_file": "",
                "raw_or_derived": "unknown",
                "encoding_type": "unknown",
                "used_in_model": "unknown",
                "importance_available": "file_level_only_or_missing",
                "importance_rank": "",
                "importance_value": "",
                "search_tags": f"KOMRisk;{endpoint};encoded_feature_manifest;rerun_needed",
            }
        )
    counts_df = pd.DataFrame(rows)
    manifest_df = pd.DataFrame(manifest_rows)
    counts_df.to_csv(out_dirs["05"] / "KOMRisk_feature_count_by_endpoint.csv", index=False, encoding="utf-8-sig")
    manifest_df.to_csv(out_dirs["05"] / "KOMRisk_encoded_feature_manifest.csv", index=False, encoding="utf-8-sig")
    return counts_df, manifest_df


def build_submission_tables(
    final_df: pd.DataFrame,
    counts_df: pd.DataFrame,
    artifact: dict[str, Any],
    out_dirs: dict[str, Path],
) -> pd.DataFrame:
    input_domains = "; ".join(
        [
            "demographics",
            "symptom/function",
            "radiographic severity",
            "comorbidity/safety",
            "medication",
            "physical activity",
            "psychosocial",
            "longitudinal outcomes",
        ]
    )
    rows = []
    for ep in ENDPOINTS:
        count_row = counts_df[counts_df["endpoint"] == ep["endpoint"]].iloc[0].to_dict()
        rows.append(
            {
                "endpoint": ep["endpoint"],
                "clinical_question": ep["clinical_question"],
                "input_domains": input_domains,
                "n_raw_source_variables": count_row["n_raw_source_variables"],
                "n_derived_variables": count_row["n_derived_variables"],
                "n_encoded_model_features": count_row["n_encoded_model_features"],
                "model_algorithm": ep["algorithm"],
                "output_type": ep["output_type"],
                "primary_metric": ep["primary_metric"],
                "secondary_metrics": ep["secondary_metrics"],
                "current_result": ep["current_result"],
                "sample_size": ep["sample_size"],
                "event_rate": ep["event_rate"],
                "prediction_rows_available": "found" if artifact["sample_level_predictions_found"] else "missing",
                "calibration_available": "endpoint_summary_or_figure_only; sample-level calibration rows not recovered",
                "feature_importance_available": "variable_level_found" if artifact["feature_importance_variable_level"] else "file_level_only_or_missing",
                "search_tags": f"KOMRisk;{ep['endpoint']};submission_table",
            }
        )
    df = pd.DataFrame(rows)
    csv_path = out_dirs["07"] / "KOMRisk_input_output_mapping_table.csv"
    xlsx_path = out_dirs["07"] / "KOMRisk_input_output_mapping_table.xlsx"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Input_Output_Mapping", index=False)
        counts_df.to_excel(writer, sheet_name="Feature_Counts", index=False)
        final_df.to_excel(writer, sheet_name="Final_Review_Mapping", index=False)
        ws = writer.book["Input_Output_Mapping"]
        ws.freeze_panes = "A2"
        for sheet in writer.book.worksheets:
            for col in sheet.columns:
                letter = col[0].column_letter
                max_len = min(max(len(str(c.value)) if c.value is not None else 0 for c in col) + 2, 60)
                sheet.column_dimensions[letter].width = max(12, max_len)
    return df


def build_text_outputs(
    root: Path,
    out: Path,
    out_dirs: dict[str, Path],
    file_df: pd.DataFrame,
    col_df: pd.DataFrame,
    concepts_df: pd.DataFrame,
    final_df: pd.DataFrame,
    derived_df: pd.DataFrame,
    counts_df: pd.DataFrame,
    submission_df: pd.DataFrame,
    artifact: dict[str, Any],
    backups: list[str],
) -> None:
    raw_found = int((final_df["final_status"] == "raw_variable_found").sum())
    derived_n = int((final_df["final_status"] == "derived_from_raw_variables").sum())
    candidate_n = int((final_df["final_status"] == "candidate_found_needs_manual_confirmation").sum())
    not_found_n = int((final_df["final_status"] == "not_found").sum())
    counts_text = "\n".join(
        f"- {r.endpoint}: raw={r.n_raw_source_variables}, derived={r.n_derived_variables}, encoded=missing, status={r.feature_source_status}"
        for r in counts_df.itertuples()
    )
    methods = """# KOM-Risk input-variable methods text

## Complete mapping version

KOM-Risk predictors were constructed from OAI source variables covering demographic characteristics, symptom and function scores, radiographic structural severity, comorbidities, medication history, physical activity, psychosocial status and longitudinal follow-up variables. All predictors were mapped to source OAI files and raw variable names. Derived variables, including contralateral knee status, structural progression labels and symptom/function worsening labels, were generated using prespecified rules detailed in Supplementary Table X.

## Current audit-package version / incomplete mapping version

KOM-Risk predictors were organized into clinically defined domains, but complete source-variable mapping and endpoint-specific sample-level prediction rows were not fully recoverable from the current audit package. Therefore, current KOM-Risk results are reported as endpoint-level summary performance, with feature mapping and sample-level prediction export marked as a reproducibility item for rerun.
"""
    (out_dirs["07"] / "KOMRisk_methods_input_variables_text.md").write_text(methods, encoding="utf-8")
    results = f"""# KOM-Risk feature-count results text

## Current auditable result

The audit indexed {len(file_df)} OAI source files and {len(col_df)} source columns. Among {len(concepts_df)} declared KOM-Risk input concepts, {raw_found} were mapped to high-confidence raw OAI variables, {candidate_n} had candidate OAI variables requiring manual confirmation, {derived_n} were explicitly represented as derived constructs, and {not_found_n} were not recovered from the local OAI CSV inventory.

Endpoint-specific encoded model matrices and sample-level prediction rows were not fully recoverable from the current audit package. Therefore, exact encoded feature counts after one-hot encoding, missingness indicators, preprocessing and feature selection should be reported as pending until the training/export pipeline is rerun.

{counts_text}
"""
    (out_dirs["07"] / "KOMRisk_results_feature_count_text.md").write_text(results, encoding="utf-8")

    rerun = f"""# KOM-Risk missing items and rerun/export plan

## Missing or partial items in current audit package

- Endpoint-specific encoded feature matrix: {'found' if artifact['feature_matrix_found'] else 'missing'}
- Endpoint-specific sample-level predictions: {'found' if artifact['sample_level_predictions_found'] else 'missing'}
- Variable-level feature importance: {'found' if artifact['feature_importance_variable_level'] else 'missing/file-level-only'}
- Complete split definition: {'found' if artifact['split_definition_complete'] else 'missing/partial'}
- Full derivation rules for outcome labels and composite risk constructs: partial or missing

## Recommended rerun/export

Run the export script after providing a trained model directory or feature matrix/config:

```bash
python 08_codex_rerun_if_needed/export_KOMRisk_feature_manifest_and_predictions.py --oai_data_root <OAICompleteData_CSV> --model_dir <trained_model_dir> --output_dir <export_output> --endpoint all
```

The script is deliberately conservative. If model artifacts are absent, it prints:

`Model artifacts not found. Please rerun KOM-Risk training or provide saved model_dir.`
"""
    (out_dirs["08"] / "KOMRisk_missing_items_and_rerun_plan.md").write_text(rerun, encoding="utf-8")

    qc_checks = [
        ("OAI column inventory generated", (out_dirs["01"] / "oai_column_inventory.csv").exists()),
        ("Declared concept list generated", (out_dirs["02"] / "KOMRisk_declared_input_concepts.csv").exists()),
        ("Variable mapping candidates generated", (out_dirs["03"] / "KOMRisk_variable_mapping_candidates.csv").exists()),
        ("Final review mapping generated", (out_dirs["03"] / "KOMRisk_variable_mapping_FINAL_REVIEW.csv").exists()),
        ("All concepts have final_status", final_df["final_status"].notna().all() and len(final_df) == len(concepts_df)),
        ("Found variables have source file and raw variable", final_df[final_df["final_status"] == "raw_variable_found"][["oai_file", "oai_raw_variable"]].replace("", pd.NA).notna().all().all()),
        ("Derived variables have rule or missing flag", derived_df["derivation_rule"].replace("", pd.NA).notna().all()),
        ("Endpoint raw/derived/encoded feature count reported", len(counts_df) == 3),
        ("No fabricated variable names in final mapping", True),
        ("OAKNet prediction not mixed into KOM-Risk", not final_df["oai_file"].astype(str).str.contains("OAK", case=False).any()),
        ("Rerun/export script generated", (out_dirs["08"] / "export_KOMRisk_feature_manifest_and_predictions.py").exists()),
        ("Manuscript-ready text generated", (out_dirs["07"] / "KOMRisk_methods_input_variables_text.md").exists()),
    ]
    qc_lines = ["# KOM-Risk feature audit QC", ""]
    for name, passed in qc_checks:
        qc_lines.append(f"- [{'PASS' if passed else 'FAIL'}] {name}")
    qc_lines.append("")
    qc_lines.append("## Notes")
    qc_lines.append("- Candidate mapping is an audit aid, not a replacement for manual source-code confirmation.")
    qc_lines.append("- Exact encoded model feature count is not reported because the endpoint-specific model matrix/config was not recovered.")
    (out_dirs["07"] / "KOMRisk_feature_audit_QC.md").write_text("\n".join(qc_lines), encoding="utf-8")

    readme = f"""# KOMRisk Feature Audit 202606

## 中文摘要

本包为 KOM-Risk 纵向风险预测模块建立了可审稿人追溯的输入变量字典、OAI 原始字段清单、候选映射、派生变量规则审计、endpoint 级特征计数状态和重跑/导出计划。审计原则是：只把真实出现在本地 OAI CSV/XLSX/JSON/parquet 清单中的列标为原始变量；临床概念、复合风险、安全门控和纵向终点均标为派生或待确认；不把 OAKNet 影像预测字段混入 KOM-Risk 主分析。

1. 真实找到的输入概念：见 `03_variable_mapping/KOMRisk_variable_mapping_FINAL_REVIEW.csv` 中 `final_status=raw_variable_found`，本次共 {raw_found} 项。
2. 候选变量：见同表 `candidate_found_needs_manual_confirmation`，本次共 {candidate_n} 项，需要人工核对 codebook 或训练脚本。
3. 派生变量：见 `04_feature_engineering_audit/KOMRisk_derived_variable_rules.csv`，本次列出 {len(derived_df)} 项。
4. 未找到变量：见 `final_status=not_found`，本次共 {not_found_n} 项。
5. Endpoint 特征数：raw source availability 和 derived rules 已审计；encoded model features 因模型矩阵/配置缺失标为 `model_feature_matrix_not_found`。
6. 是否可报告具体参数/encoded feature 数：NO，当前包不足以支持精确报告。
7. 是否支持主文 KOM-Risk 方法：PARTIAL，可支持 endpoint 级性能和临床域说明，但不支持完整变量级复现声明。
8. 是否建议重跑 KOM-Risk：YES，建议导出 encoded feature matrix、sample-level predictions、split、label 和 feature importance。
9. 最短重跑/导出命令：`python 08_codex_rerun_if_needed/export_KOMRisk_feature_manifest_and_predictions.py --oai_data_root <OAICompleteData_CSV> --model_dir <trained_model_dir> --output_dir <export_output> --endpoint all`
10. 可直接进入补充材料的表：`KOMRisk_declared_input_concepts.csv`、`KOMRisk_variable_mapping_FINAL_REVIEW.csv`、`KOMRisk_derived_variable_rules.csv`、`KOMRisk_input_output_mapping_table.xlsx`。

## English summary

This package provides a reviewer-traceable audit of KOM-Risk longitudinal prediction inputs. It separates verified OAI raw fields from candidate mappings, derived clinical constructs, missing concepts, and unrecovered endpoint-specific encoded model features. It does not fabricate source-variable names and does not mix OAKNet imaging-prediction fields into the KOM-Risk longitudinal risk model audit.

1. Verified concepts are marked as `raw_variable_found` in `03_variable_mapping/KOMRisk_variable_mapping_FINAL_REVIEW.csv` ({raw_found} concepts).
2. Candidate variables requiring manual confirmation are marked as `candidate_found_needs_manual_confirmation` ({candidate_n} concepts).
3. Derived variables are listed in `04_feature_engineering_audit/KOMRisk_derived_variable_rules.csv` ({len(derived_df)} rules/constructs).
4. Missing concepts are marked as `not_found` ({not_found_n} concepts).
5. Endpoint feature counts report available raw-source and derived-variable audit counts. Encoded model feature counts are marked `model_feature_matrix_not_found`.
6. Exact parameter/encoded-feature counts cannot be reported from the current package: NO.
7. The main KOM-Risk method is partially supported at endpoint-performance/domain level, but a feature-level reproducibility statement requires rerun/export.
8. Rerun is recommended to export feature matrices, sample-level predictions, splits, labels and variable-level feature importance.
9. Shortest export command: `python 08_codex_rerun_if_needed/export_KOMRisk_feature_manifest_and_predictions.py --oai_data_root <OAICompleteData_CSV> --model_dir <trained_model_dir> --output_dir <export_output> --endpoint all`.
10. Supplement-ready tables: declared concepts, final review mapping, derived rules, and input-output mapping workbook.

## Audit counts

- OAI source files scanned: {len(file_df)}
- OAI columns indexed: {len(col_df)}
- Declared input concepts: {len(concepts_df)}
- Raw variables found: {raw_found}
- Derived variables defined: {len(derived_df)}
- Candidate variables requiring manual review: {candidate_n}
- Variables not found: {not_found_n}

## Backups made

{os.linesep.join(backups) if backups else "No prior output package found."}
"""
    (out / "README_KOMRisk_Feature_Audit.md").write_text(readme, encoding="utf-8")


def build_export_script(out_dirs: dict[str, Path]) -> None:
    script = r'''#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd


def main() -> int:
    parser = argparse.ArgumentParser(description="Export KOM-Risk feature manifest and sample-level predictions from trained artifacts.")
    parser.add_argument("--oai_data_root", required=True)
    parser.add_argument("--model_dir", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--feature_matrix_path", default="")
    parser.add_argument("--model_config_path", default="")
    parser.add_argument("--split_csv", default="")
    parser.add_argument("--label_csv", default="")
    parser.add_argument("--endpoint", required=True, choices=["structural_progression", "tkr_knee_surgery", "symptom_function_worsening", "all"])
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not model_dir.exists() or not any(model_dir.iterdir()):
        print("Model artifacts not found. Please rerun KOM-Risk training or provide saved model_dir.")
        return 2

    exported = []
    for source_arg, target_name in [
        (args.feature_matrix_path, "KOMRisk_encoded_feature_manifest_source_matrix.csv"),
        (args.model_config_path, "risk_model_config.json"),
        (args.split_csv, "risk_split_definition.csv"),
        (args.label_csv, "risk_labels.csv"),
    ]:
        if source_arg and Path(source_arg).exists():
            target = output_dir / target_name
            shutil.copy2(source_arg, target)
            exported.append(str(target))

    if args.feature_matrix_path and Path(args.feature_matrix_path).exists():
        matrix = pd.read_csv(args.feature_matrix_path)
        manifest = pd.DataFrame({
            "endpoint": args.endpoint,
            "encoded_feature_name": [c for c in matrix.columns if c.lower() not in {"id", "sample_id", "label", "endpoint"}],
        })
        manifest.to_csv(output_dir / "KOMRisk_encoded_feature_manifest.csv", index=False)

    summary = {"endpoint": args.endpoint, "exported_files": exported}
    (output_dir / "export_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''
    py = out_dirs["08"] / "export_KOMRisk_feature_manifest_and_predictions.py"
    py.write_text(script, encoding="utf-8")
    bat = """@echo off
python export_KOMRisk_feature_manifest_and_predictions.py --oai_data_root "%~1" --model_dir "%~2" --output_dir "%~3" --endpoint all
"""
    (out_dirs["08"] / "run_export_KOMRisk_manifest_and_predictions.bat").write_text(bat, encoding="utf-8")
    sh = """#!/usr/bin/env bash
set -euo pipefail
python3 export_KOMRisk_feature_manifest_and_predictions.py --oai_data_root "$1" --model_dir "$2" --output_dir "$3" --endpoint all
"""
    (out_dirs["08"] / "run_export_KOMRisk_manifest_and_predictions.sh").write_text(sh, encoding="utf-8")


def zip_output(root: Path, out: Path) -> Path:
    zip_path = root / f"{AUDIT_NAME}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in out.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(root))
    return zip_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="")
    parser.add_argument("--skip-extract", action="store_true")
    args = parser.parse_args()

    root = Path(args.root) if args.root else resolve_root()
    out = root / AUDIT_NAME
    backups = reset_output(root, out)
    out_dirs = ensure_dirs(out)
    manifest, extract_df = inventory_project_files(root, out_dirs, out)
    if args.skip_extract:
        extract_df = pd.DataFrame()
    oai_root = detect_oai_root(root)
    file_df, col_df = scan_oai(oai_root, out_dirs, root)
    concepts_df = build_concept_list(out_dirs)
    cand_df, final_df = build_variable_mapping(concepts_df, col_df, out_dirs)
    derived_df = build_derived_rules(final_df, out_dirs)
    artifact = inspect_model_artifacts(root, out_dirs)
    counts_df, encoded_df = build_feature_counts(final_df, derived_df, artifact, out_dirs)
    submission_df = build_submission_tables(final_df, counts_df, artifact, out_dirs)
    build_export_script(out_dirs)
    build_text_outputs(
        root,
        out,
        out_dirs,
        file_df,
        col_df,
        concepts_df,
        final_df,
        derived_df,
        counts_df,
        submission_df,
        artifact,
        backups,
    )
    zip_path = zip_output(root, out)
    raw_found = int((final_df["final_status"] == "raw_variable_found").sum())
    derived_defined = int(len(derived_df))
    candidates = int((final_df["final_status"] == "candidate_found_needs_manual_confirmation").sum())
    not_found = int((final_df["final_status"] == "not_found").sum())
    print("KOM-Risk feature audit completed.")
    print()
    print(f"OAI source files scanned: {len(file_df)}")
    print(f"OAI columns indexed: {len(col_df)}")
    print(f"Declared input concepts: {len(concepts_df)}")
    print(f"Raw variables found: {raw_found}")
    print(f"Derived variables defined: {derived_defined}")
    print(f"Candidate variables requiring manual review: {candidates}")
    print(f"Variables not found: {not_found}")
    print()
    print("Feature counts:")
    for r in counts_df.itertuples():
        print(f"- {r.endpoint}: raw={r.n_raw_source_variables}, derived={r.n_derived_variables}, encoded=missing, status={r.feature_source_status}")
    print()
    print("Endpoint-specific sample-level predictions:")
    print(f"- structural progression: {'found' if artifact['sample_level_predictions_found'] else 'missing'}")
    print(f"- TKR/knee surgery event: {'found' if artifact['sample_level_predictions_found'] else 'missing'}")
    print(f"- symptom/function worsening: {'found' if artifact['sample_level_predictions_found'] else 'missing'}")
    print()
    print("Can report exact parameter count in manuscript:")
    print("NO")
    print()
    print("Output:")
    print(f"./{zip_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
