from __future__ import annotations

import csv
import ast
import json
import math
import os
import re
import shutil
import textwrap
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import patches
from matplotlib.backends.backend_agg import FigureCanvasAgg
from PIL import Image, ImageStat


ROOT = Path.cwd()
REF_POOL = Path(
    os.environ.get(
        "KOM_REF_POOL",
        "C:/OAI\u7814\u7a76\u9879\u76ee/pythonProject1/"
        "KOM\u8fd4\u4fee\u4fee\u6539/\u6295\u7a3f\u4f7f\u7528/"
        "\u6700\u7ec8\u7248\u672c/KOM_Manuscript_Figures_PNG_SELECTION_POOL_20260615",
    )
)
OUT = REF_POOL.parent / "KOM_Manuscript_Figures_STYLE_MIGRATED_REMAKE_20260615"
DEEP = ROOT / "KOM_Figure_Deep_Optimization_20260615"
MASTER = DEEP / "tables" / "KOM_Figure_Deep_Optimization_Master_Table_20260615.xlsx"
OAK = ROOT / "OAKNet_Reproducibility_Audit_202606"

FIG = OUT / "all_png_one_folder"
VEC = OUT / "editable_svg_pdf"
SRC = OUT / "source_data"
QC = OUT / "qc"
TABLES = OUT / "tables"
AUDIT = OUT / "audit"
STYLE = OUT / "style_learning"
SCRIPTS = OUT / "scripts"

if OUT.exists():
    resolved = OUT.resolve()
    if resolved.name.startswith("KOM_Manuscript_Figures_STYLE_MIGRATED_REMAKE_") and resolved.parent == REF_POOL.parent.resolve():
        shutil.rmtree(resolved, ignore_errors=True)
for d in [FIG, VEC, SRC, QC, TABLES, AUDIT, STYLE, SCRIPTS]:
    d.mkdir(parents=True, exist_ok=True)

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "font.size": 8.2,
        "axes.labelsize": 8.8,
        "xtick.labelsize": 7.8,
        "ytick.labelsize": 7.8,
        "legend.fontsize": 7.5,
        "axes.linewidth": 0.75,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": "#EAF1F5",
        "grid.linewidth": 0.75,
        "axes.axisbelow": True,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "savefig.dpi": 300,
        "figure.dpi": 160,
    }
)

COLORS = {
    "teal_dark": "#285E6F",
    "teal": "#79AFC0",
    "teal_light": "#C9E1E7",
    "mint": "#BFDCCF",
    "mint_dark": "#5E9B85",
    "blue": "#7DA6C8",
    "lavender": "#C7BEDD",
    "rose": "#E2B8B1",
    "sand": "#E7D5A8",
    "ink": "#1B2A34",
    "muted": "#66747E",
    "grid": "#EAF1F5",
    "line": "#9AAAB4",
}
PALETTE = [
    COLORS["teal"],
    COLORS["mint"],
    COLORS["blue"],
    COLORS["lavender"],
    COLORS["rose"],
    COLORS["sand"],
    "#8DB7A8",
    "#A9BDD2",
    "#D6C3D8",
    "#D9B7A1",
    "#6D98AA",
    "#B7D0DA",
]
CONDITION_LABEL = {"A": "Arm A: patient\nmaterials only", "B": "Arm B: patient\nmaterials + AI\nrecommendation", "C": "Arm C: patient\nmaterials + AI +\nevidence/MDT"}
ARM_LABEL = {"A_full": "Full KOM\nworkflow", "B_no_rag": "No evidence\nretrieval", "C_no_mdt": "No MDT\nnegotiation", "D_bare": "Direct model\noutput"}
LOWER_BETTER = {"ece", "expected_calibration_error", "mae", "mean_absolute_error", "brier", "logloss", "loss", "workload", "time", "error", "hallucination", "critical_error", "major_error", "minor_error", "count"}

fig_records: list[dict[str, Any]] = []
source_records: list[dict[str, Any]] = []
qc_records: list[dict[str, Any]] = []


def safe(text: Any, max_len: int = 120) -> str:
    s = re.sub(r"[^0-9A-Za-z._-]+", "_", str(text)).strip("_")
    s = re.sub(r"_+", "_", s)
    return (s or "figure")[:max_len]


def wrap(text: Any, width: int = 18) -> str:
    return "\n".join(textwrap.wrap(str(text).replace("_", " "), width=width, break_long_words=False))


def numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.replace({"—": np.nan, "--": np.nan, "": np.nan}), errors="coerce")


def numeric(s: pd.Series) -> pd.Series:
    replacements = {chr(8212): np.nan, chr(8211): np.nan, "--": np.nan, "": np.nan, "NA": np.nan, "nan": np.nan}
    return pd.to_numeric(s.replace(replacements), errors="coerce")


def parse_metric_dict(value: Any) -> dict[str, float]:
    if isinstance(value, dict):
        data = value
    elif value is None or (isinstance(value, float) and math.isnan(value)):
        return {}
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        if text.startswith("{") and text.endswith("}"):
            try:
                data = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                return {}
        else:
            num = pd.to_numeric(pd.Series([text]), errors="coerce").iloc[0]
            return {"value": float(num)} if pd.notna(num) else {}
    else:
        num = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        return {"value": float(num)} if pd.notna(num) else {}
    out = {}
    for key, val in data.items():
        num = pd.to_numeric(pd.Series([val]), errors="coerce").iloc[0]
        if pd.notna(num):
            out[str(key)] = float(num)
    return out


