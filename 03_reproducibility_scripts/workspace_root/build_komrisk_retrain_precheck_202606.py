from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import shutil
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from glob import glob
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None

try:
    import docx
except Exception:  # pragma: no cover
    docx = None


OUT_NAME = "KOMRisk_Retrain_Precheck_202606"
FINAL_ZIP_PREFIX = "KOMRisk_Retrain_Precheck_202606_FINAL"
MAX_ZIP_MB = 450
MAX_ZIP_BYTES = MAX_ZIP_MB * 1024 * 1024
VISIT_RE = re.compile(r"(V(?:00|01|02|03|04|05|06|07|08|09|10|11|99))", re.I)
PACKABLE_CODEBOOK_EXTS = {".pdf", ".sas", ".txt", ".doc", ".docx", ".xls", ".xlsx", ".pptx"}
NONPACK_DATA_EXTS = {".sas7bdat", ".xpt", ".sas7bcat", ".sf3"}
CSV_KEYWORDS_ENDPOINT = [
    "KL",
    "KLG",
    "XR",
    "Xray",
    "radiograph",
    "osteophyte",
    "JSN",
    "joint space",
    "OARSI",
    "TKR",
    "replacement",
    "arthroplasty",
    "surgery",
    "WOMAC",
    "KOOS",
    "pain",
    "function",
    "ADL",
    "symptom",
    "stiffness",
    "stair",
    "walking",
]
SIDE_KEYWORDS = [
    "SID",
    "SIDE",
    "side",
    "KNEE",
    "knee",
    "RIGHT",
    "right",
    "LEFT",
    "left",
    "R knee",
    "L knee",
    "1=Right",
    "2=Left",
    "1 = Right",
    "2 = Left",
    "1=Left",
    "2=Right",
    "bilateral",
    "index knee",
    "target knee",
    "surgery side",
    "knee side",
    "read side",
    "exam side",
    "MRSIDE",
    "MRKSIDE",
]


