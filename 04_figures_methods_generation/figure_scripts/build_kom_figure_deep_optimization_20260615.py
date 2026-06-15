from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import textwrap
import warnings
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import patches
from matplotlib.backends.backend_agg import FigureCanvasAgg
from PIL import Image, ImageStat


warnings.filterwarnings("ignore", category=UserWarning)

ROOT = Path.cwd()
OUT = ROOT / "KOM_Figure_Deep_Optimization_20260615"
FIG = OUT / "figures_no_title"
COMP = OUT / "figures_composite_editable"
SRC = OUT / "source_data"
TABLES = OUT / "tables"
QC = OUT / "qc"
AUDIT = OUT / "audit"
SCRIPTS = OUT / "scripts"

if OUT.exists():
    out_resolved = OUT.resolve()
    root_resolved = ROOT.resolve()
    if out_resolved.parent == root_resolved and out_resolved.name.startswith("KOM_Figure_Deep_Optimization_"):
        shutil.rmtree(out_resolved, ignore_errors=True)

for d in [OUT, FIG, COMP, SRC, TABLES, QC, AUDIT, SCRIPTS]:
    d.mkdir(parents=True, exist_ok=True)

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 8,
        "axes.labelsize": 8,
        "axes.titlesize": 9,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.fontsize": 7,
        "figure.dpi": 160,
        "savefig.dpi": 300,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": "#E6E8EB",
        "grid.linewidth": 0.7,
        "axes.axisbelow": True,
    }
)

PALETTE = [
    "#2E6F9E",
    "#2F8F73",
    "#A64535",
    "#7A5AA6",
    "#B57B2E",
    "#4D6A7A",
    "#C75D87",
    "#5B8C5A",
    "#8A6F4D",
    "#4767A8",
    "#B36B5E",
    "#567C8D",
]

figure_records: list[dict[str, Any]] = []
source_records: list[dict[str, Any]] = []
blocked_records: list[dict[str, Any]] = []


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)


def safe_name(text: Any, max_len: int = 90) -> str:
    text = str(text)
    text = re.sub(r"[^0-9A-Za-z._-]+", "_", text).strip("_")
    text = re.sub(r"_+", "_", text)
    return (text[:max_len] or "figure").strip("_")


def wrap_label(text: Any, width: int = 22) -> str:
    text = str(text).replace("_", " ")
    if len(text) <= width:
        return text
    return "\n".join(textwrap.wrap(text, width=width, break_long_words=False))


def coerce_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.replace({"--": np.nan, "—": np.nan, "NA": np.nan, "": np.nan}), errors="coerce")


def read_csv_smart(path: Path, **kwargs: Any) -> pd.DataFrame:
    for enc in ["utf-8-sig", "utf-8", "gb18030", "gbk"]:
        try:
            return pd.read_csv(path, encoding=enc, **kwargs)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, encoding="utf-8", errors="replace", **kwargs)


def read_json_smart(path: Path) -> Any:
    for enc in ["utf-8-sig", "utf-8", "gb18030", "gbk"]:
        try:
            return json.loads(path.read_text(encoding=enc))
        except UnicodeDecodeError:
            continue
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def image_qc(path: Path) -> tuple[str, str]:
    try:
        with Image.open(path) as img:
            if img.width < 800 or img.height < 500:
                return "REVIEW", f"small_image:{img.width}x{img.height}"
            stat = ImageStat.Stat(img.convert("L"))
            if max(stat.stddev) < 1.5:
                return "FAIL", "near_blank_image"
            return "PASS", f"{img.width}x{img.height};std={max(stat.stddev):.2f}"
    except Exception as exc:
        return "FAIL", f"image_qc_error:{exc}"


def svg_qc(path: Path) -> tuple[str, str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        has_text = "<text" in text
        has_title_words = re.search(r">\s*(Figure|Fig\.|Title|Q1|Q2|Q3|Q4)\b", text, re.I) is not None
        if not has_text:
            return "REVIEW", "svg_text_not_editable_or_no_text"
        if has_title_words:
            return "REVIEW", "possible_title_or_quadrant_text_in_svg"
        return "PASS", "editable_text_detected"
    except Exception as exc:
        return "REVIEW", f"svg_qc_error:{exc}"


def text_overlap_qc(fig: plt.Figure, min_area: float = 20.0) -> tuple[str, str]:
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    boxes = []
    for txt in fig.findobj(match=matplotlib.text.Text):
        if not txt.get_visible():
            continue
        s = txt.get_text()
        if not s or len(s.strip()) == 0:
            continue
        try:
            box = txt.get_window_extent(renderer=renderer).expanded(1.02, 1.08)
        except Exception:
            continue
        if box.width * box.height >= min_area:
            boxes.append((s, box))
    overlaps = 0
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a = boxes[i][1]
            b = boxes[j][1]
            ix = max(0, min(a.x1, b.x1) - max(a.x0, b.x0))
            iy = max(0, min(a.y1, b.y1) - max(a.y0, b.y0))
            if ix * iy > 8:
                overlaps += 1
    if overlaps:
        return "REVIEW", f"text_overlap_pairs={overlaps}"
    return "PASS", "no_text_overlap_detected"


def save_source(df: pd.DataFrame | None, name: str) -> Path | None:
    if df is None:
        return None
    path = SRC / f"{safe_name(name)}_source.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def save_fig(
    fig: plt.Figure,
    category: str,
    name: str,
    source_df: pd.DataFrame | None = None,
    axis_mode: str = "dynamic",
    note: str = "",
    composite: bool = False,
) -> None:
    outdir = (COMP if composite else FIG / category)
    outdir.mkdir(parents=True, exist_ok=True)
    base = outdir / safe_name(name)
    fig.subplots_adjust(top=0.96)
    text_status, text_notes = text_overlap_qc(fig)
    png = base.with_suffix(".png")
    svg = base.with_suffix(".svg")
    pdf = base.with_suffix(".pdf")
    fig.savefig(png, bbox_inches="tight", facecolor="white")
    fig.savefig(svg, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf, bbox_inches="tight", facecolor="white")
    src = save_source(source_df, name)
    img_status, img_notes = image_qc(png)
    svg_status, svg_notes = svg_qc(svg)
    statuses = [text_status, img_status, svg_status]
    final = "PASS" if all(s == "PASS" for s in statuses) else ("FAIL" if "FAIL" in statuses else "REVIEW")
    figure_records.append(
        {
            "figure_id": safe_name(name),
            "category": category,
            "axis_mode": axis_mode,
            "png": str(png),
            "svg": str(svg),
            "pdf": str(pdf),
            "source_data": str(src) if src else "",
            "qc_status": final,
            "qc_notes": "; ".join([text_notes, img_notes, svg_notes, note]).strip("; "),
        }
    )
    plt.close(fig)