def expand_training_history(history: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in history.iterrows():
        for phase in ["train", "val"]:
            if phase not in history.columns:
                continue
            for metric, value in parse_metric_dict(row.get(phase)).items():
                rows.append(
                    {
                        "arm": row.get("arm"),
                        "fold": row.get("fold"),
                        "epoch": row.get("epoch"),
                        "phase": phase,
                        "metric": metric,
                        "value": value,
                    }
                )
    return pd.DataFrame(rows)


def read_csv(path: Path) -> pd.DataFrame:
    for enc in ["utf-8-sig", "utf-8", "gb18030", "gbk"]:
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, encoding="utf-8", errors="replace")


def save_source(df: pd.DataFrame, name: str) -> Path:
    p = SRC / f"{safe(name)}_source.csv"
    df.to_csv(p, index=False, encoding="utf-8-sig")
    return p


def text_overlap(fig: plt.Figure) -> tuple[str, str]:
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    boxes = []
    for txt in fig.findobj(match=matplotlib.text.Text):
        if not txt.get_visible():
            continue
        t = txt.get_text()
        if not t or not t.strip():
            continue
        try:
            b = txt.get_window_extent(renderer=renderer).expanded(1.015, 1.05)
        except Exception:
            continue
        if b.width * b.height > 15:
            boxes.append((t, b))
    n = 0
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i][1], boxes[j][1]
            ix = max(0, min(a.x1, b.x1) - max(a.x0, b.x0))
            iy = max(0, min(a.y1, b.y1) - max(a.y0, b.y0))
            if ix * iy > 8:
                n += 1
    return ("PASS", "no_text_overlap") if n == 0 else ("REVIEW", f"text_overlap_pairs={n}")


def image_qc(path: Path) -> tuple[str, str]:
    try:
        with Image.open(path) as im:
            stat = ImageStat.Stat(im.convert("L"))
            std = float(stat.stddev[0])
            if im.width < 1000 or im.height < 700:
                return "REVIEW", f"small:{im.width}x{im.height}"
            if std < 1.2:
                return "FAIL", "near_blank"
            return "PASS", f"{im.width}x{im.height};std={std:.2f}"
    except Exception as e:
        return "FAIL", f"image_error:{e}"


def save_fig(fig: plt.Figure, name: str, category: str, df: pd.DataFrame | None = None, note: str = "") -> None:
    base = safe(f"{category}__{name}")
    png = FIG / f"{base}.png"
    svg = VEC / f"{base}.svg"
    pdf = VEC / f"{base}.pdf"
    fig.subplots_adjust(top=0.96)
    tqc, tnote = text_overlap(fig)
    fig.savefig(png, bbox_inches="tight", facecolor="white")
    fig.savefig(svg, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf, bbox_inches="tight", facecolor="white")
    src = save_source(df, base) if df is not None else None
    iqc, inote = image_qc(png)
    status = "PASS" if tqc == "PASS" and iqc == "PASS" else ("FAIL" if "FAIL" in [tqc, iqc] else "REVIEW")
    rec = {
        "figure_id": base,
        "category": category,
        "png": str(png),
        "svg": str(svg),
        "pdf": str(pdf),
        "source_data": str(src) if src else "",
        "qc_status": status,
        "qc_notes": "; ".join([tnote, inote, note]).strip("; "),
    }
    fig_records.append(rec)
    qc_records.append(rec.copy())
    plt.close(fig)


def set_axis(ax: plt.Axes, values: pd.Series | list[float], mode: str, axis: str = "y") -> None:
    vals = pd.Series(values, dtype="float64").dropna()
    if vals.empty:
        return
    lo, hi = float(vals.min()), float(vals.max())
    span = hi - lo if hi > lo else max(abs(hi), 1.0) * 0.12
    if mode == "zero":
        lo2 = min(0, lo - 0.05 * span)
        hi2 = hi + 0.13 * span
    else:
        lo2 = lo - 0.18 * span
        hi2 = hi + 0.18 * span
    if axis == "y":
        ax.set_ylim(lo2, hi2)
    else:
        ax.set_xlim(lo2, hi2)


def style_axes(ax: plt.Axes) -> None:
    ax.tick_params(axis="both", colors=COLORS["ink"], width=0.7, length=3)
    ax.xaxis.label.set_color(COLORS["ink"])
    ax.yaxis.label.set_color(COLORS["ink"])
    for sp in ["left", "bottom"]:
        ax.spines[sp].set_color("#6F7C85")
        ax.spines[sp].set_linewidth(0.75)