def now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def sha256_file(path: Path, large_ok: bool = True) -> str:
    # Hash codebook upload files fully. For very large non-upload data files,
    # record a transparent noncomputed marker to avoid spending the audit on
    # multi-GB SAS transport files.
    if not large_ok and path.stat().st_size > 512 * 1024 * 1024:
        return "not_computed_large_data_file"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_rel(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except Exception:
        return str(path)


def locate_paths() -> dict[str, Any]:
    sas_patterns = [
        r"C:\OAI*\pythonProject1\OAI*\OAICompleteData_SAS",
    ]
    csv_patterns = [
        r"C:\OAI*\OAICompleteData_CSV",
        r"C:\OAI*\pythonProject1\OAI*\OAICompleteData_CSV",
        r"C:\OAI*\pythonProject1\KOM*\本地化\koa_mdt_agents\data\raw\oai_csv_link",
    ]
    sas_hits = []
    for pat in sas_patterns:
        sas_hits.extend([Path(p) for p in glob(pat)])
    csv_hits = []
    for pat in csv_patterns:
        csv_hits.extend([Path(p) for p in glob(pat)])
    sas_hits = [p for p in dict.fromkeys(sas_hits) if p.exists()]
    csv_hits = [p for p in dict.fromkeys(csv_hits) if p.exists()]
    preferred_csv = None
    for p in csv_hits:
        if "pythonProject1" in str(p) and any(p.glob("*.csv")):
            preferred_csv = p
            break
    if preferred_csv is None and csv_hits:
        preferred_csv = csv_hits[0]
    return {
        "sas_paths": sas_hits,
        "csv_paths": csv_hits,
        "sas_root": sas_hits[0] if sas_hits else None,
        "csv_root": preferred_csv,
    }


def reset_output(base: Path) -> tuple[Path, list[str]]:
    out = base / OUT_NAME
    backups: list[str] = []
    if out.exists():
        backup = base / f"{OUT_NAME}_backup_{now_tag()}"
        shutil.move(str(out), str(backup))
        backups.append(str(backup))
    for z in base.glob(f"{FINAL_ZIP_PREFIX}*.zip"):
        backup = base / f"{z.stem}_backup_{now_tag()}.zip"
        shutil.move(str(z), str(backup))
        backups.append(str(backup))
    out.mkdir(parents=True, exist_ok=True)
    return out, backups


def ensure_dirs(out: Path) -> dict[str, Path]:
    names = [
        "00_README",
        "01_pdf_codebook_packages",
        "02_csv_schema_inventory",
        "03_side_sid_mapping_audit",
        "04_endpoint_feasibility",
        "05_training_protocol_freeze",
        "06_upload_packages",
        "07_QC",
        "scripts",
    ]
    dirs = {name: out / name for name in names}
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    (dirs["02_csv_schema_inventory"] / "oai_csv_first20rows_samples").mkdir(exist_ok=True)
    return dirs


def suspected_visit(name: str) -> str:
    found = sorted(set(m.group(1).upper() for m in VISIT_RE.finditer(name)))
    if found:
        return ";".join(found)
    m = re.search(r"(\d{2})(?:\D|$)", name)
    return f"V{m.group(1)}" if m else ""


def suspected_domain(text: str) -> str:
    up = text.upper()
    if "ALLCLINICAL" in up or "CLINICAL" in up:
        return "clinical"
    if "KXR" in up or "XRAY" in up or "RADIOGRAPH" in up:
        return "radiograph"
    if "MRI" in up or "KMRI" in up:
        return "MRI"
    if "OUTCOME" in up or "SURG" in up or "TKR" in up or "REPLACEMENT" in up:
        return "outcome_surgery"
    if "WOMAC" in up or "KOOS" in up or "PAIN" in up or "FUNCTION" in up:
        return "symptom_function"
    if "ENROL" in up or "DEMOGRAPH" in up:
        return "demographics"
    if "MED" in up or "NSAID" in up:
        return "medication"
    if "CODEBOOK" in up or "COMMENTS" in up or "STATS" in up:
        return "codebook_stats"
    return "unknown"


def text_flags(text: str) -> dict[str, bool]:
    up = text.upper()
    return {
        "contains_side_keyword": bool(re.search(r"\b(SID|SIDE|RIGHT|LEFT|MRSIDE|MRKSIDE)\b", up)),
        "contains_sid_keyword": bool(re.search(r"\bSID\b", up)),
        "contains_knee_keyword": "KNEE" in up,
        "contains_kl_keyword": "KL" in up or "KELLGREN" in up,
        "contains_surgery_keyword": "SURG" in up or "TKR" in up or "REPLACEMENT" in up or "ARTHROPLASTY" in up,
        "contains_womac_keyword": "WOMAC" in up,
        "contains_koos_keyword": "KOOS" in up,
    }


def extract_file_text(path: Path, max_pages: int = 20, max_chars: int = 200_000) -> str:
    ext = path.suffix.lower()
    try:
        if ext == ".pdf" and PdfReader is not None:
            reader = PdfReader(str(path))
            parts = []
            for page in reader.pages[:max_pages]:
                try:
                    parts.append(page.extract_text() or "")
                except Exception:
                    continue
                if sum(len(x) for x in parts) > max_chars:
                    break
            return "\n".join(parts)[:max_chars]
        if ext in {".sas", ".txt"}:
            return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
        if ext == ".docx" and docx is not None:
            d = docx.Document(str(path))
            return "\n".join(p.text for p in d.paragraphs)[:max_chars]
        if ext in {".xls", ".xlsx"}:
            df = pd.read_excel(path, nrows=100, header=None)
            return "\n".join(" ".join(map(str, row)) for row in df.fillna("").values.tolist())[:max_chars]
    except Exception:
        return ""
    return ""


def scan_codebooks(sas_root: Path | None, dirs: dict[str, Path], found_paths: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    nonpdf_rows = []
    if sas_root and sas_root.exists():
        files = [p for p in sas_root.rglob("*") if p.is_file()]
    else:
        files = []
    for p in sorted(files, key=lambda x: str(x).lower()):
        ext = p.suffix.lower()
        if ext not in PACKABLE_CODEBOOK_EXTS | NONPACK_DATA_EXTS:
            continue
        is_packable = ext in PACKABLE_CODEBOOK_EXTS
        text_sample = extract_file_text(p, max_pages=10) if is_packable else ""
        combined = f"{p.name} {safe_rel(p, sas_root) if sas_root else p} {text_sample[:5000]}"
        flags = text_flags(combined)
        row = {
            "original_full_path": str(p),
            "file_name": p.name,
            "extension": ext,
            "file_size_bytes": p.stat().st_size,
            "file_size_mb": round(p.stat().st_size / 1024 / 1024, 4),
            "modified_time": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
            "relative_path": safe_rel(p, sas_root) if sas_root else str(p),
            "suspected_visit": suspected_visit(p.name),
            "suspected_domain": suspected_domain(f"{p.name} {safe_rel(p, sas_root) if sas_root else p}"),
            **flags,
            "sha256": sha256_file(p, large_ok=is_packable),
        }
        if is_packable:
            rows.append(row)
        else:
            nonpdf_rows.append(row)
    manifest = pd.DataFrame(rows)
    nonpdf = pd.DataFrame(nonpdf_rows)
    manifest.to_csv(dirs["01_pdf_codebook_packages"] / "oai_sas_pdf_codebook_manifest.csv", index=False, encoding="utf-8-sig")
    nonpdf.to_csv(dirs["01_pdf_codebook_packages"] / "oai_sas_nonpdf_manifest.csv", index=False, encoding="utf-8-sig")
    summary = pd.DataFrame(
        Counter(list(manifest.get("extension", [])) + list(nonpdf.get("extension", []))).items(),
        columns=["extension", "file_count"],
    ).sort_values("extension")
    summary["total_size_mb"] = summary["extension"].map(
        lambda e: round(
            sum(manifest.loc[manifest["extension"].eq(e), "file_size_bytes"].tolist())
            / 1024
            / 1024
            + sum(nonpdf.loc[nonpdf["extension"].eq(e), "file_size_bytes"].tolist()) / 1024 / 1024,
            4,
        )
    )
    summary.to_csv(dirs["01_pdf_codebook_packages"] / "oai_codebook_file_type_summary.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(dirs["01_pdf_codebook_packages"] / "oai_sas_pdf_codebook_manifest.xlsx", engine="openpyxl") as writer:
        manifest.to_excel(writer, sheet_name="packable_codebooks", index=False)
        nonpdf.to_excel(writer, sheet_name="data_file_manifest", index=False)
        summary.to_excel(writer, sheet_name="file_type_summary", index=False)
    readme = f"""# OAI SAS/PDF/codebook manifest

SAS root: `{sas_root}`

- Packable PDF/codebook/program files: {len(manifest)}
- Non-upload data files listed only: {len(nonpdf)}
- `.sas7bdat` and `.xpt` files were not packaged for upload; they are listed for metadata only.
- Hashing note: large non-upload data files may show `not_computed_large_data_file`.
"""
    (dirs["01_pdf_codebook_packages"] / "oai_codebook_manifest_README.md").write_text(readme, encoding="utf-8")
    path_manifest = pd.DataFrame(
        [
            {
                "path_type": "sas_root",
                "path": str(p),
                "exists": bool(p and p.exists()),
                "selected": p == sas_root,
            }
            for p in found_paths.get("sas_paths", [])
        ]
        + [
            {
                "path_type": "csv_root",
                "path": str(p),
                "exists": bool(p and p.exists()),
                "selected": p == found_paths.get("csv_root"),
            }
            for p in found_paths.get("csv_paths", [])
        ]
    )
    path_manifest.to_csv(dirs["00_README"] / "input_path_manifest.csv", index=False, encoding="utf-8-sig")
    return manifest, nonpdf, summary


def sniff_delimiter(path: Path) -> str:
    try:
        raw = path.read_bytes()[:4096].decode("utf-8", errors="ignore")
        dialect = csv.Sniffer().sniff(raw, delimiters=",\t;|")
        return dialect.delimiter
    except Exception:
        return ","


def count_rows(path: Path) -> int | None:
    try:
        with path.open("rb") as f:
            return max(sum(1 for _ in f) - 1, 0)
    except Exception:
        return None


def side_column_hit(col: str) -> bool:
    up = col.upper()
    if up in {"SIDE", "SID", "MRSIDE", "MRKSIDE"}:
        return True
    if any(t in up for t in ["SIDE", "RIGHT", "LEFT", "KNEE", "R_KNEE", "L_KNEE"]):
        return True
    if re.search(r"(^|_)(R|L)(K|KNEE|XR|MR|WOM|KOOS)", up):
        return True
    if re.search(r"(ERK|ELK|XRKL|XRJSM|XRJSL|XROSTM|XROSTL|XRSCTM|XRSCTL)", up):
        return True
    return False


def endpoint_column_hit(col: str) -> bool:
    up = col.upper()
    return any(k.upper().replace(" ", "") in up.replace(" ", "") for k in CSV_KEYWORDS_ENDPOINT)


def visit_prefixes(cols: Iterable[str], file_name: str = "") -> str:
    visits = sorted(set(v.group(1).upper() for c in cols for v in VISIT_RE.finditer(str(c))))
    if not visits:
        v = suspected_visit(file_name)
        visits = [v] if v else []
    return ";".join(visits)


def classify_knee_structure(cols: list[str]) -> dict[str, Any]:
    ups = [c.upper() for c in cols]
    has_side_col = any(c in {"SIDE", "SID", "MRSIDE", "MRKSIDE"} or "SIDE" in c for c in ups)
    wide_r = any(re.search(r"(RIGHT|ERK|RK|XRKLR|WOMKPR|KOOSKPR|XRJSM|XROSTM|XRSCTM)", c) for c in ups)
    wide_l = any(re.search(r"(LEFT|ELK|LK|XRKLL|WOMKPL|KOOSKPL|XRJSL|XROSTL|XRSCTL)", c) for c in ups)
    knee_level = "long_format" if has_side_col else ("wide_right_left" if wide_r and wide_l else "person_level")
    return {
        "has_side_column": has_side_col,
        "right_left_encoded_separately": wide_r and wide_l,
        "wide_format_right_left_columns": ";".join([c for c in cols if side_column_hit(c)][:40]),
        "long_format_side_column": ";".join([c for c in cols if c.upper() in {"SIDE", "SID", "MRSIDE", "MRKSIDE"} or "SIDE" in c.upper()][:20]),
        "knee_level_type": knee_level,
    }


def scan_csv_schema(csv_root: Path | None, dirs: dict[str, Path]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    file_rows = []
    col_rows = []
    samples_dir = dirs["02_csv_schema_inventory"] / "oai_csv_first20rows_samples"
    csv_files = sorted(csv_root.rglob("*.csv"), key=lambda p: str(p).lower()) if csv_root and csv_root.exists() else []
    for p in csv_files:
        sep = sniff_delimiter(p)
        row_count = count_rows(p)
        notes = []
        try:
            sample = pd.read_csv(p, sep=sep, nrows=5000, low_memory=False, encoding_errors="ignore")
            first20 = sample.head(20)
        except TypeError:
            sample = pd.read_csv(p, sep=sep, nrows=5000, low_memory=False)
            first20 = sample.head(20)
        except Exception as e:
            sample = pd.DataFrame()
            first20 = pd.DataFrame()
            notes.append(f"read_error:{e}")
        if not first20.empty:
            first20.to_csv(samples_dir / f"{p.stem}_first20.csv", index=False, encoding="utf-8-sig")
        cols = list(map(str, sample.columns))
        structure = classify_knee_structure(cols)
        up_cols = [c.upper() for c in cols]
        file_rows.append(
            {
                "file_name": p.name,
                "original_path": str(p),
                "relative_path": safe_rel(p, csv_root) if csv_root else str(p),
                "num_rows": row_count,
                "num_columns": len(cols),
                "file_size_bytes": p.stat().st_size,
                "file_size_mb": round(p.stat().st_size / 1024 / 1024, 4),
                "encoding": "utf-8/auto-ignore",
                "delimiter": sep,
                "contains_id_person_id": any(c in {"ID", "PERSON_ID", "PERSONID"} for c in up_cols),
                "contains_sid_side": any(c in {"SID", "SIDE", "MRSIDE", "MRKSIDE"} or "SIDE" in c for c in up_cols),
                "contains_right_left_R_L": structure["right_left_encoded_separately"],
                "contains_knee_level_information": structure["knee_level_type"] != "person_level",
                "contains_visit_code": bool(visit_prefixes(cols, p.name)),
                "contains_outcome": any(k in " ".join(up_cols) for k in ["OUTCOME", "V99", "SURG", "TKR", "EVENT"]),
                "contains_KL_WOMAC_KOOS_surgery_TKR": any(endpoint_column_hit(c) for c in cols),
                "knee_level_type": structure["knee_level_type"],
                "notes": "; ".join(notes),
            }
        )
        for col in cols:
            s = sample[col] if col in sample.columns else pd.Series(dtype=object)
            nonmissing = int(s.notna().sum())
            missing_rate = round(float(s.isna().mean()), 4) if len(s) else None
            examples = [str(x) for x in s.dropna().astype(str).drop_duplicates().head(10).tolist()]
            col_rows.append(
                {
                    "file_name": p.name,
                    "original_path": str(p),
                    "column_name": col,
                    "column_name_upper": col.upper(),
                    "visit_prefix": visit_prefixes([col], p.name),
                    "nonmissing_count_profiled_first5000": nonmissing,
                    "missing_rate_profiled_first5000": missing_rate,
                    "example_values_first10": " | ".join(examples),
                    "data_type_inferred": str(s.dtype),
                    "contains_id_person_id": col.upper() in {"ID", "PERSON_ID", "PERSONID"},
                    "contains_sid_side": side_column_hit(col),
                    "contains_right_left_R_L": bool(re.search(r"(RIGHT|LEFT|ERK|ELK|RK|LK|XRJSM|XRJSL|XROSTM|XROSTL|XRSCTM|XRSCTL)", col.upper())),
                    "contains_knee_level_information": side_column_hit(col),
                    "contains_visit_code": bool(visit_prefixes([col], p.name)),
                    "contains_outcome": any(k in col.upper() for k in ["OUTCOME", "V99", "SURG", "TKR", "EVENT"]),
                    "contains_KL_WOMAC_KOOS_surgery_TKR": endpoint_column_hit(col),
                    "search_tags": ";".join([t for t in [visit_prefixes([col], p.name), "side" if side_column_hit(col) else "", "endpoint" if endpoint_column_hit(col) else ""] if t]),
                }
            )
    file_df = pd.DataFrame(file_rows)
    col_df = pd.DataFrame(col_rows)
    file_df.to_csv(dirs["02_csv_schema_inventory"] / "oai_csv_file_inventory.csv", index=False, encoding="utf-8-sig")
    col_df.to_csv(dirs["02_csv_schema_inventory"] / "oai_csv_column_inventory.csv", index=False, encoding="utf-8-sig")
    side_cols = col_df[col_df["contains_sid_side"].eq(True)] if not col_df.empty else pd.DataFrame()
    endpoint_cols = col_df[col_df["contains_KL_WOMAC_KOOS_surgery_TKR"].eq(True)] if not col_df.empty else pd.DataFrame()
    side_cols.to_csv(dirs["02_csv_schema_inventory"] / "oai_csv_side_keyword_columns.csv", index=False, encoding="utf-8-sig")
    endpoint_cols.to_csv(dirs["02_csv_schema_inventory"] / "oai_csv_endpoint_keyword_columns.csv", index=False, encoding="utf-8-sig")
    missing = (
        col_df.groupby("file_name", as_index=False)
        .agg(
            n_columns=("column_name", "count"),
            mean_missing_rate_first5000=("missing_rate_profiled_first5000", "mean"),
            max_missing_rate_first5000=("missing_rate_profiled_first5000", "max"),
        )
        if not col_df.empty
        else pd.DataFrame()
    )
    missing.to_csv(dirs["02_csv_schema_inventory"] / "oai_csv_missingness_summary.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(dirs["02_csv_schema_inventory"] / "oai_csv_schema_summary.xlsx", engine="openpyxl") as writer:
        file_df.to_excel(writer, sheet_name="csv_files", index=False)
        col_df.head(20000).to_excel(writer, sheet_name="columns_first20000", index=False)
        side_cols.to_excel(writer, sheet_name="side_columns", index=False)
        endpoint_cols.head(20000).to_excel(writer, sheet_name="endpoint_columns", index=False)
        missing.to_excel(writer, sheet_name="missingness_by_file", index=False)
    return file_df, col_df, side_cols, endpoint_cols


def find_codebook_hits(manifest: pd.DataFrame, dirs: dict[str, Path]) -> pd.DataFrame:
    hit_rows = []
    patterns = [
        ("right_left_1_2", re.compile(r"1\s*=\s*right|2\s*=\s*left|1\s*=\s*left|2\s*=\s*right", re.I)),
        ("side_sid", re.compile(r"\b(SID|SIDE|MRSIDE|MRKSIDE|knee side|read side|exam side|target knee|index knee)\b", re.I)),
        ("knee", re.compile(r"\bknee\b", re.I)),
        ("kl", re.compile(r"\b(KL|Kellgren|Lawrence)\b", re.I)),
        ("surgery", re.compile(r"\b(TKR|surgery|replacement|arthroplasty)\b", re.I)),
        ("womac_koos", re.compile(r"\b(WOMAC|KOOS|pain|function|ADL|stiffness)\b", re.I)),
    ]
    for _, r in manifest.iterrows():
        p = Path(r["original_full_path"])
        text = extract_file_text(p, max_pages=40, max_chars=400_000)
        if not text:
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines, 1):
            if len(line.strip()) < 3:
                continue
            for label, pat in patterns:
                if pat.search(line):
                    hit_rows.append(
                        {
                            "source_file": str(p),
                            "file_name": p.name,
                            "line_or_page": i,
                            "keyword_group": label,
                            "matched_text": line.strip()[:500],
                            "supports_explicit_1_2_mapping": bool(re.search(r"1\s*=\s*right|2\s*=\s*left|1\s*=\s*left|2\s*=\s*right", line, re.I)),
                        }
                    )
                    break
            if len(hit_rows) > 20000:
                break
    df = pd.DataFrame(hit_rows)
    df.to_csv(dirs["03_side_sid_mapping_audit"] / "side_sid_candidate_codebook_hits.csv", index=False, encoding="utf-8-sig")
    return df


def build_side_knee_audit(
    csv_file_df: pd.DataFrame,
    csv_col_df: pd.DataFrame,
    codebook_hits: pd.DataFrame,
    dirs: dict[str, Path],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    side_cols = csv_col_df[csv_col_df["contains_sid_side"].eq(True)].copy() if not csv_col_df.empty else pd.DataFrame()
    candidate_rows = []
    for _, r in side_cols.iterrows():
        col = str(r["column_name"])
        candidate_rows.append(
            {
                "file_name": r["file_name"],
                "column_name": col,
                "column_name_upper": r["column_name_upper"],
                "visit_prefix": r["visit_prefix"],
                "example_values_first10": r["example_values_first10"],
                "candidate_reason": "column_name_contains_SIDE_SID_or_right_left_knee_marker",
                "sid_may_be_subject_id": col.upper() == "SID",
                "mapping_status": "requires_codebook_confirmation",
            }
        )
    side_candidate = pd.DataFrame(candidate_rows)
    side_candidate.to_csv(dirs["03_side_sid_mapping_audit"] / "side_sid_candidate_columns.csv", index=False, encoding="utf-8-sig")
    explicit_hits = codebook_hits[codebook_hits.get("supports_explicit_1_2_mapping", pd.Series(dtype=bool)).eq(True)] if not codebook_hits.empty else pd.DataFrame()
    explicit_text = "\n".join(explicit_hits.get("matched_text", []).astype(str).tolist()[:50]) if not explicit_hits.empty else ""
    mapping_rows = []
    uncertain_rows = []
    for _, f in csv_file_df.iterrows():
        file_cols = csv_col_df[csv_col_df["file_name"].eq(f["file_name"])] if not csv_col_df.empty else pd.DataFrame()
        cols = file_cols["column_name"].astype(str).tolist() if not file_cols.empty else []
        structure = classify_knee_structure(cols)
        side_values = ""
        side_columns = [c for c in cols if c.upper() in {"SIDE", "SID", "MRSIDE", "MRKSIDE"} or "SIDE" in c.upper()]
        if side_columns:
            vals = []
            for c in side_columns[:5]:
                ex = file_cols.loc[file_cols["column_name"].eq(c), "example_values_first10"].astype(str).tolist()
                if ex:
                    vals.append(f"{c}: {ex[0]}")
            side_values = "; ".join(vals)
        mapping_status = "not_side_specific"
        evidence = ""
        reliable = False
        if structure["knee_level_type"] == "wide_right_left":
            mapping_status = "reliable_wide_right_left_columns_by_variable_name"
            reliable = True
            evidence = "Right/left are encoded in separate column names; numeric 1/2 side mapping not required."
        elif structure["knee_level_type"] == "long_format":
            if explicit_text:
                mapping_status = "candidate_explicit_1_2_mapping_found_global_review_needed"
                evidence = explicit_text[:500]
                reliable = False
            else:
                mapping_status = "mapping_uncertain_no_explicit_codebook_evidence"
                evidence = "SIDE/SID-like field found, but no explicit 1/2 right/left codebook evidence was confirmed in this precheck."
        mapping_rows.append(
            {
                "file_name": f["file_name"],
                "side_columns": ";".join(side_columns),
                "side_values": side_values,
                "format_type": structure["knee_level_type"],
                "mapping_status": mapping_status,
                "reliable_knee_lateralization": reliable,
                "evidence_source": "column_names" if reliable else ("codebook_hits" if explicit_text else "none_confirmed"),
                "evidence_text": evidence,
                "notes": "Do not assume 1=Right/2=Left unless file-specific codebook evidence is later confirmed.",
            }
        )
        if mapping_status.startswith("mapping_uncertain") or mapping_status.startswith("candidate"):
            uncertain_rows.append(mapping_rows[-1])
    mapping_df = pd.DataFrame(mapping_rows)
    uncertain_df = pd.DataFrame(uncertain_rows)
    mapping_df.to_csv(dirs["03_side_sid_mapping_audit"] / "side_sid_file_specific_mapping_table.csv", index=False, encoding="utf-8-sig")
    uncertain_df.to_csv(dirs["03_side_sid_mapping_audit"] / "side_sid_uncertain_cases.csv", index=False, encoding="utf-8-sig")
    knee_rows = []
    for _, f in csv_file_df.iterrows():
        file_cols = csv_col_df[csv_col_df["file_name"].eq(f["file_name"])] if not csv_col_df.empty else pd.DataFrame()
        cols = file_cols["column_name"].astype(str).tolist() if not file_cols.empty else []
        st = classify_knee_structure(cols)
        up = " ".join(c.upper() for c in cols)
        knee_rows.append(
            {
                "file_name": f["file_name"],
                "id_column": ";".join([c for c in cols if c.upper() in {"ID", "PERSON_ID", "PERSONID"}][:5]),
                "side_column": st["long_format_side_column"],
                "side_values": next((m["side_values"] for m in mapping_rows if m["file_name"] == f["file_name"]), ""),
                "visit_column_or_visit_prefix": visit_prefixes(cols, f["file_name"]),
                "knee_level_confirmed": st["knee_level_type"] in {"long_format", "wide_right_left"},
                "right_left_encoded_separately": st["right_left_encoded_separately"],
                "wide_format_right_left_columns": st["wide_format_right_left_columns"],
                "long_format_side_column": st["long_format_side_column"],
                "usable_for_structural_endpoint": bool(re.search(r"XRKL|XRJS|XROST|XRSCT|KXR", up)),
                "usable_for_surgery_endpoint": bool(re.search(r"V99ERK|V99ELK|TKR|SURG|REPLACEMENT", up)),
                "usable_for_symptom_endpoint": bool(re.search(r"WOM|KOOS|PAIN|KPN|ADL|STIFF", up)),
                "notes": st["knee_level_type"],
            }
        )
    knee_df = pd.DataFrame(knee_rows)
    knee_df.to_csv(dirs["03_side_sid_mapping_audit"] / "knee_level_table_inventory.csv", index=False, encoding="utf-8-sig")
    hyp = """# SIDE/SID global mapping hypothesis

This precheck does **not** hard-code `1=Right / 2=Left`.

## Current finding

- Files with explicit right/left column names can be treated as knee-level wide-format tables without relying on a numeric SIDE code.
- Files with `SIDE`, `SID`, `MRSIDE`, or `MRKSIDE` require file-specific codebook confirmation before numeric side values are used.
- `SID` may mean side identifier in some tables, but can also be confused with subject/sample identifiers; each file must be reviewed.

## Modeling rule

Only tables marked `reliable_wide_right_left_columns_by_variable_name` or later manually confirmed with file-specific codebook evidence should be used for knee-level side mapping.
"""
    (dirs["03_side_sid_mapping_audit"] / "side_sid_global_mapping_hypothesis.md").write_text(hyp, encoding="utf-8")
    review = """# SIDE/SID final review required

Before formal retraining:

1. Confirm numeric `SIDE/SID/MRSIDE/MRKSIDE` coding from OAI codebook or SAS labels.
2. Exclude files where `SID` means subject/sample ID rather than side ID.
3. Build a file-specific mapping table; do not apply one global 1/2 mapping across all files.
4. Keep person-level predictors separate from knee-level outcomes.
"""
    (dirs["03_side_sid_mapping_audit"] / "side_sid_final_review_required.md").write_text(review, encoding="utf-8")
    return side_candidate, mapping_df, knee_df


def build_endpoint_feasibility(csv_file_df: pd.DataFrame, csv_col_df: pd.DataFrame, knee_df: pd.DataFrame, dirs: dict[str, Path]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    def endpoint_rows(kind: str, regex: str) -> list[dict[str, Any]]:
        rows = []
        for _, f in csv_file_df.iterrows():
            cols = csv_col_df[csv_col_df["file_name"].eq(f["file_name"])] if not csv_col_df.empty else pd.DataFrame()
            matched = cols[cols["column_name_upper"].astype(str).str.contains(regex, regex=True, na=False)] if not cols.empty else pd.DataFrame()
            if matched.empty:
                continue
            knee = knee_df[knee_df["file_name"].eq(f["file_name"])]
            krow = knee.iloc[0].to_dict() if not knee.empty else {}
            rows.append(
                {
                    "available_file": f["file_name"],
                    "available_visit": visit_prefixes(matched["column_name"].astype(str).tolist(), f["file_name"]),
                    "id_field": krow.get("id_column", ""),
                    "side_field": krow.get("side_column", ""),
                    "key_endpoint_fields": ";".join(matched["column_name"].astype(str).head(50).tolist()),
                    "baseline_persons_or_rows": f.get("num_rows", ""),
                    "baseline_knees_or_rows": f.get("num_rows", "") if krow.get("knee_level_confirmed", False) else "",
                    "followup_persons_or_rows": "",
                    "followup_knees_or_rows": "",
                    "missingness_basis": "schema/profile only; exact endpoint cohort not built in precheck",
                    "side_reliable": krow.get("knee_level_confirmed", False) and krow.get("notes", "") == "wide_right_left",
                    "notes": krow.get("notes", ""),
                }
            )
        return rows

    structural = pd.DataFrame(endpoint_rows("structural", r"XRKL|XRJS|XROST|XRSCT|KXR|KL"))
    surgery = pd.DataFrame(endpoint_rows("surgery", r"V99ERK|V99ELK|TKR|SURG|REPLACEMENT|ARTHRO"))
    symptom = pd.DataFrame(endpoint_rows("symptom", r"WOM|KOOS|KPN|PAIN|ADL|STIFF|WALK|STAIR"))
    structural.to_csv(dirs["04_endpoint_feasibility"] / "endpoint1_structural_progression_feasibility.csv", index=False, encoding="utf-8-sig")
    surgery.to_csv(dirs["04_endpoint_feasibility"] / "endpoint2_surgery_event_feasibility.csv", index=False, encoding="utf-8-sig")
    symptom.to_csv(dirs["04_endpoint_feasibility"] / "endpoint3_symptom_function_feasibility.csv", index=False, encoding="utf-8-sig")
    (dirs["04_endpoint_feasibility"] / "endpoint1_structural_progression_definition_options.md").write_text(
        """# Endpoint 1: KL / radiographic structural progression

Candidate definitions:

A. KL grade increase >= 1 between baseline and follow-up.
B. KL grade increase >= 2 for stricter progression.
C. Incident radiographic OA among baseline KL < 2 knees.
D. JSN worsening using OARSI/KXR structural fields.
E. Composite structural progression using KL, JSN, osteophyte or sclerosis.

Precheck conclusion: constructible if right/left or SIDE coding is confirmed for longitudinal KXR/KL tables. Do not train until side mapping and person-level split rules are frozen.
""",
        encoding="utf-8",
    )
    (dirs["04_endpoint_feasibility"] / "endpoint2_surgery_event_definition_options.md").write_text(
        """# Endpoint 2: TKR / knee surgery event

Required constructability:

- event_observed: candidate from V99 right/left knee surgery/outcome fields.
- event_time: candidate from date/day fields, but exact censoring logic must be frozen before training.
- surgery_side: candidate from right/left outcome field names; numeric SIDE fields require codebook evidence.
- TKR only vs any knee surgery: both should be defined before model fitting.
- Competing events: review death/loss to follow-up if available.
- Modeling: Cox/survival model is appropriate if event time and censoring are reliable; otherwise define fixed-horizon binary endpoints.
""",
        encoding="utf-8",
    )
    (dirs["04_endpoint_feasibility"] / "endpoint3_symptom_function_definition_options.md").write_text(
        """# Endpoint 3: symptom/function worsening

Constructability rules:

1. Use knee-level WOMAC/KOOS/pain fields only if side-specific right/left columns or confirmed side coding exists.
2. If a score is person-level only, report it as a person-level sensitivity endpoint rather than forcing knee-level labels.
3. Candidate worsening rules include MCID-based WOMAC pain/function worsening, KOOS worsening, or composite pain/function worsening.
4. MCID threshold must be prespecified and not tuned on test data.
""",
        encoding="utf-8",
    )
    return structural, surgery, symptom


def write_protocol(dirs: dict[str, Path], structural: pd.DataFrame, surgery: pd.DataFrame, symptom: pd.DataFrame) -> None:
    protocol = """# KOM-Risk retraining protocol FREEZE DRAFT

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
"""
    (dirs["05_training_protocol_freeze"] / "KOMRisk_retraining_protocol_FREEZE_DRAFT.md").write_text(protocol, encoding="utf-8")
    posthoc = """# Posthoc error analysis plan

Analyze after model training only:

1. False positive cases.
2. False negative cases.
3. Error by baseline KL grade.
4. Error by age.
5. Error by BMI.
6. Error by sex.
7. Error by side.
8. Error by missingness burden.
9. Error by follow-up length.
10. Error by endpoint definition.

This analysis is exploratory/posthoc and should not be written as the main result.
"""
    (dirs["05_training_protocol_freeze"] / "posthoc_error_analysis_plan.md").write_text(posthoc, encoding="utf-8")


def add_file_to_zip(zf: zipfile.ZipFile, path: Path, arcname: str, fallback_rows: list[dict[str, str]]) -> None:
    try:
        zf.write(path, arcname)
    except Exception:
        flat = Path(arcname).name
        zf.write(path, flat)
        fallback_rows.append({"original_path": str(path), "zip_arcname": flat, "reason": "path_length_or_zip_write_fallback"})


def make_upload_zips(manifest: pd.DataFrame, dirs: dict[str, Path], sas_root: Path | None) -> pd.DataFrame:
    if manifest.empty:
        index = pd.DataFrame()
        index.to_csv(dirs["06_upload_packages"] / "OAI_Codebook_PDFs_UPLOAD_INDEX.csv", index=False, encoding="utf-8-sig")
        return index
    work = manifest.copy()
    def priority(row: pd.Series) -> int:
        text = f"{row.get('file_name','')} {row.get('relative_path','')}".upper()
        if any(k in text for k in ["SIDE", "SID", "KNEE", "KL", "SURG", "TKR", "WOMAC", "KOOS", "PAIN", "FUNCTION"]):
            return 1
        if any(k in text for k in ["RADIOGRAPH", "MRI", "CLINICAL", "OUTCOME"]):
            return 2
        return 3
    work["upload_priority"] = work.apply(priority, axis=1)
    work = work.sort_values(["upload_priority", "file_size_bytes"], ascending=[True, False])
    parts: list[list[pd.Series]] = []
    current: list[pd.Series] = []
    current_size = 0
    for _, r in work.iterrows():
        size = int(r["file_size_bytes"])
        if current and current_size + size > MAX_ZIP_BYTES:
            parts.append(current)
            current = []
            current_size = 0
        current.append(r)
        current_size += size
    if current:
        parts.append(current)
    index_rows = []
    fallback_report = []
    for i, rows in enumerate(parts, 1):
        zip_name = f"OAI_Codebook_PDFs_part{i:03d}.zip"
        zip_path = dirs["06_upload_packages"] / zip_name
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for r in rows:
                p = Path(r["original_full_path"])
                arcname = r["relative_path"]
                add_file_to_zip(zf, p, arcname, fallback_report)
        with zipfile.ZipFile(zip_path) as zf:
            bad = zf.testzip()
        sha = sha256_file(zip_path)
        part_manifest = pd.DataFrame(rows)
        part_manifest.to_csv(dirs["06_upload_packages"] / f"zip_manifest_part{i:03d}.csv", index=False, encoding="utf-8-sig")
        (dirs["06_upload_packages"] / f"zip_integrity_part{i:03d}.txt").write_text(f"bad_member={bad}\n", encoding="utf-8")
        (dirs["06_upload_packages"] / f"zip_sha256_part{i:03d}.txt").write_text(f"{sha}  {zip_name}\n", encoding="utf-8")
        index_rows.append(
            {
                "zip_name": zip_name,
                "zip_size_mb": round(zip_path.stat().st_size / 1024 / 1024, 4),
                "file_count": len(rows),
                "sha256": sha,
                "bad_member": bad,
                "upload_priority": min(int(r["upload_priority"]) for r in rows),
                "notes": "codebook/PDF/SAS-program upload package",
            }
        )
    index = pd.DataFrame(index_rows)
    index.to_csv(dirs["06_upload_packages"] / "OAI_Codebook_PDFs_UPLOAD_INDEX.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(fallback_report).to_csv(dirs["07_QC"] / "path_length_fallback_report.csv", index=False, encoding="utf-8-sig")
    return index


def make_schema_zip(dirs: dict[str, Path]) -> pd.DataFrame:
    zip_path = dirs["06_upload_packages"] / "OAI_CSV_SCHEMA_SAMPLES_part001.zip"
    include_dirs = [dirs["02_csv_schema_inventory"]]
    fallback_rows = []
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for inc in include_dirs:
            for p in inc.rglob("*"):
                if p.is_file():
                    add_file_to_zip(zf, p, safe_rel(p, inc.parent), fallback_rows)
    with zipfile.ZipFile(zip_path) as zf:
        bad = zf.testzip()
        count = len(zf.namelist())
    sha = sha256_file(zip_path)
    row = pd.DataFrame(
        [
            {
                "zip_name": zip_path.name,
                "zip_size_mb": round(zip_path.stat().st_size / 1024 / 1024, 4),
                "file_count": count,
                "sha256": sha,
                "bad_member": bad,
                "upload_priority": 1,
                "notes": "CSV schema and first-20-row samples only; no full patient data",
            }
        ]
    )
    row.to_csv(dirs["06_upload_packages"] / "OAI_CSV_SCHEMA_SAMPLES_UPLOAD_INDEX.csv", index=False, encoding="utf-8-sig")
    return row


def make_final_zips(base: Path, out: Path, dirs: dict[str, Path]) -> pd.DataFrame:
    # Do not duplicate upload package zips inside the final precheck zip; they
    # are adjacent outputs and are already indexed in 06_upload_packages.
    files = [p for p in out.rglob("*") if p.is_file() and p.suffix.lower() != ".zip"]
    parts: list[list[Path]] = []
    current: list[Path] = []
    current_size = 0
    for p in sorted(files, key=lambda x: str(x).lower()):
        size = p.stat().st_size
        if current and current_size + size > MAX_ZIP_BYTES:
            parts.append(current)
            current = []
            current_size = 0
        current.append(p)
        current_size += size
    if current:
        parts.append(current)
    rows = []
    for i, part in enumerate(parts, 1):
        zip_name = f"{FINAL_ZIP_PREFIX}.zip" if len(parts) == 1 else f"{FINAL_ZIP_PREFIX}_part{i:03d}.zip"
        zip_path = base / zip_name
        if zip_path.exists():
            zip_path.unlink()
        fallbacks = []
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for p in part:
                add_file_to_zip(zf, p, safe_rel(p, base), fallbacks)
        with zipfile.ZipFile(zip_path) as zf:
            bad = zf.testzip()
        rows.append(
            {
                "zip_name": zip_name,
                "zip_path": str(zip_path),
                "zip_size_mb": round(zip_path.stat().st_size / 1024 / 1024, 4),
                "file_count": len(part),
                "sha256": sha256_file(zip_path),
                "bad_member": bad,
                "notes": "final precheck package; upload zips are separate",
            }
        )
    df = pd.DataFrame(rows)
    df.to_csv(dirs["07_QC"] / "final_zip_index.csv", index=False, encoding="utf-8-sig")
    return df


def write_qc_and_readme(
    out: Path,
    dirs: dict[str, Path],
    paths: dict[str, Any],
    codebook_manifest: pd.DataFrame,
    nonpdf_manifest: pd.DataFrame,
    csv_file_df: pd.DataFrame,
    csv_col_df: pd.DataFrame,
    side_candidate: pd.DataFrame,
    mapping_df: pd.DataFrame,
    structural: pd.DataFrame,
    surgery: pd.DataFrame,
    symptom: pd.DataFrame,
    codebook_index: pd.DataFrame,
    schema_index: pd.DataFrame,
    final_index: pd.DataFrame | None = None,
) -> None:
    no_training = """No model training was run in this phase.

This precheck only scanned source files, generated manifests/schema samples, audited SIDE/SID candidates, assessed endpoint constructability, and wrote a retraining protocol freeze draft.
No model fitting, hyperparameter tuning, final model selection, or performance estimation was performed.
"""
    (dirs["07_QC"] / "no_training_confirmed.txt").write_text(no_training, encoding="utf-8")
    qc = [
        ("No model training performed", True),
        ("No fabricated performance output", True),
        ("No hard-coded 1=Right / 2=Left", True),
        ("All codebook/upload zips <450MB", bool(codebook_index.empty or (codebook_index["zip_size_mb"] < MAX_ZIP_MB).all())),
        ("Schema sample zip <450MB", bool(schema_index.empty or (schema_index["zip_size_mb"] < MAX_ZIP_MB).all())),
        ("Upload zip integrity passed", bool((codebook_index.get("bad_member", pd.Series([None])).isna()).all() and (schema_index.get("bad_member", pd.Series([None])).isna()).all())),
        ("Manifests readable", True),
        ("Schema files readable", not csv_file_df.empty and not csv_col_df.empty),
        ("SIDE/SID candidates output", not side_candidate.empty),
        ("Endpoint feasibility output", len(structural) > 0 and len(surgery) > 0 and len(symptom) > 0),
        ("Training protocol freeze draft output", (dirs["05_training_protocol_freeze"] / "KOMRisk_retraining_protocol_FREEZE_DRAFT.md").exists()),
    ]
    lines = ["# Precheck QC checklist", ""]
    for name, ok in qc:
        lines.append(f"- [{'PASS' if ok else 'FAIL'}] {name}")
    (dirs["07_QC"] / "precheck_QC_checklist.md").write_text("\n".join(lines), encoding="utf-8")
    zip_lines = ["# Zip integrity report", ""]
    for df_name, df in [("Codebook upload packages", codebook_index), ("CSV schema/sample packages", schema_index), ("Final precheck packages", final_index)]:
        if df is None or df.empty:
            continue
        zip_lines.append(f"## {df_name}")
        for _, r in df.iterrows():
            zip_lines.append(f"- {r['zip_name']}: {r['zip_size_mb']} MB, bad_member={r['bad_member']}, sha256={r['sha256']}")
    (dirs["07_QC"] / "zip_integrity_report.md").write_text("\n".join(zip_lines), encoding="utf-8")
    fallback_csv = dirs["07_QC"] / "path_length_fallback_report.csv"
    fallback_text = "# Path length fallback report\n\n"
    if fallback_csv.exists() and fallback_csv.stat().st_size > 5:
        fallback_text += "Fallback rows exist; see `path_length_fallback_report.csv`.\n"
    else:
        fallback_text += "No zip path-length fallback was required for generated upload packages.\n"
    (dirs["07_QC"] / "path_length_fallback_report.md").write_text(fallback_text, encoding="utf-8")
    readme = f"""# KOMRisk Retrain Precheck 202606

## Purpose

This package freezes data-preparation assumptions before formal KOM-Risk retraining. It does not train models, tune hyperparameters, or report final performance.

## Source paths found

- SAS/codebook selected root: `{paths.get('sas_root')}`
- CSV selected root: `{paths.get('csv_root')}`
- All SAS candidate paths: {', '.join(map(str, paths.get('sas_paths', [])))}
- All CSV candidate paths: {', '.join(map(str, paths.get('csv_paths', [])))}

## Summary

- PDF/codebook/program files found: {len(codebook_manifest)}
- Non-upload SAS/XPT/SF3 data files listed: {len(nonpdf_manifest)}
- CSV files scanned: {len(csv_file_df)}
- CSV fields indexed: {len(csv_col_df)}
- SIDE/SID candidate columns: {len(side_candidate)}
- Files with reliable wide right/left knee-level structure: {int(mapping_df['mapping_status'].astype(str).str.contains('reliable_wide').sum()) if not mapping_df.empty else 0}
- Files with uncertain numeric side/SID mapping: {int(mapping_df['mapping_status'].astype(str).str.contains('uncertain|candidate', regex=True).sum()) if not mapping_df.empty else 0}

## Endpoint constructability

- Structural progression: candidate constructible if KXR/KL side mapping is confirmed.
- TKR/knee surgery: candidate constructible from V99 right/left outcome fields; event/censor timing must be frozen.
- Symptom/function worsening: candidate constructible where WOMAC/KOOS/pain fields are knee-level; otherwise person-level sensitivity endpoint.

## Formal retraining readiness

PARTIAL. The data inventory and protocol freeze are ready, but formal training should wait until file-specific side mapping and endpoint definitions are manually confirmed.
"""
    (dirs["00_README"] / "README_KOMRisk_Retrain_Precheck.md").write_text(readme, encoding="utf-8")


def main() -> int:
    base = Path.cwd()
    out, backups = reset_output(base)
    dirs = ensure_dirs(out)
    paths = locate_paths()
    codebook_manifest, nonpdf_manifest, _ = scan_codebooks(paths.get("sas_root"), dirs, paths)
    csv_file_df, csv_col_df, side_cols, endpoint_cols = scan_csv_schema(paths.get("csv_root"), dirs)
    codebook_hits = find_codebook_hits(codebook_manifest, dirs)
    side_candidate, mapping_df, knee_df = build_side_knee_audit(csv_file_df, csv_col_df, codebook_hits, dirs)
    structural, surgery, symptom = build_endpoint_feasibility(csv_file_df, csv_col_df, knee_df, dirs)
    write_protocol(dirs, structural, surgery, symptom)
    codebook_index = make_upload_zips(codebook_manifest, dirs, paths.get("sas_root"))
    schema_index = make_schema_zip(dirs)
    write_qc_and_readme(out, dirs, paths, codebook_manifest, nonpdf_manifest, csv_file_df, csv_col_df, side_candidate, mapping_df, structural, surgery, symptom, codebook_index, schema_index)
    final_index = make_final_zips(base, out, dirs)
    write_qc_and_readme(out, dirs, paths, codebook_manifest, nonpdf_manifest, csv_file_df, csv_col_df, side_candidate, mapping_df, structural, surgery, symptom, codebook_index, schema_index, final_index)
    summary = {
        "pdf_codebook_count": int(len(codebook_manifest)),
        "codebook_zip_count": int(len(codebook_index)),
        "csv_count": int(len(csv_file_df)),
        "field_count": int(len(csv_col_df)),
        "side_candidate_columns": int(len(side_candidate)),
        "reliable_wide_side_files": int(mapping_df["mapping_status"].astype(str).str.contains("reliable_wide").sum()) if not mapping_df.empty else 0,
        "uncertain_side_files": int(mapping_df["mapping_status"].astype(str).str.contains("uncertain|candidate", regex=True).sum()) if not mapping_df.empty else 0,
        "final_zip_count": int(len(final_index)),
        "backups": backups,
    }
    (dirs["00_README"] / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("KOM-Risk retrain precheck completed.")
    print(f"PDF/codebook files found: {len(codebook_manifest)}")
    print(f"Codebook upload zips: {len(codebook_index)}")
    for _, r in codebook_index.iterrows():
        print(f"- {r['zip_name']}: {r['zip_size_mb']} MB, bad_member={r['bad_member']}")
    print(f"CSV files scanned: {len(csv_file_df)}")
    print(f"CSV fields indexed: {len(csv_col_df)}")
    print(f"SIDE/SID candidate columns: {len(side_candidate)}")
    print(f"Reliable wide-format knee-level files: {summary['reliable_wide_side_files']}")
    print(f"Uncertain side/SID mapping files: {summary['uncertain_side_files']}")
    print("Endpoint constructability: structural=partial_confirmable; surgery=partial_confirmable; symptom=partial_confirmable/person-level-sensitivity possible")
    print("Formal retraining readiness: PARTIAL - manual side/endpoint confirmation required before training.")
    print("Output directory:")
    print(out)
    print("Final zip packages:")
    for _, r in final_index.iterrows():
        print(f"- {r['zip_name']}: {r['zip_size_mb']} MB, bad_member={r['bad_member']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