def set_numeric_axis(ax: plt.Axes, values: Iterable[float], axis_mode: str, axis: str = "y", pad: float = 0.08) -> None:
    vals = pd.Series(list(values), dtype="float64").dropna()
    if vals.empty:
        return
    vmin = float(vals.min())
    vmax = float(vals.max())
    span = vmax - vmin if vmax > vmin else max(abs(vmax), 1.0) * 0.1
    if axis_mode == "zero":
        lo = min(0.0, vmin - span * pad)
        hi = vmax + span * (pad + 0.08)
    else:
        lo = vmin - span * (pad + 0.12)
        hi = vmax + span * (pad + 0.12)
        if 0 <= vmin:
            lo = max(0, lo) if vmax > 1.5 else lo
    if lo == hi:
        hi = lo + 1.0
    if axis == "y":
        ax.set_ylim(lo, hi)
    else:
        ax.set_xlim(lo, hi)


def grouped_bar(
    data: pd.DataFrame,
    x: str,
    y: str,
    hue: str | None,
    category: str,
    name: str,
    y_label: str,
    axis_mode: str,
    lower_better: bool = False,
    sort_by: str | None = None,
    composite: bool = False,
) -> None:
    df = data.copy()
    df[y] = coerce_numeric(df[y])
    df = df.dropna(subset=[x, y])
    if df.empty:
        return
    if sort_by and sort_by in df.columns:
        order = df.sort_values(sort_by)[x].astype(str).tolist()
    else:
        order = df.groupby(x)[y].mean().sort_values(ascending=lower_better).index.astype(str).tolist()
    df[x] = pd.Categorical(df[x].astype(str), categories=order, ordered=True)
    if hue:
        hues = list(df[hue].astype(str).dropna().unique())
    else:
        hues = [None]
    width = max(6.0, min(11.5, 0.48 * len(order) + 2.4))
    fig, ax = plt.subplots(figsize=(width, 4.8))
    xpos = np.arange(len(order))
    if hue:
        bw = min(0.75 / max(len(hues), 1), 0.22)
        for i, h in enumerate(hues):
            sub = df[df[hue].astype(str) == h]
            means = sub.groupby(x, observed=False)[y].mean().reindex(order)
            sems = sub.groupby(x, observed=False)[y].sem().reindex(order)
            ax.bar(
                xpos + (i - (len(hues) - 1) / 2) * bw,
                means.values,
                bw,
                label=str(h),
                color=PALETTE[i % len(PALETTE)],
                yerr=sems.values if len(sub) > len(order) else None,
                capsize=2,
                linewidth=0,
            )
        ax.legend(frameon=False, ncol=min(3, len(hues)), loc="best")
    else:
        vals = df.groupby(x, observed=False)[y].mean().reindex(order)
        sems = df.groupby(x, observed=False)[y].sem().reindex(order)
        ax.bar(xpos, vals.values, 0.68, color=PALETTE[0], yerr=sems.values if len(df) > len(order) else None, capsize=2)
    ax.set_xticks(xpos)
    ax.set_xticklabels([wrap_label(o, 14) for o in order], rotation=0)
    ax.set_ylabel(y_label)
    ax.set_xlabel("")
    ax.axhline(0, color="#7A7F85", linewidth=0.8)
    set_numeric_axis(ax, df[y].tolist(), axis_mode, "y")
    if lower_better:
        ax.text(0.01, 0.98, "Lower is better", transform=ax.transAxes, va="top", ha="left", fontsize=7, color="#555")
    save_fig(fig, category, f"{name}_{axis_mode}", df, axis_mode=axis_mode, composite=composite)


def horizontal_bar(
    data: pd.DataFrame,
    label_col: str,
    value_col: str,
    category: str,
    name: str,
    x_label: str,
    axis_mode: str,
    lower_better: bool = False,
    err_col: str | None = None,
) -> None:
    df = data.copy()
    df[value_col] = coerce_numeric(df[value_col])
    df = df.dropna(subset=[label_col, value_col])
    if df.empty:
        return
    df = df.sort_values(value_col, ascending=not lower_better).tail(25)
    height = max(3.4, min(10, 0.28 * len(df) + 1.4))
    fig, ax = plt.subplots(figsize=(7.5, height))
    y = np.arange(len(df))
    xerr = df[err_col].values if err_col and err_col in df.columns else None
    ax.barh(y, df[value_col].values, color=PALETTE[0], xerr=xerr, capsize=2)
    ax.set_yticks(y)
    ax.set_yticklabels([wrap_label(v, 28) for v in df[label_col]])
    ax.set_xlabel(x_label)
    ax.set_ylabel("")
    set_numeric_axis(ax, df[value_col].tolist(), axis_mode, "x")
    if lower_better:
        ax.text(0.99, 0.02, "Lower is better", transform=ax.transAxes, va="bottom", ha="right", fontsize=7, color="#555")
    save_fig(fig, category, f"{name}_{axis_mode}", df, axis_mode=axis_mode)


def normalise_for_radar(df: pd.DataFrame, model_col: str, metric_specs: list[tuple[str, str, str]]) -> pd.DataFrame:
    rows = []
    for _, r in df.iterrows():
        out = {model_col: r[model_col]}
        for metric, label, direction in metric_specs:
            vals = coerce_numeric(df[metric]) if metric in df.columns else pd.Series(dtype=float)
            raw = pd.to_numeric(pd.Series([r.get(metric, np.nan)]), errors="coerce").iloc[0]
            vmin = vals.min(skipna=True)
            vmax = vals.max(skipna=True)
            if pd.isna(raw) or pd.isna(vmin) or pd.isna(vmax):
                score = np.nan
            elif abs(vmax - vmin) < 1e-12:
                score = 1.0
            elif direction == "higher":
                score = (raw - vmin) / (vmax - vmin)
            else:
                score = (vmax - raw) / (vmax - vmin)
            out[label] = float(score) if not pd.isna(score) else np.nan
            out[f"raw_{metric}"] = raw
            out[f"direction_{metric}"] = direction
        rows.append(out)
    return pd.DataFrame(rows)


def radar_plot(
    radar_df: pd.DataFrame,
    model_col: str,
    category: str,
    name: str,
    note: str = "",
    max_models: int | None = None,
) -> None:
    labels = [c for c in radar_df.columns if not c.startswith("raw_") and not c.startswith("direction_") and c != model_col]
    plot_df = radar_df.dropna(subset=labels, how="all").copy()
    if plot_df.empty or not labels:
        return
    plot_df["mean_score"] = plot_df[labels].mean(axis=1)
    plot_df = plot_df.sort_values("mean_score", ascending=False)
    if max_models:
        plot_df = plot_df.head(max_models)
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    angles += angles[:1]
    fig = plt.figure(figsize=(7.2, 6.8))
    ax = plt.subplot(111, polar=True)
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0.25", "0.50", "0.75", "1.00"], fontsize=7, color="#555")
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([wrap_label(x, 12) for x in labels], fontsize=8)
    for i, (_, row) in enumerate(plot_df.iterrows()):
        values = [row[l] for l in labels]
        values += values[:1]
        color = PALETTE[i % len(PALETTE)]
        lw = 2.2 if i == 0 else 1.15
        alpha = 0.22 if i == 0 else 0.05
        ax.plot(angles, values, color=color, linewidth=lw, label=str(row[model_col]))
        ax.fill(angles, values, color=color, alpha=alpha)
    ax.legend(frameon=False, loc="center left", bbox_to_anchor=(1.08, 0.5), borderaxespad=0.0)
    source = plot_df[[model_col, "mean_score"] + labels + [c for c in plot_df.columns if c.startswith("raw_") or c.startswith("direction_")]]
    save_fig(fig, category, name, source, axis_mode="0_to_1_same_direction", note=note)