def infer_label_column(df: pd.DataFrame) -> str:
    preferred = ["model", "arm_code", "condition", "method", "algorithm_label", "algorithm", "metric", "feature", "Mode", "Outcome", "arm", "stage_label"]
    for c in preferred:
        if c in df.columns:
            return c
    for c in df.columns:
        if numeric(df[c]).notna().sum() < max(2, len(df) // 2):
            return c
    return df.columns[0]


def pretty_labels(vals: list[Any], col: str) -> list[str]:
    out = []
    for v in vals:
        s = str(v)
        if col == "condition":
            s = CONDITION_LABEL.get(s, s)
        elif col == "arm_code":
            s = ARM_LABEL.get(s, s)
        out.append(wrap(s, 14))
    return out


def is_lower_better(metric: str) -> bool:
    m = metric.lower()
    return any(k in m for k in LOWER_BETTER)


def bar_mean_sd(df: pd.DataFrame, label_col: str, value_col: str, err_col: str | None, name: str, category: str, mode: str = "dynamic", y_label: str | None = None) -> None:
    d = df.copy()
    d[value_col] = numeric(d[value_col])
    if err_col and err_col in d.columns:
        d[err_col] = numeric(d[err_col])
    d = d.dropna(subset=[label_col, value_col])
    if d.empty:
        return
    d = d.sort_values(value_col, ascending=is_lower_better(value_col) or is_lower_better(name))
    fig, ax = plt.subplots(figsize=(8.8, 5.25))
    x = np.arange(len(d))
    vals = d[value_col].to_numpy(float)
    errs = d[err_col].to_numpy(float) if err_col and err_col in d.columns else None
    colors = [PALETTE[i % len(PALETTE)] for i in range(len(d))]
    ax.bar(x, vals, color=colors, edgecolor="white", linewidth=0.8, alpha=0.92, yerr=errs, capsize=3, ecolor=COLORS["teal_dark"])
    for xi, yi in zip(x, vals):
        ax.text(xi, yi, f"{yi:.3g}", ha="center", va="bottom", fontsize=6.8, color=COLORS["ink"])
    ax.set_xticks(x)
    ax.set_xticklabels(pretty_labels(d[label_col].tolist(), label_col))
    ax.set_ylabel(y_label or value_col.replace("_", " "))
    if is_lower_better(value_col) or is_lower_better(name):
        ax.text(0.01, 0.98, "Lower is better", transform=ax.transAxes, ha="left", va="top", fontsize=7, color=COLORS["muted"])
    set_axis(ax, d[value_col], mode, "y")
    style_axes(ax)
    save_fig(fig, f"{name}_{mode}", category, d, note=f"axis={mode}")


def box_strip(df: pd.DataFrame, group_col: str, value_col: str, name: str, category: str, y_label: str | None = None) -> None:
    d = df.copy()
    d[value_col] = numeric(d[value_col])
    d = d.dropna(subset=[group_col, value_col])
    if d.empty:
        return
    groups = list(d[group_col].dropna().astype(str).unique())
    data = [d[d[group_col].astype(str) == g][value_col].to_numpy(float) for g in groups]
    fig, ax = plt.subplots(figsize=(8.8, 5.25))
    bp = ax.boxplot(data, patch_artist=True, widths=0.52, showfliers=False, medianprops={"color": COLORS["ink"], "linewidth": 1.0})
    for i, patch in enumerate(bp["boxes"]):
        patch.set_facecolor(PALETTE[i % len(PALETTE)])
        patch.set_alpha(0.35)
        patch.set_edgecolor(COLORS["teal_dark"])
    rng = np.random.default_rng(20260615)
    for i, vals in enumerate(data, start=1):
        if len(vals) > 220:
            vals = rng.choice(vals, size=220, replace=False)
        jitter = rng.normal(i, 0.055, size=len(vals))
        ax.scatter(jitter, vals, s=9, alpha=0.42, color=PALETTE[(i - 1) % len(PALETTE)], edgecolors="none")
        ax.scatter([i], [np.nanmean(vals)], s=32, color=COLORS["ink"], zorder=5)
    ax.set_xticks(range(1, len(groups) + 1))
    ax.set_xticklabels(pretty_labels(groups, group_col))
    ax.set_ylabel(y_label or value_col.replace("_", " "))
    set_axis(ax, d[value_col], "dynamic", "y")
    style_axes(ax)
    save_fig(fig, name, category, d)


def radar(df: pd.DataFrame, id_col: str, metrics: list[tuple[str, str, str]], name: str, category: str) -> None:
    if not metrics:
        return
    rows = []
    for _, r in df.iterrows():
        row = {id_col: r[id_col]}
        for col, label, direction in metrics:
            vals = numeric(df[col])
            raw = pd.to_numeric(pd.Series([r[col]]), errors="coerce").iloc[0]
            if pd.isna(raw) or vals.dropna().empty:
                score = np.nan
            elif abs(vals.max() - vals.min()) < 1e-12:
                score = 1.0
            elif direction == "lower":
                score = (vals.max() - raw) / (vals.max() - vals.min())
            else:
                score = (raw - vals.min()) / (vals.max() - vals.min())
            row[label] = float(score) if not pd.isna(score) else np.nan
            row[f"raw_{col}"] = raw
            row[f"direction_{col}"] = direction
        rows.append(row)
    rd = pd.DataFrame(rows)
    labels = [m[1] for m in metrics]
    rd["overall"] = rd[labels].mean(axis=1)
    rd = rd.sort_values("overall", ascending=False)
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    angles += angles[:1]
    fig = plt.figure(figsize=(7.2, 6.2))
    ax = plt.subplot(111, polar=True)
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.50, 0.75, 1.00])
    ax.set_yticklabels(["0.25", "0.50", "0.75", "1.00"], fontsize=7, color=COLORS["muted"])
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([wrap(x, 12) for x in labels], fontsize=8)
    ax.grid(color=COLORS["grid"], linewidth=0.8)
    for i, (_, r) in enumerate(rd.iterrows()):
        vals = [r[l] for l in labels] + [r[labels[0]]]
        lw = 2.2 if i == 0 else 1.2
        alpha = 0.24 if i == 0 else 0.06
        color = PALETTE[i % len(PALETTE)]
        ax.plot(angles, vals, color=color, lw=lw, label=str(r[id_col]))
        ax.fill(angles, vals, color=color, alpha=alpha)
    ax.legend(loc="center left", bbox_to_anchor=(1.08, 0.5), frameon=False)
    save_fig(fig, name, category, rd, note="same-direction min-max radar")


def confusion_matrix_plot(csv_path: Path, name: str, normalized: bool) -> None:
    df = read_csv(csv_path)
    # First column may be true label or unnamed index.
    if df.columns[0].lower().startswith("unnamed") or "true" in df.columns[0].lower() or "reference" in df.columns[0].lower():
        mat = df.iloc[:, 1:].apply(pd.to_numeric, errors="coerce").to_numpy(float)
        ylabels = df.iloc[:, 0].astype(str).tolist()
    else:
        mat = df.apply(pd.to_numeric, errors="coerce").to_numpy(float)
        ylabels = [str(i) for i in range(mat.shape[0])]
    xlabels = [str(i).replace("Predicted_", "").replace("KL_", "KL ") for i in range(mat.shape[1])]
    fig, ax = plt.subplots(figsize=(5.4, 5.2))
    im = ax.imshow(mat, cmap="Blues", vmin=0, vmax=1 if normalized else None)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            val = mat[i, j]
            txt = f"{val:.2f}" if normalized else f"{int(round(val))}"
            ax.text(j, i, txt, ha="center", va="center", fontsize=7, color="white" if val > (0.55 if normalized else np.nanmax(mat) * 0.55) else COLORS["ink"])
    ax.set_xticks(np.arange(mat.shape[1]))
    ax.set_yticks(np.arange(mat.shape[0]))
    ax.set_xticklabels([f"KL {i}" for i in range(mat.shape[1])])
    ax.set_yticklabels([f"KL {i}" for i in range(mat.shape[0])])
    ax.set_xlabel("Predicted KL grade")
    ax.set_ylabel("Reference KL grade")
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cb.ax.tick_params(labelsize=7)
    ax.grid(False)
    save_fig(fig, name, "confusion_matrices", df, note="normalized" if normalized else "counts")


def reference_inventory() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    png_rows = []
    for sub in ["no_titles", "with_titles", "ALL_PNG_SELECTION_POOL", "legacy_imported_png", "qa_contact_sheets"]:
        d = REF_POOL / sub
        if not d.exists():
            continue
        for p in sorted(d.glob("*.png")):
            try:
                with Image.open(p) as im:
                    png_rows.append({"folder": sub, "file": p.name, "path": str(p), "width": im.width, "height": im.height, "size_bytes": p.stat().st_size})
            except Exception as e:
                png_rows.append({"folder": sub, "file": p.name, "path": str(p), "error": repr(e)})
    png_df = pd.DataFrame(png_rows)
    manifest = read_csv(REF_POOL / "figure_manifest_qc.csv") if (REF_POOL / "figure_manifest_qc.csv").exists() else pd.DataFrame()
    long_rows = []
    src_dir = REF_POOL / "plot_source_tables"
    for p in sorted(src_dir.glob("*.csv")) if src_dir.exists() else []:
        try:
            df = read_csv(p)
            source_records.append({"source_file": p.name, "rows": len(df), "columns": "|".join(df.columns), "path": str(p)})
            for idx, row in df.iterrows():
                for col, val in row.items():
                    long_rows.append({"source_file": p.name, "row_index": idx, "field": col, "value": val})
        except Exception as e:
            source_records.append({"source_file": p.name, "error": repr(e), "path": str(p)})
    return png_df, manifest, pd.DataFrame(long_rows)


def remake_reference_source_figures() -> dict[str, pd.DataFrame]:
    outputs = {}
    src_dir = REF_POOL / "plot_source_tables"
    if not src_dir.exists():
        return outputs
    for p in sorted(src_dir.glob("*.csv")):
        df = read_csv(p)
        outputs[f"legacy_{safe(p.stem)}"] = df
        label = infer_label_column(df)
        value_col = "mean" if "mean" in df.columns else None
        if value_col is None:
            nums = [c for c in df.columns if numeric(df[c]).notna().sum() >= 2]
            value_col = nums[0] if nums else None
        if value_col is None:
            continue
        err_col = "sd" if "sd" in df.columns else ("std" if "std" in df.columns else None)
        metric_name = p.stem.replace("_source", "")
        for mode in ["dynamic", "zero"]:
            bar_mean_sd(df, label, value_col, err_col, metric_name, "legacy_style_remake", mode=mode, y_label=value_col)
        if any(k in metric_name.lower() for k in ["confidence", "workload", "overall_quality", "safety", "actionability"]):
            box_strip(df, label, value_col, f"{metric_name}_box_style", "legacy_style_remake", y_label=value_col)
    return outputs