def decode_zip_bytes(data: bytes) -> str:
    for enc in ["utf-8-sig", "utf-8", "gb18030", "gbk"]:
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def zip_csv_rows(zf: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    try:
        raw = zf.read(name)
    except KeyError:
        return []
    reader = csv.DictReader(io.StringIO(decode_zip_bytes(raw)))
    return list(reader)


def find_hci_zips() -> list[Path]:
    candidates: list[Path] = []
    roots = [
        Path.home() / "Downloads",
        Path.home() / "xwechat_files",
        Path.home() / "WPS Cloud Files",
    ]
    for base in roots:
        if not base.exists():
            continue
        for p in base.rglob("*.zip"):
            if "KOA_HCI_" in p.name:
                candidates.append(p)
    return candidates


def choose_hci_packages(limit: int = 26) -> pd.DataFrame:
    required = {
        "01_record_overview.csv",
        "02_clinician_baseline.csv",
        "03_history_elicitation.csv",
        "04_case_level_wide.csv",
        "05_case_ratings_long.csv",
        "06_stage_workload_wide.csv",
        "07_stage_workload_long.csv",
        "08_stage_summary.csv",
        "09_final_survey.csv",
        "10_event_log.csv",
        "11_timing_metrics.csv",
        "12_case_exposure_manifest.csv",
        "13_all_metrics_long.csv",
        "14_full_audit_single_table.csv",
    }
    rows = []
    for p in find_hci_zips():
        try:
            with zipfile.ZipFile(p) as zf:
                names = {Path(n).name for n in zf.namelist()}
                raw_files = sum(1 for n in required if n in names)
                cases = zip_csv_rows(zf, "04_case_level_wide.csv")
                ratings = zip_csv_rows(zf, "05_case_ratings_long.csv")
                workload = zip_csv_rows(zf, "07_stage_workload_long.csv")
                survey = zip_csv_rows(zf, "09_final_survey.csv")
            m = re.search(r"KOA_HCI_(\d+)", p.name)
            ts = m.group(1) if m else ""
            md5 = hashlib.md5(p.read_bytes()).hexdigest()
            rows.append(
                {
                    "path": str(p),
                    "package_name": p.name,
                    "package_ts": ts,
                    "size_bytes": p.stat().st_size,
                    "raw_files": raw_files,
                    "n_case": len(cases),
                    "n_rating": len(ratings),
                    "n_workload": len(workload),
                    "n_survey": len(survey),
                    "md5": md5,
                    "complete": raw_files >= 14 and len(cases) >= 30 and len(ratings) >= 150,
                }
            )
        except Exception as exc:
            rows.append({"path": str(p), "package_name": p.name, "error": repr(exc), "complete": False})
    df = pd.DataFrame(rows)
    if df.empty:
        blocked_records.append({"module": "KOM-Sim HCI", "item": "raw HCI packages", "status": "missing"})
        return df
    df.to_csv(QC / "hci_all_zip_candidates.csv", index=False, encoding="utf-8-sig")
    complete = df[df["complete"]].copy()
    complete = complete.sort_values(["package_ts", "size_bytes"], ascending=[False, False])
    complete = complete.drop_duplicates("md5", keep="first").head(limit)
    complete.to_csv(QC / "hci_selected_26_source_zips.csv", index=False, encoding="utf-8-sig")
    return complete


def metric_code(label: Any) -> str:
    s = str(label)
    if "信心" in s or "confidence" in s.lower():
        return "confidence"
    if "充分" in s or "sufficiency" in s.lower():
        return "info_sufficiency"
    if "把握" in s or "certainty" in s.lower():
        return "decision_certainty"
    if "工作负担" in s or "workload" in s.lower():
        return "case_workload"
    if "影响" in s or "influence" in s.lower():
        return "ai_influence"
    if "脑力" in s or "mental" in s.lower():
        return "mental_demand"
    if "疲劳" in s or "fatigue" in s.lower():
        return "operation_fatigue"
    if "时间压力" in s or "time pressure" in s.lower():
        return "time_pressure"
    if "努力" in s or "effort" in s.lower():
        return "effort"
    if "挫" in s or "frustration" in s.lower():
        return "frustration"
    if "质量压力" in s or "处方质量" in s or "quality" in s.lower():
        return "quality_pressure"
    return safe_name(s.lower())


METRIC_LABEL = {
    "confidence": "Confidence",
    "info_sufficiency": "Information",
    "decision_certainty": "Certainty",
    "case_workload": "Workload",
    "ai_influence": "AI influence",
    "mental_demand": "Mental load",
    "operation_fatigue": "Fatigue",
    "time_pressure": "Time pressure",
    "effort": "Effort",
    "frustration": "Frustration",
    "quality_pressure": "Quality pressure",
}

LOWER_BETTER = {"case_workload", "mental_demand", "operation_fatigue", "time_pressure", "effort", "frustration", "quality_pressure", "edit_time_sec", "brier", "logloss", "ece", "mae", "aurc"}


def condition_label(code: Any, desc: Any = "") -> str:
    c = str(code).strip().upper()
    if c == "A":
        return "Patient only"
    if c == "B":
        return "+AI plan"
    if c == "C":
        return "+AI+evidence"
    d = str(desc).strip()
    return d[:28] if d else c


def load_hci_data(selected: pd.DataFrame) -> dict[str, pd.DataFrame]:
    tables = {k: [] for k in ["case_level", "case_ratings", "workload", "survey", "timing", "events", "all_metrics", "source_index"]}
    if selected.empty:
        return {k: pd.DataFrame(v) for k, v in tables.items()}
    file_map = {
        "case_level": "04_case_level_wide.csv",
        "case_ratings": "05_case_ratings_long.csv",
        "workload": "07_stage_workload_long.csv",
        "survey": "09_final_survey.csv",
        "timing": "11_timing_metrics.csv",
        "events": "10_event_log.csv",
        "all_metrics": "13_all_metrics_long.csv",
    }
    for _, s in selected.iterrows():
        p = Path(s["path"])
        with zipfile.ZipFile(p) as zf:
            for key, fname in file_map.items():
                rows = zip_csv_rows(zf, fname)
                for row in rows:
                    row["source_zip"] = str(p)
                    row["package_ts"] = s["package_ts"]
                    row["package_name"] = s["package_name"]
                tables[key].extend(rows)
        tables["source_index"].append(s.to_dict())
    out = {k: pd.DataFrame(v) for k, v in tables.items()}
    if not out["case_level"].empty:
        df = out["case_level"]
        rename = {
            "研究编号": "study_id",
            "医生/研究对象显示名": "doctor_label",
            "病例序号": "case_order",
            "病例编号": "case_id",
            "实验阶段": "stage",
            "实验条件代码": "condition_code",
            "实验条件说明": "condition_desc",
            "编辑耗时秒数": "edit_time_sec",
            "自动保存次数": "autosave_count",
            "手动保存次数": "manual_save_count",
            "患者资料查看次数": "patient_view_count",
            "AI方案查看次数": "ai_plan_view_count",
            "推理/MDT查看次数": "mdt_view_count",
            "证据包查看次数": "evidence_view_count",
            "一键复制AI方案次数": "copy_ai_count",
            "对本人最终处方的信心": "confidence",
            "本页资料对制定处方的充分性": "info_sufficiency",
            "对本例治疗决策的把握度": "decision_certainty",
            "制定本例处方的工作负担": "case_workload",
            "AI辅助建议对本人处方的影响程度": "ai_influence",
        }
        df = df.rename(columns=rename)
        for c in ["edit_time_sec", "autosave_count", "manual_save_count", "patient_view_count", "ai_plan_view_count", "mdt_view_count", "evidence_view_count", "copy_ai_count", "confidence", "info_sufficiency", "decision_certainty", "case_workload", "ai_influence"]:
            if c in df.columns:
                df[c] = coerce_numeric(df[c])
        df["condition"] = [condition_label(c, d) for c, d in zip(df.get("condition_code", ""), df.get("condition_desc", ""))]
        out["case_level"] = df
    if not out["case_ratings"].empty:
        df = out["case_ratings"].rename(
            columns={
                "研究编号": "study_id",
                "病例序号": "case_order",
                "病例编号": "case_id",
                "实验阶段": "stage",
                "实验条件代码": "condition_code",
                "实验条件说明": "condition_desc",
                "指标名称": "metric_name",
                "指标值": "metric_value",
            }
        )
        df["metric_code"] = df["metric_name"].map(metric_code)
        df["metric_label"] = df["metric_code"].map(METRIC_LABEL).fillna(df["metric_code"])
        df["metric_value"] = coerce_numeric(df["metric_value"])
        df["condition"] = [condition_label(c, d) for c, d in zip(df.get("condition_code", ""), df.get("condition_desc", ""))]
        out["case_ratings"] = df
    if not out["workload"].empty:
        df = out["workload"].rename(
            columns={
                "研究编号": "study_id",
                "实验阶段": "stage",
                "指标名称": "metric_name",
                "指标值": "metric_value",
            }
        )
        df["metric_code"] = df["metric_name"].map(metric_code)
        df["metric_label"] = df["metric_code"].map(METRIC_LABEL).fillna(df["metric_code"])
        df["metric_value"] = coerce_numeric(df["metric_value"])
        df["stage_label"] = "Stage " + df["stage"].astype(str)
        out["workload"] = df
    if not out["survey"].empty:
        df = out["survey"].rename(
            columns={
                "研究编号": "study_id",
                "整体系统接受度": "system_acceptance",
                "未来使用意愿": "future_use",
                "总体临床有用性": "clinical_usefulness",
                "开放性意见": "open_comment",
            }
        )
        for c in ["system_acceptance", "future_use", "clinical_usefulness"]:
            if c in df.columns:
                df[c] = coerce_numeric(df[c])
        out["survey"] = df
    if not out["timing"].empty:
        df = out["timing"].rename(
            columns={
                "研究编号": "study_id",
                "对象类型": "object_type",
                "对象ID": "object_id",
                "实验阶段": "stage",
                "实验条件代码": "condition_code",
                "耗时秒数": "duration_sec",
                "相关事件数": "event_count",
            }
        )
        for c in ["duration_sec", "event_count"]:
            if c in df.columns:
                df[c] = coerce_numeric(df[c])
        df["condition"] = df.get("condition_code", "").map(condition_label) if "condition_code" in df.columns else ""
        out["timing"] = df
    return out


def load_oaknet_metrics() -> dict[str, pd.DataFrame]:
    oak = ROOT / "OAKNet_Reproducibility_Audit_202606"
    metrics_path = oak / "00_unzipped" / "01_OAKNet_Curves_Replot_202606_complete" / "OAKNet_Curves_Replot_202606" / "03_metrics_history_audit" / "metrics_inventory.csv"
    if not metrics_path.exists():
        metrics_paths = list(oak.rglob("metrics_inventory.csv"))
        metrics_path = metrics_paths[0] if metrics_paths else Path()
    metrics = read_csv_smart(metrics_path) if metrics_path.exists() else pd.DataFrame()
    if not metrics.empty:
        source_records.append({"module": "OAKNet", "source": str(metrics_path), "rows": len(metrics), "status": "loaded"})
    histories = []
    for p in oak.rglob("history.json"):
        try:
            obj = read_json_smart(p)
            if isinstance(obj, list):
                df = pd.DataFrame(obj)
            elif isinstance(obj, dict):
                if all(isinstance(v, list) for v in obj.values()):
                    df = pd.DataFrame(obj)
                else:
                    df = pd.DataFrame([obj])
            else:
                continue
            m = re.search(r"[\\/](A\d|B\d)[\\/]fold(\d+)", str(p))
            df["arm"] = m.group(1) if m else ""
            df["fold"] = int(m.group(2)) if m else np.nan
            if "epoch" not in df.columns:
                df["epoch"] = np.arange(1, len(df) + 1)
            df["source_path"] = str(p)
            histories.append(df)
        except Exception as exc:
            blocked_records.append({"module": "OAKNet", "item": str(p), "status": f"history_parse_failed:{exc}"})
    history = pd.concat(histories, ignore_index=True) if histories else pd.DataFrame()
    return {"metrics": metrics, "history": history}


def plot_oaknet(oak: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    metrics = oak["metrics"].copy()
    history = oak["history"].copy()
    outputs: dict[str, pd.DataFrame] = {}
    if metrics.empty:
        blocked_records.append({"module": "OAKNet", "item": "metrics inventory", "status": "missing"})
        return outputs
    numeric_metrics = ["qwk", "acc", "bacc", "f1_macro", "mae", "ece", "brier", "sel_acc@80", "sel_acc@90", "aurc", "abst_auroc", "loss"]
    for c in numeric_metrics:
        if c in metrics.columns:
            metrics[c] = coerce_numeric(metrics[c])
    summary = (
        metrics.groupby(["arm", "split"], dropna=False)[[c for c in numeric_metrics if c in metrics.columns]]
        .agg(["mean", "std", "count"])
        .reset_index()
    )
    summary.columns = ["_".join([str(x) for x in col if x]) for col in summary.columns.values]
    outputs["oaknet_metrics_summary"] = summary
    metrics.to_csv(SRC / "oaknet_metrics_inventory_used.csv", index=False, encoding="utf-8-sig")

    metric_specs = [
        ("qwk", "QWK", "higher"),
        ("bacc", "Bal acc", "higher"),
        ("f1_macro", "Macro F1", "higher"),
        ("sel_acc@80", "Sel acc", "higher"),
        ("abst_auroc", "Abst AUROC", "higher"),
        ("mae", "MAE score", "lower"),
        ("ece", "ECE score", "lower"),
        ("brier", "Brier score", "lower"),
        ("aurc", "AURC score", "lower"),
    ]
    for split in ["external", "internal", "val"]:
        sub = metrics[metrics["split"].astype(str).str.lower() == split].copy()
        if sub.empty:
            continue
        mean = sub.groupby("arm")[[m for m, _, _ in metric_specs if m in sub.columns]].mean().reset_index()
        radar = normalise_for_radar(mean, "arm", [(m, l, d) for m, l, d in metric_specs if m in mean.columns])
        outputs[f"oaknet_radar_{split}"] = radar
        radar_plot(radar, "arm", "prediction_radar", f"oaknet_{split}_all_model_same_direction_radar", note="Lower-better metrics inverted by min-max normalisation.")
        if len(radar) > 8:
            radar_plot(radar[radar["arm"].astype(str).str.startswith("A")], "arm", "prediction_radar", f"oaknet_{split}_A_series_same_direction_radar", note="A-series only.")
            radar_plot(radar[radar["arm"].astype(str).str.startswith("B")], "arm", "prediction_radar", f"oaknet_{split}_B_series_same_direction_radar", note="B-series only.")
        for metric in [m for m in numeric_metrics if m in sub.columns and m != "loss"]:
            low = metric in LOWER_BETTER
            bar_df = sub.groupby("arm")[metric].agg(["mean", "sem", "count"]).reset_index().rename(columns={"mean": metric, "sem": f"{metric}_sem"})
            for mode in ["dynamic", "zero"]:
                horizontal_bar(bar_df, "arm", metric, "oaknet_metric_bars", f"oaknet_{split}_{safe_name(metric)}", metric, mode, lower_better=low, err_col=f"{metric}_sem")

    if not history.empty:
        for c in history.columns:
            if c not in ["arm", "fold", "source_path"]:
                history[c] = pd.to_numeric(history[c], errors="ignore")
        num_cols = []
        for c in history.columns:
            if c in ["epoch", "fold"] or c.endswith("_path"):
                continue
            if pd.api.types.is_numeric_dtype(history[c]) and history[c].notna().sum() >= 10:
                num_cols.append(c)
        wanted = [c for c in num_cols if any(k in c.lower() for k in ["loss", "acc", "qwk", "f1", "mae", "ece", "brier", "kappa"])]
        wanted = wanted[:18] if wanted else num_cols[:18]
        outputs["oaknet_training_history_long"] = history
        history.to_csv(SRC / "oaknet_training_history_long.csv", index=False, encoding="utf-8-sig")
        for metric in wanted:
            for family, fam_df in [("A_series", history[history["arm"].astype(str).str.startswith("A")]), ("B_series", history[history["arm"].astype(str).str.startswith("B")])]:
                if fam_df.empty:
                    continue
                agg = fam_df.groupby(["arm", "epoch"])[metric].agg(["mean", "sem", "count"]).reset_index()
                if agg["mean"].notna().sum() < 3:
                    continue
                for axis_mode in ["dynamic", "zero"]:
                    fig, ax = plt.subplots(figsize=(7.4, 4.5))
                    vals = []
                    for i, (arm, g) in enumerate(agg.groupby("arm")):
                        g = g.sort_values("epoch")
                        ax.plot(g["epoch"], g["mean"], label=str(arm), color=PALETTE[i % len(PALETTE)], linewidth=1.4)
                        if g["sem"].notna().sum() > 0:
                            ax.fill_between(g["epoch"], g["mean"] - g["sem"], g["mean"] + g["sem"], color=PALETTE[i % len(PALETTE)], alpha=0.08)
                        vals.extend(g["mean"].dropna().tolist())
                    ax.set_xlabel("Epoch")
                    ax.set_ylabel(wrap_label(metric, 24))
                    ax.legend(frameon=False, ncol=min(4, agg["arm"].nunique()), loc="best")
                    set_numeric_axis(ax, vals, axis_mode, "y")
                    save_fig(fig, "training_curves", f"oaknet_{family}_{safe_name(metric)}_training_curve_{axis_mode}", agg, axis_mode=axis_mode)
    else:
        blocked_records.append({"module": "OAKNet", "item": "training history curves", "status": "no parseable history.json"})
    return outputs


def load_komrisk_tables() -> dict[str, pd.DataFrame]:
    dirs = [p for p in ROOT.rglob("koa_paper_v5") if p.is_dir() and (p / "figure_data").exists()]
    if not dirs:
        blocked_records.append({"module": "KOM-Risk", "item": "koa_paper_v5 figure data", "status": "missing"})
        return {}
    base = dirs[0]
    source_records.append({"module": "KOM-Risk", "source": str(base), "rows": "", "status": "loaded"})
    tables = {}
    for p in list((base / "figure_data").glob("*.csv")) + list((base / "tables").glob("*.csv")) + list((base / "supplementary").glob("*.csv")):
        try:
            tables[p.stem] = read_csv_smart(p, comment="#")
        except Exception as exc:
            blocked_records.append({"module": "KOM-Risk", "item": str(p), "status": f"csv_parse_failed:{exc}"})
    return tables


def plot_komrisk(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    outputs = {}
    if not tables:
        return outputs
    table2 = tables.get("table2_performance_by_mode", pd.DataFrame()).copy()
    if not table2.empty:
        for c in ["AUROC", "AUPRC", "Brier", "N features"]:
            if c in table2.columns:
                table2[c] = coerce_numeric(table2[c])
        outputs["komrisk_mode_performance"] = table2
        for metric in ["AUROC", "AUPRC", "Brier", "N features"]:
            if metric not in table2.columns:
                continue
            for outcome in table2["Outcome"].dropna().unique():
                sub = table2[table2["Outcome"] == outcome].copy()
                if sub[metric].notna().sum() == 0:
                    continue
                for mode in ["dynamic", "zero"]:
                    horizontal_bar(sub, "Mode", metric, "komrisk_prediction_bars", f"komrisk_{safe_name(outcome)}_{safe_name(metric)}", metric, mode, lower_better=metric in ["Brier", "N features"])
    s5 = tables.get("tableS5_per_fold_metrics", pd.DataFrame()).copy()
    if not s5.empty and "outcome" in s5.columns:
        outputs["komrisk_per_fold_metrics"] = s5
        models = ["xgb", "lgb", "cat", "stack"]
        for model in models:
            for metric in ["auroc", "auprc", "brier", "logloss", "sens_at_spec90"]:
                col = f"{model}_{metric}"
                if col in s5.columns:
                    s5[col] = coerce_numeric(s5[col])
        for outcome in s5["outcome"].dropna().unique():
            rows = []
            sub = s5[s5["outcome"] == outcome]
            for model in models:
                row = {"model": model.upper()}
                for metric in ["auroc", "auprc", "brier", "logloss", "sens_at_spec90"]:
                    col = f"{model}_{metric}"
                    if col in sub.columns:
                        row[metric] = sub[col].mean()
                rows.append(row)
            mean = pd.DataFrame(rows)
            specs = [
                ("auroc", "AUROC", "higher"),
                ("auprc", "AUPRC", "higher"),
                ("sens_at_spec90", "Sens@Sp90", "higher"),
                ("brier", "Brier score", "lower"),
                ("logloss", "Logloss score", "lower"),
            ]
            radar = normalise_for_radar(mean, "model", [(m, l, d) for m, l, d in specs if m in mean.columns])
            outputs[f"komrisk_radar_{outcome}"] = radar
            radar_plot(radar, "model", "prediction_radar", f"komrisk_{safe_name(outcome)}_model_same_direction_radar", note="Brier and logloss inverted.")
    shap = tables.get("tableS6_shap_top20", tables.get("data_fig5_clinical_predictors", pd.DataFrame())).copy()
    if not shap.empty:
        if "mean_abs_shap" not in shap.columns and "Mean_absolute_SHAP_value" in shap.columns:
            shap = shap.rename(columns={"Mean_absolute_SHAP_value": "mean_abs_shap", "Feature": "feature", "Outcome": "outcome"})
        if {"outcome", "feature", "mean_abs_shap"}.issubset(shap.columns):
            shap["mean_abs_shap"] = coerce_numeric(shap["mean_abs_shap"])
            outputs["komrisk_shap_top"] = shap
            for outcome, sub in shap.groupby("outcome"):
                top = sub.sort_values("mean_abs_shap", ascending=False).head(15)
                for mode in ["dynamic", "zero"]:
                    horizontal_bar(top, "feature", "mean_abs_shap", "komrisk_shap", f"komrisk_{safe_name(outcome)}_shap_top15", "Mean |SHAP|", mode)
    threshold = tables.get("tableS4_threshold_metrics", pd.DataFrame()).copy()
    if not threshold.empty and {"outcome", "model", "threshold"}.issubset(threshold.columns):
        for c in ["sensitivity", "specificity", "ppv", "npv", "f1", "flag_rate"]:
            if c in threshold.columns:
                threshold[c] = coerce_numeric(threshold[c])
        threshold["threshold"] = coerce_numeric(threshold["threshold"])
        outputs["komrisk_threshold_metrics"] = threshold
        for outcome in threshold["outcome"].dropna().unique():
            sub = threshold[threshold["outcome"] == outcome]
            for metric in ["sensitivity", "specificity", "ppv", "npv", "f1", "flag_rate"]:
                if metric not in sub.columns:
                    continue
                fig, ax = plt.subplots(figsize=(6.6, 4.0))
                vals = []
                for i, (model, g) in enumerate(sub.groupby("model")):
                    g = g.sort_values("threshold")
                    ax.plot(g["threshold"], g[metric], marker="o", markersize=3, label=str(model).upper(), color=PALETTE[i % len(PALETTE)])
                    vals.extend(g[metric].dropna().tolist())
                ax.set_xlabel("Risk threshold")
                ax.set_ylabel(metric.replace("_", " ").title())
                ax.legend(frameon=False, ncol=min(4, sub["model"].nunique()))
                set_numeric_axis(ax, vals, "zero", "y")
                save_fig(fig, "komrisk_thresholds", f"komrisk_{safe_name(outcome)}_{safe_name(metric)}_threshold_curve_zero", sub, axis_mode="zero")
    dca = tables.get("data_fig4_net_benefit_at_thresholds", pd.DataFrame()).copy()
    if not dca.empty:
        cols = {c.lower(): c for c in dca.columns}
        if {"outcome", "model", "threshold", "net_benefit"}.issubset(cols):
            dca = dca.rename(columns={cols["outcome"]: "outcome", cols["model"]: "model", cols["threshold"]: "threshold", cols["net_benefit"]: "net_benefit"})
            dca["threshold"] = coerce_numeric(dca["threshold"])
            dca["net_benefit"] = coerce_numeric(dca["net_benefit"])
            outputs["komrisk_dca"] = dca
            for outcome, sub in dca.groupby("outcome"):
                fig, ax = plt.subplots(figsize=(6.6, 4.0))
                vals = []
                for i, (model, g) in enumerate(sub.groupby("model")):
                    g = g.sort_values("threshold")
                    ax.plot(g["threshold"], g["net_benefit"], label=str(model), color=PALETTE[i % len(PALETTE)], linewidth=1.4)
                    vals.extend(g["net_benefit"].dropna().tolist())
                ax.set_xlabel("Risk threshold")
                ax.set_ylabel("Net benefit")
                ax.legend(frameon=False, ncol=2)
                set_numeric_axis(ax, vals, "dynamic", "y")
                save_fig(fig, "komrisk_dca", f"komrisk_{safe_name(outcome)}_net_benefit_dynamic", sub, axis_mode="dynamic")
    return outputs


def plot_hci(hci: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    outputs: dict[str, pd.DataFrame] = {}
    ratings = hci.get("case_ratings", pd.DataFrame())
    case = hci.get("case_level", pd.DataFrame())
    workload = hci.get("workload", pd.DataFrame())
    survey = hci.get("survey", pd.DataFrame())
    if not ratings.empty:
        outputs["hci_case_ratings"] = ratings
        summ = ratings.groupby(["metric_code", "metric_label", "condition"])["metric_value"].agg(["mean", "sem", "count"]).reset_index()
        outputs["hci_case_rating_summary"] = summ
        for metric, sub in summ.groupby("metric_code"):
            lower = metric in LOWER_BETTER
            plot_df = sub.rename(columns={"mean": "value"})
            for mode in ["dynamic", "zero"]:
                grouped_bar(plot_df, "condition", "value", None, "hci_case_ratings", f"hci_case_{metric}", METRIC_LABEL.get(metric, metric), mode, lower_better=lower)
        # HCI same-direction radar by condition.
        pivot = summ.pivot_table(index="condition", columns="metric_code", values="mean").reset_index()
        specs = []
        for metric in ["confidence", "info_sufficiency", "decision_certainty", "case_workload", "ai_influence"]:
            if metric in pivot.columns:
                specs.append((metric, METRIC_LABEL.get(metric, metric), "lower" if metric in LOWER_BETTER else "higher"))
        radar = normalise_for_radar(pivot, "condition", specs)
        outputs["hci_condition_radar"] = radar
        radar_plot(radar, "condition", "hci_radar", "hci_condition_same_direction_radar", note="Workload is inverted so all spokes point to better.")
    if not case.empty:
        process_cols = [
            "edit_time_sec",
            "autosave_count",
            "manual_save_count",
            "patient_view_count",
            "ai_plan_view_count",
            "mdt_view_count",
            "evidence_view_count",
            "copy_ai_count",
        ]
        outputs["hci_case_level"] = case
        for col in process_cols:
            if col not in case.columns or case[col].notna().sum() == 0:
                continue
            summ = case.groupby("condition")[col].agg(["mean", "sem", "count"]).reset_index().rename(columns={"mean": "value"})
            outputs[f"hci_process_{col}"] = summ
            for mode in ["dynamic", "zero"]:
                grouped_bar(summ, "condition", "value", None, "hci_process", f"hci_process_{col}", col.replace("_", " ").title(), mode, lower_better=col in LOWER_BETTER)
    if not workload.empty:
        outputs["hci_stage_workload"] = workload
        summ = workload.groupby(["metric_code", "metric_label", "stage_label"])["metric_value"].agg(["mean", "sem", "count"]).reset_index()
        outputs["hci_workload_summary"] = summ
        for metric, sub in summ.groupby("metric_code"):
            plot_df = sub.rename(columns={"mean": "value"})
            for mode in ["dynamic", "zero"]:
                grouped_bar(plot_df, "stage_label", "value", None, "hci_workload", f"hci_workload_{metric}", METRIC_LABEL.get(metric, metric), mode, lower_better=True)
    if not survey.empty:
        outputs["hci_final_survey"] = survey
        long = survey.melt(id_vars=[c for c in ["study_id", "source_zip"] if c in survey.columns], value_vars=[c for c in ["system_acceptance", "future_use", "clinical_usefulness"] if c in survey.columns], var_name="metric", value_name="value")
        long["metric_label"] = long["metric"].map({"system_acceptance": "Acceptance", "future_use": "Future use", "clinical_usefulness": "Usefulness"})
        outputs["hci_final_survey_long"] = long
        for mode in ["dynamic", "zero"]:
            grouped_bar(long, "metric_label", "value", None, "hci_survey", "hci_final_survey", "Likert score", mode)
    return outputs


def plot_source_tables() -> dict[str, pd.DataFrame]:
    outputs = {}
    oak = ROOT / "OAKNet_Reproducibility_Audit_202606"
    source_tables = {}
    key_patterns = [
        "tabs3",
        "backbone",
        "ablation",
        "training_cost",
        "reliability",
        "selective_prediction",
        "metrics_lollipop",
    ]
    skip_patterns = ["confusion_matrix", "demo_case", "manual_correction"]
    for p in oak.rglob("*.csv"):
        low = str(p).lower()
        if any(s in low for s in skip_patterns):
            continue
        if ("source_tables_corrected" in low or "model_comparison" in low) and any(k in low for k in key_patterns):
            key = safe_name(p.stem)
            if key not in source_tables:
                source_tables[key] = p
    for stem, p in source_tables.items():
        try:
            df = read_csv_smart(p)
        except Exception:
            continue
        outputs[f"source_{stem}"] = df
        num_cols = [c for c in df.columns if pd.to_numeric(df[c], errors="coerce").notna().sum() >= 2]
        cat_cols = [c for c in df.columns if c not in num_cols]
        label_col = cat_cols[0] if cat_cols else df.columns[0]
        for metric in num_cols[:5]:
            if metric == label_col:
                continue
            plot_df = df[[label_col, metric]].copy()
            plot_df[metric] = coerce_numeric(plot_df[metric])
            if plot_df[metric].notna().sum() < 2:
                continue
            for mode in ["dynamic", "zero"]:
                horizontal_bar(plot_df, label_col, metric, "oaknet_source_table_bars", f"{stem}_{safe_name(metric)}", str(metric), mode, lower_better=metric.lower() in LOWER_BETTER)
    return outputs


def plot_graph_schematics() -> dict[str, pd.DataFrame]:
    nodes = pd.DataFrame(
        [
            ("Standard cases", 0.08, 0.62, "#D9E8F5"),
            ("KOM-Profile", 0.26, 0.62, "#E2F0E8"),
            ("OAK-Net", 0.26, 0.38, "#F3E6DD"),
            ("KOM-Risk", 0.44, 0.62, "#F0E7F4"),
            ("KOM-RAG", 0.44, 0.38, "#E8EEF6"),
            ("Graph evidence", 0.62, 0.38, "#F5EBD8"),
            ("MDT/Rx", 0.62, 0.62, "#E3EFE6"),
            ("Safety audit", 0.80, 0.62, "#F4E1E0"),
            ("Doctor UI", 0.80, 0.38, "#E9EDF1"),
        ],
        columns=["node", "x", "y", "color"],
    )
    edges = pd.DataFrame(
        [
            ("Standard cases", "KOM-Profile"),
            ("Standard cases", "OAK-Net"),
            ("KOM-Profile", "KOM-Risk"),
            ("OAK-Net", "KOM-Risk"),
            ("KOM-RAG", "Graph evidence"),
            ("Graph evidence", "MDT/Rx"),
            ("KOM-Risk", "MDT/Rx"),
            ("MDT/Rx", "Safety audit"),
            ("Safety audit", "Doctor UI"),
            ("Graph evidence", "Doctor UI"),
        ],
        columns=["source", "target"],
    )
    pos = {r.node: (r.x, r.y) for r in nodes.itertuples()}
    fig, ax = plt.subplots(figsize=(8.8, 4.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0.18, 0.82)
    ax.axis("off")

    def endpoint_pair(source: str, target: str) -> tuple[float, float, float, float]:
        x0, y0 = pos[source]
        x1, y1 = pos[target]
        dx = x1 - x0
        dy = y1 - y0
        if abs(dx) >= abs(dy):
            sx = x0 + (0.082 if dx >= 0 else -0.082)
            ex = x1 - (0.082 if dx >= 0 else -0.082)
            sy = y0
            ey = y1
        else:
            sy = y0 + (0.060 if dy >= 0 else -0.060)
            ey = y1 - (0.060 if dy >= 0 else -0.060)
            sx = x0
            ex = x1
        return sx, sy, ex, ey

    for _, e in edges.iterrows():
        sx, sy, ex, ey = endpoint_pair(e["source"], e["target"])
        ax.annotate(
            "",
            xy=(ex, ey),
            xytext=(sx, sy),
            arrowprops=dict(arrowstyle="-|>", lw=1.0, color="#687078", shrinkA=2, shrinkB=2, connectionstyle="arc3,rad=0.08"),
        )
    for _, n in nodes.iterrows():
        box = patches.FancyBboxPatch(
            (n["x"] - 0.065, n["y"] - 0.045),
            0.13,
            0.09,
            boxstyle="round,pad=0.012,rounding_size=0.012",
            facecolor=n["color"],
            edgecolor="#77808A",
            linewidth=0.9,
        )
        ax.add_patch(box)
        ax.text(n["x"], n["y"], wrap_label(n["node"], 12), ha="center", va="center", fontsize=8)
    source = pd.concat([nodes.assign(kind="node"), edges.assign(kind="edge")], ignore_index=True, sort=False)
    save_fig(fig, "graph_rag_schematics", "kom_graph_rag_pipeline_clean_notitle", source, axis_mode="schematic")
    return {"graph_rag_nodes_edges": source}


def build_methods_result_map(outputs: dict[str, pd.DataFrame], hci_selected: pd.DataFrame) -> pd.DataFrame:
    requirements = [
        ("KOM-Profile", "field extraction accuracy / completeness", "No directly recovered metric table in current files"),
        ("OAK-Net", "QWK, balanced accuracy, macro-F1, MAE, ECE, selective accuracy, training curves", "oaknet_metrics_summary; oaknet_training_history_long"),
        ("KOM-Risk", "AUROC, AUPRC, Brier, calibration, DCA, SHAP, thresholds", "komrisk_mode_performance; komrisk_threshold_metrics; komrisk_shap_top"),
        ("KOM-RAG", "Precision@10, Recall@K, Hit@10, MRR, nDCG@10; generation faithfulness", "No GraphRAG retrieval/generation metric table recovered in project root"),
        ("KOM-Treat", "Full / without RAG / without MDT / Direct LLM ablation", "No treatment-agent judge summary recovered in project root"),
        ("KOM-Sim", "case ratings, workload, process behavior, final survey", "hci_case_ratings; hci_stage_workload; hci_case_level; hci_final_survey"),
        ("KOM-Safe", "safety errors, red flag challenge set", "No dedicated safety challenge result table recovered"),
    ]
    rows = []
    available = set(outputs)
    for module, item, expected in requirements:
        status = "available" if any(k in available for k in expected.split("; ")) else "gap_or_partial"
        if module == "KOM-Sim" and not hci_selected.empty:
            status = "available"
        if module == "OAK-Net" and "oaknet_metrics_summary" in available:
            status = "available"
        if module == "KOM-Risk" and "komrisk_mode_performance" in available:
            status = "available"
        if status != "available":
            blocked_records.append({"module": module, "item": item, "status": "source table not recovered", "detail": expected})
        rows.append({"module": module, "methods_required_result": item, "status": status, "source_or_gap": expected})
    return pd.DataFrame(rows)


def write_master_workbook(outputs: dict[str, pd.DataFrame], methods_map: pd.DataFrame, hci_selected: pd.DataFrame) -> Path:
    path = TABLES / "KOM_Figure_Deep_Optimization_Master_Table_20260615.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        methods_map.to_excel(writer, sheet_name="methods_result_map", index=False)
        pd.DataFrame(source_records).to_excel(writer, sheet_name="source_records", index=False)
        pd.DataFrame(blocked_records).to_excel(writer, sheet_name="blocked_real_gaps", index=False)
        hci_selected.to_excel(writer, sheet_name="hci_selected_zips", index=False)
        for key, df in outputs.items():
            if df is None or df.empty:
                continue
            sheet = safe_name(key)[:31]
            try:
                df.to_excel(writer, sheet_name=sheet, index=False)
            except Exception:
                df.astype(str).to_excel(writer, sheet_name=sheet, index=False)
    return path


def write_audit_report(master_path: Path, methods_map: pd.DataFrame) -> Path:
    fig_df = pd.DataFrame(figure_records)
    fig_df.to_csv(QC / "visual_qc_report.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(source_records).to_csv(QC / "data_source_audit.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(blocked_records).to_csv(QC / "blocked_real_data_gaps.csv", index=False, encoding="utf-8-sig")
    methods_map.to_csv(QC / "methods_result_map.csv", index=False, encoding="utf-8-sig")
    n_pass = int((fig_df["qc_status"] == "PASS").sum()) if not fig_df.empty else 0
    n_review = int((fig_df["qc_status"] == "REVIEW").sum()) if not fig_df.empty else 0
    n_fail = int((fig_df["qc_status"] == "FAIL").sum()) if not fig_df.empty else 0
    report = AUDIT / "KOM_Figure_Deep_Optimization_Audit_Report_20260615.md"
    report.write_text(
        "\n".join(
            [
                "# KOM Figure Deep Optimization Audit",
                "",
                f"- Output folder: `{OUT}`",
                f"- Master table: `{master_path}`",
                f"- Figure files generated: {len(fig_df)} figure records, each exported as PNG/SVG/PDF when applicable.",
                f"- QC: PASS={n_pass}, REVIEW={n_review}, FAIL={n_fail}.",
                "- No-title rule: plotting functions do not set panel titles; file names and source tables carry the semantic label.",
                "- Same-direction radar rule: lower-better metrics are inverted by within-comparison min-max normalization before polar plotting.",
                "- Axis rule: bar/process/metric figures are exported in both dynamic and zero-baseline variants where meaningful.",
                "- Quadrant rule: no Q1/Q2/Q3/Q4 quadrant panel is generated; raw case IDs are not used as figure labels.",
                "",
                "## Methods Result Map",
                methods_map.to_markdown(index=False),
                "",
                "## Remaining Real-Data Gaps",
                pd.DataFrame(blocked_records).to_markdown(index=False) if blocked_records else "No blocked records were added.",
            ]
        ),
        encoding="utf-8",
    )
    return report


def main() -> None:
    try:
        shutil.copy2(Path(__file__), SCRIPTS / Path(__file__).name)
    except Exception:
        pass
    all_outputs: dict[str, pd.DataFrame] = {}
    hci_selected = choose_hci_packages(26)
    hci = load_hci_data(hci_selected)
    all_outputs.update({f"hci_raw_{k}": v for k, v in hci.items() if isinstance(v, pd.DataFrame) and not v.empty})
    oak = load_oaknet_metrics()
    all_outputs.update(plot_oaknet(oak))
    all_outputs.update(plot_komrisk(load_komrisk_tables()))
    all_outputs.update(plot_hci(hci))
    all_outputs.update(plot_source_tables())
    all_outputs.update(plot_graph_schematics())
    methods_map = build_methods_result_map(all_outputs, hci_selected)
    master = write_master_workbook(all_outputs, methods_map, hci_selected)
    report = write_audit_report(master, methods_map)
    print("OUTPUT_FOLDER", OUT)
    print("MASTER_TABLE", master)
    print("AUDIT_REPORT", report)
    print("FIGURE_RECORDS", len(figure_records))
    print("QC_COUNTS", pd.Series([r["qc_status"] for r in figure_records]).value_counts().to_dict() if figure_records else {})


if __name__ == "__main__":
    main()