def remake_oaknet_from_master(xl: pd.ExcelFile) -> dict[str, pd.DataFrame]:
    outputs = {}
    metrics = pd.read_excel(xl, "oaknet_metrics_summary") if "oaknet_metrics_summary" in xl.sheet_names else pd.DataFrame()
    if not metrics.empty:
        outputs["oaknet_metrics_summary"] = metrics
        metric_map = [
            ("qwk_mean", "QWK"),
            ("bacc_mean", "Balanced accuracy"),
            ("f1_macro_mean", "Macro F1"),
            ("mae_mean", "Mean absolute error"),
            ("ece_mean", "Expected calibration error"),
            ("sel_acc@80_mean", "Selective accuracy at 80% coverage"),
        ]
        for split in ["external", "internal", "val"]:
            sub = metrics[metrics["split"].astype(str) == split]
            if sub.empty:
                continue
            for col, label in metric_map:
                if col not in sub.columns:
                    continue
                d = sub[["arm", col, col.replace("_mean", "_std") if col.replace("_mean", "_std") in sub.columns else col]].copy()
                d.columns = ["model", "mean", "sd"]
                for mode in ["dynamic", "zero"]:
                    bar_mean_sd(d, "model", "mean", "sd", f"KOMRad_{split}_{safe(label)}", "oaknet_model_ranking", mode=mode, y_label=label)
            rd = sub[["arm"] + [m[0] for m in metric_map if m[0] in sub.columns]].copy()
            radar_specs = [(m[0], m[1].replace("Expected calibration error", "ECE score").replace("Mean absolute error", "MAE score"), "lower" if is_lower_better(m[1]) else "higher") for m in metric_map if m[0] in rd.columns]
            radar(rd, "arm", radar_specs, f"KOMRad_{split}_same_direction_radar", "prediction_radar")
    history = pd.read_excel(xl, "oaknet_training_history_long") if "oaknet_training_history_long" in xl.sheet_names else pd.DataFrame()
    if not history.empty and {"arm", "epoch"}.issubset(history.columns):
        outputs["oaknet_training_history_long"] = history
        expanded = expand_training_history(history)
        if not expanded.empty:
            outputs["oaknet_training_metrics_long"] = expanded
            metric_labels = {
                "loss": "Loss",
                "qwk": "QWK",
                "acc": "Accuracy",
                "bacc": "Balanced accuracy",
                "f1_macro": "Macro F1",
                "mae": "Mean absolute error",
                "ece": "Expected calibration error",
                "brier": "Brier score",
                "sel_acc@80": "Selective accuracy at 80% coverage",
                "sel_acc@90": "Selective accuracy at 90% coverage",
                "aurc": "AURC",
                "abst_auroc": "Abstention AUROC",
            }
            metric_order = [m for m in metric_labels if m in set(expanded["metric"])]
            for phase in ["train", "val"]:
                for metric in metric_order:
                    sub = expanded[(expanded["phase"] == phase) & (expanded["metric"] == metric)]
                    if sub.empty:
                        continue
                    agg = sub.groupby(["arm", "epoch"], as_index=False)["value"].mean()
                    for mode in ["dynamic", "zero"]:
                        fig, ax = plt.subplots(figsize=(9.2, 5.5))
                        for i, (arm, g) in enumerate(agg.groupby("arm")):
                            ax.plot(g["epoch"], g["value"], lw=1.25, color=PALETTE[i % len(PALETTE)], label=str(arm), alpha=0.9)
                        ax.set_xlabel("Epoch")
                        ax.set_ylabel(f"{phase.capitalize()} {metric_labels.get(metric, metric)}")
                        ax.legend(frameon=False, ncol=6, loc="lower center", bbox_to_anchor=(0.5, -0.29))
                        set_axis(ax, agg["value"], mode)
                        style_axes(ax)
                        save_fig(
                            fig,
                            f"KOMRad_{phase}_{safe(metric)}_trajectories_all_models_{mode}",
                            "training_metric_curves",
                            agg.assign(phase=phase, metric=metric),
                            note=f"{phase} {metric}",
                        )
            paired_metrics = ["loss", "qwk", "bacc", "f1_macro", "mae", "ece", "brier"]
            for arm in sorted(expanded["arm"].dropna().astype(str).unique()):
                arm_df = expanded[expanded["arm"].astype(str) == arm]
                for metric in [m for m in paired_metrics if m in set(arm_df["metric"])]:
                    g = arm_df[arm_df["metric"] == metric].groupby(["epoch", "phase"], as_index=False)["value"].mean()
                    if g["phase"].nunique() < 2:
                        continue
                    for mode in ["dynamic", "zero"]:
                        fig, ax = plt.subplots(figsize=(7.4, 4.85))
                        for phase, color in [("train", COLORS["teal_dark"]), ("val", COLORS["rose"])]:
                            gg = g[g["phase"] == phase]
                            ax.plot(gg["epoch"], gg["value"], color=color, lw=1.8, label=phase.capitalize())
                        ax.set_xlabel("Epoch")
                        ax.set_ylabel(metric_labels.get(metric, metric))
                        ax.legend(frameon=False, loc="best")
                        set_axis(ax, g["value"], mode)
                        style_axes(ax)
                        save_fig(
                            fig,
                            f"KOMRad_{arm}_{safe(metric)}_train_val_{mode}",
                            "training_single_model_curves",
                            g.assign(arm=arm, metric=metric),
                            note=f"{arm} {metric}",
                        )
    # Confusion matrices from audited recomputation.
    cdir = OAK / "05_recomputed_figures" / "confusion_matrices"
    if cdir.exists():
        for p in sorted(cdir.glob("*confusion_counts.csv")):
            confusion_matrix_plot(p, p.stem, normalized=False)
        for p in sorted(cdir.glob("*confusion_normalized.csv")):
            confusion_matrix_plot(p, p.stem, normalized=True)
    return outputs


def remake_hci_from_master(xl: pd.ExcelFile) -> dict[str, pd.DataFrame]:
    outputs = {}
    case = pd.read_excel(xl, "hci_case_level") if "hci_case_level" in xl.sheet_names else pd.DataFrame()
    ratings = pd.read_excel(xl, "hci_case_ratings") if "hci_case_ratings" in xl.sheet_names else pd.DataFrame()
    workload = pd.read_excel(xl, "hci_stage_workload") if "hci_stage_workload" in xl.sheet_names else pd.DataFrame()
    if not ratings.empty:
        outputs["hci_case_ratings"] = ratings
        for metric, g in ratings.groupby("metric_code"):
            ylabel = str(g["metric_label"].iloc[0]) if "metric_label" in g.columns else str(metric)
            box_strip(g, "condition", "metric_value", f"KOMSim_{safe(metric)}_box_strip_by_condition", "hci_box_strip", ylabel)
            summ = g.groupby("condition")["metric_value"].agg(["mean", "std", "count"]).reset_index()
            for mode in ["dynamic", "zero"]:
                bar_mean_sd(summ, "condition", "mean", "std", f"KOMSim_{safe(metric)}_mean_sd_by_condition", "hci_mean_sd", mode, ylabel)
        pivot = ratings.groupby(["condition", "metric_code"])["metric_value"].mean().unstack().reset_index()
        specs = []
        for c in ["confidence", "info_sufficiency", "decision_certainty", "case_workload", "ai_influence"]:
            if c in pivot.columns:
                specs.append((c, c.replace("_", " ").title(), "lower" if "workload" in c else "higher"))
        radar(pivot, "condition", specs, "KOMSim_multidimensional_radar_profile_by_condition", "hci_radar")
    if not case.empty:
        outputs["hci_case_level"] = case
        process_cols = ["edit_time_sec", "patient_view_count", "ai_plan_view_count", "mdt_view_count", "evidence_view_count", "copy_ai_count"]
        for col in process_cols:
            if col in case.columns and numeric(case[col]).notna().sum() > 0:
                box_strip(case, "condition", col, f"KOMSim_{safe(col)}_box_strip_by_condition", "hci_process_box_strip", col.replace("_", " ").title())
                summ = case.groupby("condition")[col].agg(["mean", "std", "count"]).reset_index()
                for mode in ["dynamic", "zero"]:
                    bar_mean_sd(summ, "condition", "mean", "std", f"KOMSim_{safe(col)}_mean_sd_by_condition", "hci_process_mean_sd", mode, col.replace("_", " ").title())
    if not workload.empty:
        outputs["hci_stage_workload"] = workload
        for metric, g in workload.groupby("metric_code"):
            ylabel = str(g["metric_label"].iloc[0]) if "metric_label" in g.columns else str(metric)
            box_strip(g, "stage_label", "metric_value", f"KOMSim_stage_{safe(metric)}_box_strip", "hci_workload_stage", ylabel)
            summ = g.groupby("stage_label")["metric_value"].agg(["mean", "std", "count"]).reset_index()
            for mode in ["dynamic", "zero"]:
                bar_mean_sd(summ, "stage_label", "mean", "std", f"KOMSim_stage_{safe(metric)}_mean_sd", "hci_workload_stage", mode, ylabel)
    return outputs


def remake_komrisk_from_master(xl: pd.ExcelFile) -> dict[str, pd.DataFrame]:
    outputs = {}
    perf = pd.read_excel(xl, "komrisk_mode_performance") if "komrisk_mode_performance" in xl.sheet_names else pd.DataFrame()
    if not perf.empty:
        outputs["komrisk_mode_performance"] = perf
        for metric in ["AUROC", "AUPRC", "Brier"]:
            if metric in perf.columns:
                for outcome, g in perf.groupby("Outcome"):
                    d = g[["Mode", metric]].copy().rename(columns={"Mode": "mode", metric: "mean"})
                    for mode in ["dynamic", "zero"]:
                        bar_mean_sd(d, "mode", "mean", None, f"KOMRisk_{safe(outcome)}_{metric}", "komrisk_mode_performance", mode, metric)
    shap = pd.read_excel(xl, "komrisk_shap_top") if "komrisk_shap_top" in xl.sheet_names else pd.DataFrame()
    if not shap.empty and {"outcome", "feature", "mean_abs_shap"}.issubset(shap.columns):
        outputs["komrisk_shap_top"] = shap
        for outcome, g in shap.groupby("outcome"):
            top = g.sort_values("mean_abs_shap", ascending=False).head(15).copy()
            fig, ax = plt.subplots(figsize=(7.8, 5.2))
            top = top.sort_values("mean_abs_shap")
            y = np.arange(len(top))
            ax.barh(y, top["mean_abs_shap"], color=COLORS["teal"], alpha=0.9)
            ax.set_yticks(y)
            ax.set_yticklabels([wrap(x, 26) for x in top["feature"]])
            ax.set_xlabel("Mean absolute SHAP value")
            style_axes(ax)
            save_fig(fig, f"KOMRisk_{safe(outcome)}_SHAP_top15", "komrisk_shap", top)
    return outputs


def graph_schematic() -> pd.DataFrame:
    nodes = pd.DataFrame(
        [
            ("Standard\ncases", 0.08, 0.63, COLORS["teal_light"]),
            ("KOM-Profile", 0.25, 0.63, "#DCEBE4"),
            ("OAK-Net", 0.25, 0.34, "#EEE2D7"),
            ("KOM-Risk", 0.43, 0.63, "#ECE4F0"),
            ("KOM-RAG", 0.43, 0.34, "#E7EEF5"),
            ("Graph\nevidence", 0.61, 0.34, "#F1E7D2"),
            ("MDT/Rx", 0.61, 0.63, "#DFEDE3"),
            ("Safety\naudit", 0.79, 0.63, "#F1DDDA"),
            ("Doctor UI", 0.79, 0.34, "#E8EDF1"),
        ],
        columns=["node", "x", "y", "color"],
    )
    edges = [
        ("Standard\ncases", "KOM-Profile"),
        ("Standard\ncases", "OAK-Net"),
        ("KOM-Profile", "KOM-Risk"),
        ("OAK-Net", "KOM-Risk"),
        ("KOM-Risk", "MDT/Rx"),
        ("KOM-RAG", "Graph\nevidence"),
        ("Graph\nevidence", "MDT/Rx"),
        ("MDT/Rx", "Safety\naudit"),
        ("Safety\naudit", "Doctor UI"),
        ("Graph\nevidence", "Doctor UI"),
    ]
    pos = {r.node: (r.x, r.y) for r in nodes.itertuples()}
    fig, ax = plt.subplots(figsize=(10.4, 5.5))
    ax.set_xlim(0, 0.9)
    ax.set_ylim(0.18, 0.82)
    ax.axis("off")
    for s, t in edges:
        x0, y0 = pos[s]
        x1, y1 = pos[t]
        dx, dy = x1 - x0, y1 - y0
        if abs(dx) >= abs(dy):
            start = (x0 + (0.066 if dx > 0 else -0.066), y0)
            end = (x1 - (0.066 if dx > 0 else -0.066), y1)
        else:
            start = (x0, y0 + (0.052 if dy > 0 else -0.052))
            end = (x1, y1 - (0.052 if dy > 0 else -0.052))
        ax.annotate("", xy=end, xytext=start, arrowprops=dict(arrowstyle="-|>", lw=1.2, color="#68747D", connectionstyle="arc3,rad=0.08"))
    for _, n in nodes.iterrows():
        box = patches.FancyBboxPatch((n.x - 0.062, n.y - 0.048), 0.124, 0.096, boxstyle="round,pad=0.014,rounding_size=0.014", facecolor=n.color, edgecolor="#7B8790", lw=1.1)
        ax.add_patch(box)
        ax.text(n.x, n.y, n.node, ha="center", va="center", fontsize=9.2, color=COLORS["ink"])
    source = pd.concat([nodes.assign(kind="node"), pd.DataFrame(edges, columns=["source", "target"]).assign(kind="edge")], ignore_index=True, sort=False)
    save_fig(fig, "KOM_clean_frontier_graph_rag_pipeline", "graph_rag_schematic", source)
    return source


def write_gallery() -> None:
    pngs = sorted(FIG.glob("*.png"))
    cards = []
    cats = {}
    for p in pngs:
        cat = p.name.split("__", 1)[0]
        cats[cat] = cats.get(cat, 0) + 1
        label = p.stem.split("__", 1)[-1].replace("_", " ")
        cards.append(f"<figure class='card' data-cat='{cat}' data-name='{p.name.lower()} {label.lower()}'><a href='{p.name}' target='_blank'><img loading='lazy' src='{p.name}'></a><figcaption><b>{cat}</b><span>{label}</span></figcaption></figure>")
    chips = "".join([f"<button class='chip' data-filter='{c}'>{c}<span>{n}</span></button>" for c, n in sorted(cats.items())])
    html = f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>KOM style-migrated remake</title>
<style>body{{margin:0;font-family:Arial,Helvetica,sans-serif;background:#f7f9fb;color:#1B2A34}}.bar{{position:sticky;top:0;background:rgba(255,255,255,.96);border-bottom:1px solid #dbe4ea;padding:12px 16px;display:grid;grid-template-columns:1fr auto;gap:12px;z-index:2}}input{{font-size:14px;padding:10px;border:1px solid #ccd8df;border-radius:6px}}.meta{{font-size:13px;color:#66747E;align-self:center}}.chips{{padding:10px 16px;background:white;border-bottom:1px solid #dbe4ea;display:flex;gap:8px;flex-wrap:wrap}}.chip{{border:1px solid #ccd8df;background:white;border-radius:999px;padding:6px 10px;font-size:12px;cursor:pointer}}.chip span{{margin-left:5px;color:#66747E}}.chip.active{{background:#285E6F;color:white;border-color:#285E6F}}.chip.active span{{color:#d9edf3}}.grid{{padding:16px;display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px}}.card{{margin:0;background:white;border:1px solid #dbe4ea;border-radius:8px;overflow:hidden;box-shadow:0 1px 2px rgba(24,36,48,.05)}}.card img{{width:100%;aspect-ratio:4/3;object-fit:contain;background:white;display:block;border-bottom:1px solid #e4edf2}}figcaption{{padding:9px 10px 11px;display:flex;flex-direction:column;gap:4px;min-height:58px}}figcaption b{{font-size:12px;color:#285E6F}}figcaption span{{font-size:12px;line-height:1.25;overflow-wrap:anywhere}}.hide{{display:none}}</style></head>
<body><div class='bar'><input id='q' placeholder='Search all style-migrated figures...'><div id='meta' class='meta'>{len(pngs)} figures</div></div><div class='chips'><button class='chip active' data-filter='all'>All<span>{len(pngs)}</span></button>{chips}</div><main class='grid'>{''.join(cards)}</main>
<script>const cards=[...document.querySelectorAll('.card')], q=document.getElementById('q'), meta=document.getElementById('meta');let active='all';function f(){{let s=q.value.toLowerCase(),n=0;cards.forEach(c=>{{let ok=(active==='all'||c.dataset.cat===active)&&(!s||c.dataset.name.includes(s));c.classList.toggle('hide',!ok);if(ok)n++;}});meta.textContent=n+' / '+cards.length+' figures shown';}}document.querySelectorAll('.chip').forEach(b=>b.onclick=()=>{{document.querySelectorAll('.chip').forEach(x=>x.classList.remove('active'));b.classList.add('active');active=b.dataset.filter;f();}});q.oninput=f;f();</script></body></html>"""
    (FIG / "index.html").write_text(html, encoding="utf-8")
    pd.DataFrame(fig_records).to_csv(FIG / "STYLE_MIGRATED_FIGURE_MANIFEST.csv", index=False, encoding="utf-8-sig")


def write_master(outputs: dict[str, pd.DataFrame], reference_png: pd.DataFrame, reference_manifest: pd.DataFrame, reference_source_long: pd.DataFrame) -> Path:
    path = TABLES / "KOM_Style_Migrated_Remake_Master_Table_20260615.xlsx"
    used_sheets: set[str] = set()

    def sheet_name(base: str) -> str:
        stem = safe(base, 27) or "sheet"
        name = stem[:31]
        i = 1
        while name.lower() in used_sheets:
            suffix = f"_{i:02d}"
            name = f"{stem[:31 - len(suffix)]}{suffix}"
            i += 1
        used_sheets.add(name.lower())
        return name

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(fig_records).to_excel(writer, sheet_name("remade_figure_manifest"), index=False)
        pd.DataFrame(qc_records).to_excel(writer, sheet_name("visual_qc"), index=False)
        pd.DataFrame(source_records).to_excel(writer, sheet_name("legacy_source_index"), index=False)
        reference_png.to_excel(writer, sheet_name("reference_png_inventory"), index=False)
        if not reference_manifest.empty:
            reference_manifest.to_excel(writer, sheet_name("reference_manifest_qc"), index=False)
        if not reference_source_long.empty:
            reference_source_long.to_excel(writer, sheet_name("legacy_source_values_long"), index=False)
        for name, df in outputs.items():
            if df is None or df.empty:
                continue
            try:
                df.to_excel(writer, sheet_name(name), index=False)
            except Exception:
                df.astype(str).to_excel(writer, sheet_name(name), index=False)
        old_xl = pd.ExcelFile(MASTER)
        old_index = pd.DataFrame(
            [{"old_sheet_order": i + 1, "old_sheet_name": sheet} for i, sheet in enumerate(old_xl.sheet_names)]
        )
        old_index.to_excel(writer, sheet_name("old_master_sheet_index"), index=False)
        for i, sheet in enumerate(old_xl.sheet_names, start=1):
            old_df = pd.read_excel(old_xl, sheet_name=sheet)
            try:
                old_df.to_excel(writer, sheet_name(f"old_{i:02d}_{sheet}"), index=False)
            except Exception:
                old_df.astype(str).to_excel(writer, sheet_name(f"old_{i:02d}_{sheet}"), index=False)
    return path


def main() -> None:
    if not REF_POOL.exists():
        raise FileNotFoundError(REF_POOL)
    if not MASTER.exists():
        raise FileNotFoundError(MASTER)
    shutil.copy2(Path(__file__), SCRIPTS / Path(__file__).name)
    reference_png, reference_manifest, reference_source_long = reference_inventory()
    xl = pd.ExcelFile(MASTER)
    outputs: dict[str, pd.DataFrame] = {}
    outputs.update(remake_reference_source_figures())
    outputs.update(remake_oaknet_from_master(xl))
    outputs.update(remake_hci_from_master(xl))
    outputs.update(remake_komrisk_from_master(xl))
    outputs["graph_rag_schematic_source"] = graph_schematic()
    write_gallery()
    master = write_master(outputs, reference_png, reference_manifest, reference_source_long)
    pd.DataFrame(qc_records).to_csv(QC / "style_migrated_visual_qc.csv", index=False, encoding="utf-8-sig")
    report = AUDIT / "KOM_Style_Migrated_Remake_Audit_20260615.md"
    qcdf = pd.DataFrame(qc_records)
    report.write_text(
        "\n".join(
            [
                "# KOM Style-Migrated Figure Remake Audit",
                "",
                f"- Reference PNG inventory: {len(reference_png)} files.",
                f"- Reference source tables imported into master table: {len(source_records)} files.",
                f"- Remade figures: {len(fig_records)} PNG/SVG/PDF records.",
                f"- QC counts: {qcdf['qc_status'].value_counts().to_dict() if not qcdf.empty else {}}.",
                f"- Previous deep-optimization master workbook appended: {len(pd.ExcelFile(MASTER).sheet_names)} original sheets plus an old-sheet index.",
                "- Final master workbook is intentionally larger than the previous workbook because it carries both regenerated figure sources and prior master sheets.",
                "- Style migrated from the provided manuscript PNG selection pool: muted teal bars, pale grid, compact labels, value annotations, box+strip overlays, light radar fills, and clean rounded workflow panels.",
                "- Q1/Q2/Q3/Q4 quadrant panels were not regenerated.",
                "- Confusion matrices and training/validation curves were explicitly regenerated from audited OAKNet assets/master tables.",
            ]
        ),
        encoding="utf-8",
    )
    print("OUTPUT", OUT)
    print("PNG_GALLERY", FIG / "index.html")
    print("MASTER_TABLE", master)
    print("FIGURES", len(fig_records))
    print("QC", qcdf["qc_status"].value_counts().to_dict() if not qcdf.empty else {})


if __name__ == "__main__":
    main()
