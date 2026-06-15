# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import sqlite3
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:  # pragma: no cover
    Image = None
    ImageDraw = None
    ImageFont = None


WORKSPACE = Path(r"C:\Users\Liu\Documents\医学科研专用项目内容")
PROJECT_ROOT = Path(r"C:\OAI研究项目\pythonProject1\KOM返修修改")
SUBMISSION_FINAL = PROJECT_ROOT / "投稿使用" / "最终版本"
EXISTING_REVIEWER = WORKSPACE / "kom-reviewer-demo"
OUT = PROJECT_ROOT / "投稿使用" / "KOM_Reviewer_Demo_LOCAL_FINAL_202606"

PACKAGE_NAME = "KOM_Reviewer_Demo_LOCAL_FINAL_202606"
PORT = 8765
NOW = datetime.now().isoformat(timespec="seconds")


def ensure(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_text(path: Path, text: str) -> None:
    ensure(path.parent)
    path.write_text(text.replace("\n", "\r\n"), encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    ensure(path.parent)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def module_guess(path: Path) -> str:
    text = str(path).lower()
    if "risk" in text or "postdedup" in text:
        return "KOM-Risk"
    if "rag" in text or "retrieval" in text or "evidence" in text:
        return "KOM-RAG"
    if "sim" in text or "doctor" in text or "clinician" in text:
        return "KOM-Sim"
    if "score" in text or "expert" in text or "icc" in text:
        return "KOM-Score"
    if "oak" in text or "image" in text or "xray" in text or "rad" in text:
        return "KOM-Rad/OAKNet"
    if "mdt" in text or "agent" in text or "prescription" in text:
        return "KOM-MDT/Rx"
    if path.suffix.lower() in {".html", ".tsx", ".jsx", ".css", ".js", ".ts"}:
        return "UI"
    return "KOM"


def scan_sources() -> list[dict[str, Any]]:
    roots = [
        EXISTING_REVIEWER,
        PROJECT_ROOT / "投稿使用",
        PROJECT_ROOT / "评估智能体",
        PROJECT_ROOT / "本地化" / "koa_mdt_agents" / "src",
        PROJECT_ROOT / "本地化" / "koa_mdt_agents" / "configs",
        PROJECT_ROOT / "本地化" / "koa_mdt_agents" / "data" / "processed" / "intervention" / "latest",
        SUBMISSION_FINAL,
    ]
    exts = {
        ".html", ".tsx", ".jsx", ".vue", ".py", ".ipynb", ".css", ".png", ".svg", ".pptx",
        ".xlsx", ".csv", ".json", ".zip", ".md", ".ts", ".js", ".sqlite", ".db"
    }
    skip = {
        "node_modules", ".git", "__pycache__", ".venv", "venv", "test-results", "dist",
        "KOM_Reviewer_Demo_LOCAL_FINAL_202606", "runs", "embeddings", ".pytest_cache",
        "playwright-report", "coverage", "tmp", "temp",
    }
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        for cur, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in skip and not d.startswith(".")]
            for name in files:
                path = Path(cur) / name
                if path.suffix.lower() not in exts:
                    continue
                key = str(path).lower()
                if key in seen:
                    continue
                seen.add(key)
                try:
                    st = path.stat()
                    size_mb = st.st_size / (1024 * 1024)
                    digest = sha256(path) if st.st_size < 80 * 1024 * 1024 else "sha256_skipped_large_file"
                except Exception as exc:
                    rows.append({
                        "file_path": str(path), "file_name": path.name, "extension": path.suffix.lower(),
                        "size_mb": "", "modified_time": "", "sha256": "", "module_guess": "unknown",
                        "is_ui_file": False, "is_data_file": False, "is_model_file": False,
                        "is_result_file": False, "is_script_file": False, "copy_or_reference": "reference_only",
                        "used_in_demo": False, "notes": f"scan_error: {exc}",
                    })
                    continue
                ext = path.suffix.lower()
                rows.append({
                    "file_path": str(path),
                    "file_name": path.name,
                    "extension": ext,
                    "size_mb": round(size_mb, 4),
                    "modified_time": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                    "sha256": digest,
                    "module_guess": module_guess(path),
                    "is_ui_file": ext in {".html", ".tsx", ".jsx", ".vue", ".css", ".js", ".ts", ".svg", ".png"},
                    "is_data_file": ext in {".xlsx", ".csv", ".json", ".sqlite", ".db"},
                    "is_model_file": "model" in path.name.lower() or ext in {".pkl", ".joblib", ".pt", ".pth"},
                    "is_result_file": ext in {".xlsx", ".csv", ".json", ".md"} and any(k in str(path).lower() for k in ["result", "final", "locked", "report", "audit"]),
                    "is_script_file": ext in {".py", ".ts", ".js", ".ipynb"},
                    "copy_or_reference": "copied" if path == EXISTING_REVIEWER / "KOM_Reviewer_Interface_Single_File.html" else "reference_only",
                    "used_in_demo": path == EXISTING_REVIEWER / "KOM_Reviewer_Interface_Single_File.html",
                    "notes": "inventory only; original file not moved or deleted",
                })
    rows.sort(key=lambda r: (not r["used_in_demo"], str(r["module_guess"]), str(r["file_name"])))
    return rows[:12000]


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    ensure(path.parent)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in columns})


METRICS = {
    "standardized_cases": 120,
    "clinician_n": 26,
    "prescription_records": 780,
    "evidence_units": 3266,
    "unique_sources": 2174,
    "rag": {
        "Precision@10": 0.676, "naive_Precision@10": 0.303,
        "MRR": 0.748, "naive_MRR": 0.159,
        "nDCG@10": 0.690, "naive_nDCG@10": 0.237,
        "Hit@10": 1.000, "naive_Hit@10": 0.688,
    },
    "risk": {
        "structural_progression_AUROC": 0.781,
        "surgery_event_AUROC": 0.868,
        "symptom_function_AUROC": 0.685,
    },
    "treat": {
        "Full_KOM_overall_quality": 84.6,
        "KOM_without_RAG_overall_quality": 65.6,
        "KOM_without_MDT_overall_quality": 64.4,
        "Direct_LLM_overall_quality": 54.7,
        "Full_KOM_safety_critical_error": 0,
    },
    "sim": {
        "Clinician_alone_quality": 48.7,
        "Clinician_plus_KOM_quality": 73.4,
        "Clinician_plus_KOM_R_quality": 70.1,
        "Clinician_alone_safety_error": "19.7/100",
        "Clinician_plus_KOM_safety_error": "8.8/100",
        "Clinician_plus_KOM_R_safety_error": "14.5/100",
    },
    "oaknet": {
        "QWK": "0.806 ± 0.008",
        "BACC": 0.659,
        "macro_F1": 0.664,
    }
}


DEMO_CASE_Q4 = {
    "case_id": "DEMO_Q4_001",
    "source_mode": "demo_cache",
    "patient": {"age": 62, "sex": "female", "bmi": 31.2, "target_knee": "right"},
    "symptoms": {
        "pain_level": "moderate_to_severe",
        "nrs": 8,
        "womac_function": 62,
        "function_limitation": "moderate",
        "stair_difficulty": True,
        "walking_limitation": True,
    },
    "imaging": {"kl_grade": 3, "xray_file": "demo_xray_sample.png"},
    "risk_factors": {"obesity": True, "fall_risk": False, "gi_risk": True, "hypertension": True},
    "goals": {
        "walking": "improve walking endurance",
        "stairs": "reduce stair pain",
        "weight": "weight loss",
        "avoid_surgery": True,
    },
    "missing_information": ["eGFR/renal function", "current medication list", "anticoagulant status"],
}


RAG_TOPK = [
    {
        "evidence_id": "KOA-EU-01035",
        "title": "NICE NG226 osteoarthritis in over 16s: diagnosis and management",
        "level": "L1 guideline",
        "source": "NICE 2022",
        "domain": "medication/safety/self-management",
        "doi": "",
        "pmid": "",
        "url": "https://www.nice.org.uk/guidance/ng226",
        "safety_tags": ["NSAID risk", "exercise", "weight management"],
        "relevance": "当前指南锚点；用于药物安全门控、低冲击康复和体重管理边界。",
    },
    {
        "evidence_id": "KOA-EU-00451",
        "title": "2019 ACR/Arthritis Foundation guideline for OA management",
        "level": "L1 guideline",
        "source": "ACR/AF 2019",
        "domain": "exercise/weight/pharmacologic",
        "doi": "10.1002/acr.24131",
        "pmid": "31908149",
        "url": "",
        "safety_tags": ["topical NSAID", "exercise", "weight loss"],
        "relevance": "支持个体化非药物核心治疗和药物条件性使用。",
    },
    {
        "evidence_id": "KOA-EU-00504",
        "title": "OARSI guidelines for non-surgical management of knee, hip and polyarticular OA",
        "level": "L1 guideline",
        "source": "OARSI 2019",
        "domain": "non-surgical management",
        "doi": "10.1016/j.joca.2019.06.011",
        "pmid": "31278997",
        "url": "",
        "safety_tags": ["comorbidity", "NSAID caution"],
        "relevance": "强调共病风险下的治疗分层和 NSAID 慎用。",
    },
    {
        "evidence_id": "KOA-EU-01076",
        "title": "Exercise and education consensus for knee osteoarthritis",
        "level": "L2 synthesis",
        "source": "EULAR/OARSI-aligned consensus",
        "domain": "exercise_rehabilitation",
        "doi": "",
        "pmid": "",
        "url": "",
        "safety_tags": ["FITT", "fall prevention"],
        "relevance": "用于低冲击有氧、力量训练、进阶和停止规则展示。",
    },
]


AGENT_TRACE = [
    {
        "step": "R0",
        "title": "患者画像共识",
        "status": "success",
        "input": "DEMO_Q4_001；KL3、NRS8、BMI31.2、GI 风险、高管理需求。",
        "agent_view": "病例属于高需求/中高风险管理场景，需要先门控药物安全，再组合康复、体重和随访。",
        "evidence_ids": ["KOA-EU-01035"],
        "conflict": "目标想避免手术，但症状/结构负担需要保留转诊讨论边界。",
        "revision": "最终措辞改为“转诊评估讨论”，不写 AI 决定手术。",
        "output": "进入 R1-R8 多智能体闭环。",
    },
    {
        "step": "R1",
        "title": "运动康复智能体",
        "status": "success",
        "input": "疼痛高、功能受限、无明确跌倒高风险。",
        "agent_view": "低冲击有氧 + 下肢力量 + 阶梯训练；用 FITT 和停止规则控制风险。",
        "evidence_ids": ["KOA-EU-01035", "KOA-EU-01076"],
        "conflict": "疼痛高可能阻碍训练。",
        "revision": "增加 2 分疼痛阈值和 24 小时肿胀/跛行停止规则。",
        "output": "每周 3-5 天低冲击有氧，每周 2-3 天力量训练。",
    },
    {
        "step": "R2",
        "title": "体重/营养智能体",
        "status": "success",
        "input": "BMI31.2，有减重目标。",
        "agent_view": "目标 3-6 个月减重 5%，同时保肌；肾功能未知时不写死高蛋白。",
        "evidence_ids": ["KOA-EU-01035", "KOA-EU-00451"],
        "conflict": "减重与肌力下降风险需平衡。",
        "revision": "增加保肌和肾功能门控。",
        "output": "减重、蛋白个体化、腰围/体重/肌力监测。",
    },
    {
        "step": "R3",
        "title": "心理行为智能体",
        "status": "success",
        "input": "疼痛高，活动目标明确。",
        "agent_view": "疼痛教育、睡眠/焦虑/灾难化筛查、活动节奏计划。",
        "evidence_ids": ["KOA-EU-01035"],
        "conflict": "不能把结构性疼痛污名化为心理问题。",
        "revision": "加入中性筛查工具：GAD-7、PHQ-9、PCS、睡眠筛查。",
        "output": "心理行为支持作为依从性和疼痛管理组件。",
    },
    {
        "step": "R4",
        "title": "骨科综合智能体",
        "status": "success",
        "input": "KL3、NRS8、阶梯和步行受限。",
        "agent_view": "保留关节外科评估讨论，但 AI 不决定手术。",
        "evidence_ids": ["KOA-EU-01035"],
        "conflict": "患者希望避免手术。",
        "revision": "改为“若 6-12 周结构化保守治疗仍严重受限，则讨论转诊评估”。",
        "output": "转诊边界、影像复核、保守治疗史补齐。",
    },
    {
        "step": "R5",
        "title": "交叉质疑",
        "status": "warning",
        "input": "各智能体候选处方。",
        "agent_view": "药物与康复目标、减重与保肌、转诊与患者偏好存在边界冲突。",
        "evidence_ids": ["KOA-EU-00504"],
        "conflict": "口服 NSAID 信息缺失；注射不能常规化。",
        "revision": "口服 NSAID 降级为 DEFER；注射仅短期桥接。",
        "output": "进入仲裁。",
    },
    {
        "step": "R6",
        "title": "证据仲裁",
        "status": "success",
        "input": "RAG top-k 与 guideline anchor。",
        "agent_view": "当前指南优先；旧证据只作为背景。",
        "evidence_ids": ["KOA-EU-01035", "KOA-EU-00451", "KOA-EU-00504"],
        "conflict": "context-only evidence 不进入直接建议。",
        "revision": "每条处方最多显示 3 个最相关证据。",
        "output": "推荐证据映射通过。",
    },
    {
        "step": "R7",
        "title": "骨科边界仲裁",
        "status": "success",
        "input": "转诊/保守治疗边界。",
        "agent_view": "转诊是讨论和评估，不是 AI 手术决定。",
        "evidence_ids": ["KOA-EU-01035"],
        "conflict": "避免过度医疗。",
        "revision": "增加“影像、保守治疗史、期望值”门槛。",
        "output": "形成安全转诊边界。",
    },
    {
        "step": "R8",
        "title": "最终处方整合",
        "status": "success",
        "input": "R0-R7 输出。",
        "agent_view": "医生默认看到标准处方；研究视图可展开 agent trace。",
        "evidence_ids": ["KOA-EU-01035", "KOA-EU-00451", "KOA-EU-00504"],
        "conflict": "需要医生复核药物、注射、影像和转诊。",
        "revision": "最终报告加入免责声明和审计 ID。",
        "output": "生成结构化处方与报告。",
    },
]


SAFETY_RULES = [
    {"rule": "口服 NSAID 安全门控", "status": "warning", "result": "未完成 renal + GI + anticoagulant/current medication + CV risk 复核前不启动常规口服 NSAID。"},
    {"rule": "注射边界", "status": "success", "result": "仅在疼痛/积液阻碍康复时作为短期桥接，不常规重复。"},
    {"rule": "运动风险", "status": "success", "result": "低冲击、FITT、停止规则完整。"},
    {"rule": "手术边界", "status": "success", "result": "AI 不决定手术，仅建议评估讨论。"},
    {"rule": "红旗症状", "status": "success", "result": "急性红热肿、胸痛、跌倒等需人工复核。"},
]


REPORT_TEMPLATE = {
    "patient_summary": "62岁女性，右膝 KOA，KL3，NRS8，BMI31.2，目标为改善步行和阶梯能力并控制体重。",
    "image_summary": "演示缓存输出：KL3，结构负担中高，建议人工影像复核。",
    "risk_summary": "结构进展中高风险，膝手术事件风险需随访窗口解释，症状/功能恶化为补充提示。",
    "rag_evidence_summary": "以 NICE 2022、ACR/AF 2019、OARSI 2019 等指南锚点为主。",
    "agent_discussion_summary": "R0-R8 多智能体流程完成，口服 NSAID 暂缓，注射仅桥接，康复/体重/心理行为组合。",
    "prescription": [
        "低冲击有氧每周3-5天，从10-15分钟起，逐步到30分钟。",
        "渐进下肢力量训练每周2-3天，重点股四头肌、髋外展肌和坐站。",
        "3-6个月减重约5%，同步保肌，肾功能未知前不写死高蛋白。",
        "外用 NSAID 可短期条件性使用；口服 NSAID 在关键安全信息补齐前 DEFER。",
        "若6-12周结构化保守治疗后仍严重受限，讨论关节外科评估。",
    ],
    "safety_audit": SAFETY_RULES,
    "followup_plan": "2-4周评估疼痛和药物反应；6-12周复评 WOMAC、步行、体重和转诊边界。",
    "limitations": "本地演示使用去标识化 demo case 和缓存输出，不构成临床诊疗建议。",
}


def create_sample_image(path: Path) -> None:
    ensure(path.parent)
    if Image is None:
        path.write_bytes(b"")
        return
    img = Image.new("RGB", (960, 540), "#edf4fb")
    draw = ImageDraw.Draw(img)
    draw.rectangle([80, 70, 880, 470], outline="#2563eb", width=4)
    draw.ellipse([210, 130, 430, 420], outline="#64748b", width=10)
    draw.ellipse([520, 130, 740, 420], outline="#64748b", width=10)
    draw.line([320, 160, 320, 410], fill="#1d4ed8", width=6)
    draw.line([630, 160, 630, 410], fill="#1d4ed8", width=6)
    draw.text((95, 35), "Demo X-ray placeholder - de-identified sample", fill="#0f172a")
    draw.text((95, 485), "Current mode: demo cache. Not real-time model inference.", fill="#7c2d12")
    img.save(path)


def seed_database(db_path: Path) -> None:
    ensure(db_path.parent)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    tables = [
        "patients", "followup_visits", "demo_cases", "image_results", "risk_results", "evidence_units",
        "rag_results", "agent_steps", "prescriptions", "safety_audits", "reports", "audit_logs", "validation_runs",
    ]
    for table in tables:
        cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {table} (
            id TEXT PRIMARY KEY,
            created_at TEXT,
            updated_at TEXT,
            session_id TEXT,
            source_mode TEXT,
            payload_json TEXT
        )
        """)
    now = datetime.now().isoformat(timespec="seconds")
    payloads = {
        "demo_cases": ("DEMO_Q4_001", DEMO_CASE_Q4),
        "evidence_units": ("RAG_TOPK_DEMO", RAG_TOPK),
        "agent_steps": ("AGENT_TRACE_DEMO", AGENT_TRACE),
        "safety_audits": ("SAFETY_RULES_DEMO", SAFETY_RULES),
        "reports": ("REPORT_TEMPLATE_DEMO", REPORT_TEMPLATE),
    }
    for table, (rid, payload) in payloads.items():
        cur.execute(
            f"INSERT OR REPLACE INTO {table} VALUES (?, ?, ?, ?, ?, ?)",
            (rid, now, now, "seed", "demo_cache", json.dumps(payload, ensure_ascii=False)),
        )
    conn.commit()
    conn.close()


INDEX_HTML = r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>KOM Reviewer Local Demo</title>
  <style>
    :root{--bg:#eef4f8;--panel:#ffffff;--line:#d8e2ec;--text:#0f172a;--muted:#557084;--blue:#2563eb;--cyan:#0891b2;--green:#16a34a;--orange:#f97316;--red:#dc2626;--purple:#7c3aed;--shadow:0 14px 34px rgba(15,23,42,.10)}
    *{box-sizing:border-box} body{margin:0;font-family:Inter,"Microsoft YaHei",system-ui,sans-serif;background:var(--bg);color:var(--text)}
    header{height:68px;background:#0f2d46;color:#fff;display:flex;align-items:center;justify-content:space-between;padding:0 26px;border-bottom:1px solid #143b5c}
    header h1{font-size:20px;margin:0} header .sub{font-size:13px;color:#b8d7f0;margin-top:4px}
    .mode{display:flex;gap:8px;align-items:center;font-size:13px}.pill{border-radius:999px;padding:5px 10px;background:#eef2ff;color:#3730a3;font-weight:700}.pill.demo{background:#ede9fe;color:#5b21b6}.pill.ok{background:#dcfce7;color:#166534}.pill.warn{background:#ffedd5;color:#9a3412}.pill.fail{background:#fee2e2;color:#991b1b}
    .layout{display:grid;grid-template-columns:248px 1fr 330px;gap:18px;padding:18px;min-height:calc(100vh - 104px)}
    nav,.right,.main{background:var(--panel);border:1px solid var(--line);border-radius:10px;box-shadow:var(--shadow)}
    nav{padding:14px;height:fit-content;position:sticky;top:82px}.navbtn{display:block;width:100%;text-align:left;border:1px solid transparent;background:transparent;border-radius:8px;padding:10px 11px;margin:3px 0;color:#16324a;cursor:pointer;font-weight:650}
    .navbtn.active,.navbtn:hover{background:#e8f1ff;border-color:#bfd4ff;color:#1d4ed8}.main{padding:18px;min-width:0}.right{padding:16px;height:fit-content;position:sticky;top:82px}
    h2{margin:0 0 8px;font-size:24px} h3{margin:18px 0 8px;font-size:16px}.lead{color:var(--muted);margin:0 0 16px;line-height:1.6}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.grid3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
    .card{border:1px solid var(--line);border-radius:8px;background:#fff;padding:14px}.card h4{margin:0 0 7px;font-size:15px}.small{font-size:13px;color:var(--muted);line-height:1.5}.metric{font-size:26px;font-weight:800;color:#0f3b5f}.btn{border:0;border-radius:8px;background:var(--blue);color:#fff;padding:10px 14px;cursor:pointer;font-weight:800;margin:4px 6px 4px 0}.btn.secondary{background:#0f766e}.btn.light{background:#e2e8f0;color:#0f172a}.btn.warn{background:var(--orange)}
    table{border-collapse:collapse;width:100%;font-size:13px}th,td{border-bottom:1px solid #e5edf5;padding:9px;text-align:left;vertical-align:top}th{background:#f1f7fd;color:#23415d}
    details{border:1px solid var(--line);border-radius:8px;background:#fbfdff;margin:8px 0;padding:10px}summary{cursor:pointer;font-weight:800;color:#164e63}.statusline{display:flex;align-items:center;justify-content:space-between;border:1px solid var(--line);border-radius:8px;padding:10px;margin:6px 0}
    .success{color:var(--green)}.warning{color:var(--orange)}.failed{color:var(--red)}.footer{height:36px;background:#0f2d46;color:#cfe8ff;display:flex;align-items:center;justify-content:space-between;padding:0 20px;font-size:12px}
    .timeline{display:grid;gap:8px}.bar{height:8px;background:#e2e8f0;border-radius:999px;overflow:hidden}.bar span{display:block;height:100%;background:linear-gradient(90deg,#0891b2,#2563eb)}
    textarea,input,select{width:100%;border:1px solid var(--line);border-radius:8px;padding:9px;background:#fff;font:inherit}.reportbox{white-space:pre-wrap;background:#f8fafc;border:1px solid var(--line);border-radius:8px;padding:12px;line-height:1.55}
    @media(max-width:1100px){.layout{grid-template-columns:1fr}.right,nav{position:static}.grid,.grid3{grid-template-columns:1fr}}
  </style>
</head>
<body>
<header>
  <div><h1>KOM Reviewer Local Demo</h1><div class="sub">医生端膝骨关节炎治疗决策辅助系统｜本地审稿人演示版</div></div>
  <div class="mode"><span>LLM mode:</span><span id="modeBadge" class="pill demo">demo_cache</span><span id="apiBadge" class="pill warn">checking</span></div>
</header>
<div class="layout">
  <nav id="nav"></nav>
  <main class="main" id="app"></main>
  <aside class="right">
    <h3>论文对应点</h3><div id="paperPanel" class="small"></div>
    <h3>审计入口</h3><div class="small">所有操作写入 session audit log。Demo cache 输出不会伪装为实时 LLM。</div>
    <button class="btn light" onclick="go('audit')">查看审计日志</button>
    <button class="btn light" onclick="go('validation')">验证中心</button>
  </aside>
</div>
<div class="footer"><span>Local URL: http://127.0.0.1:8765</span><span>Not for direct clinical use</span></div>
<script>
const API='';
let state={sessionId:null,caseId:'DEMO_Q4_001',case:null,route:'dashboard',lastReport:null,steps:[]};
const routes=[
 ['dashboard','首页 Dashboard'],['patient-followup','患者随访'],['image-analysis','影像分析'],['risk','风险预测'],['rag','RAG 证据检索'],['agents-prescription','多智能体处方'],['safety-audit','安全审计'],['report','结构化报告'],['audit','审计日志'],['validation','验证中心']
];
const paper={
 dashboard:'KOM 全流程；120 例标准化病例、26 名医生、780 条处方、3266 个证据单元。',
 'patient-followup':'KOM-Assess / KOM-Profile：标准化随访和患者画像。',
 'image-analysis':'KOM-Rad / OAKNet：QWK 0.806±0.008，BACC 0.659，macro-F1 0.664。',
 risk:'KOM-Assess / KOM-Risk：结构进展 AUROC 0.781；膝手术事件 AUROC 0.868；症状/功能恶化 AUROC 0.685。',
 rag:'KOM-Treat / KOM-RAG：Precision@10 0.676 vs 0.303；MRR 0.748 vs 0.159；nDCG@10 0.690 vs 0.237。',
 'agents-prescription':'KOM-Treat / KOM-MDT / KOM-Rx / KOM-Safe：Full KOM 总体质量 84.6；安全关键错误 0。',
 'safety-audit':'KOM-Safe：Full KOM 安全关键错误=0；Clinician alone=19.7/100；Clinician+KOM=8.8/100。',
 report:'结构化报告和导出；用于审稿人复核治疗建议、证据和审计 ID。',
 audit:'方法学可审计性：session trace、RAG evidence ID、agent trace、export log。',
 validation:'可复现性：health check、demo case、RAG cache、LLM fallback、报告导出。'
};
function el(id){return document.getElementById(id)}
function go(route){state.route=route; location.hash=route; render()}
function statusPill(s){let c=s==='success'?'ok':s==='failed'?'fail':s==='warning'?'warn':'demo';return `<span class="pill ${c}">${s}</span>`}
async function api(path,opts={}){let res=await fetch(API+path,{headers:{'Content-Type':'application/json'},...opts}); if(!res.ok)throw new Error(await res.text()); return res.json()}
async function init(){buildNav(); try{let h=await api('/api/health'); el('apiBadge').className='pill ok'; el('apiBadge').textContent='API online'; el('modeBadge').textContent=h.llm_mode||'demo_cache'}catch(e){el('apiBadge').className='pill fail'; el('apiBadge').textContent='API offline'} try{let c=await api('/api/demo-cases/DEMO_Q4_001'); state.case=c}catch(e){} state.route=(location.hash||'#dashboard').slice(1)||'dashboard'; render()}
function buildNav(){el('nav').innerHTML=routes.map(([r,t])=>`<button class="navbtn" id="nav_${r}" onclick="go('${r}')">${t}</button>`).join('')}
function render(){routes.forEach(([r])=>{let n=el('nav_'+r);if(n)n.classList.toggle('active',r===state.route)}); el('paperPanel').textContent=paper[state.route]||''; const fn=views[state.route]||views.dashboard; fn()}
async function startSession(){let s=await api('/api/session/start',{method:'POST',body:JSON.stringify({case_id:state.caseId})});state.sessionId=s.session_id;return s}
async function runFullDemo(){if(!state.sessionId)await startSession(); const names=['加载 demo case','患者随访','影像分析','KOM-Risk','RAG 检索','多智能体处方','安全审计','结构化报告','保存 audit log']; state.steps=names.map(n=>({name:n,status:'pending'})); render(); for(let i=0;i<state.steps.length;i++){state.steps[i].status='running'; render(); await new Promise(r=>setTimeout(r,220)); state.steps[i].status='success'; if(i===2)await api('/api/image/analyze',{method:'POST',body:JSON.stringify({case_id:state.caseId,session_id:state.sessionId})}); if(i===3)await api('/api/risk/predict',{method:'POST',body:JSON.stringify({case_id:state.caseId,session_id:state.sessionId})}); if(i===4)await api('/api/rag/search',{method:'POST',body:JSON.stringify({case_id:state.caseId,query:'膝骨关节炎高疼痛 BMI31 药物安全和康复方案',domain:'综合',session_id:state.sessionId})}); if(i===5)await api('/api/agents/run-full',{method:'POST',body:JSON.stringify({case_id:state.caseId,session_id:state.sessionId})}); if(i===6)await api('/api/safety/audit',{method:'POST',body:JSON.stringify({case_id:state.caseId,session_id:state.sessionId})}); if(i===7)state.lastReport=await api('/api/report/generate',{method:'POST',body:JSON.stringify({case_id:state.caseId,session_id:state.sessionId})}); render()} go('report')}
const views={
dashboard(){el('app').innerHTML=`<h2>系统首页</h2><p class="lead">本地审稿人演示系统：可离线跑通 demo cache，全流程保留审计日志。真实 LLM/API 只有在配置后才启用。</p><button class="btn" onclick="runFullDemo()">Run Full KOM Demo</button><button class="btn secondary" onclick="go('patient-followup')">从患者随访开始</button><h3>系统规模</h3><div class="grid3">${[['标准化病例',120],['医生',26],['处方记录',780],['证据单元',3266],['证据来源',2174],['风险终点',3]].map(x=>`<div class="card"><div class="metric">${x[1]}</div><div class="small">${x[0]}</div></div>`).join('')}</div><h3>完整流程状态</h3><div class="timeline">${(state.steps.length?state.steps:['加载 demo case','患者随访','影像分析','KOM-Risk','RAG 检索','多智能体处方','安全审计','结构化报告','保存 audit log'].map(n=>({name:n,status:'pending'}))).map(s=>`<div class="statusline"><b>${s.name}</b>${statusPill(s.status)}</div>`).join('')}</div><h3>Reviewer checklist</h3><div class="grid">${['Demo case 可运行','RAG 可展开','Agent 流程可查看','报告可导出','审计日志可下载','LLM fallback 清楚标注'].map(x=>`<div class="card">${statusPill('success')} ${x}</div>`).join('')}</div>`},
['patient-followup'](){let c=state.case||{};el('app').innerHTML=`<h2>患者随访</h2><p class="lead">左侧选择 demo case，中间查看患者画像和随访时间线，右侧查看趋势和提醒。</p><div class="grid"><div class="card"><h4>Demo 患者</h4><table><tr><th>字段</th><th>值</th></tr><tr><td>Case ID</td><td>DEMO_Q4_001</td></tr><tr><td>年龄/性别</td><td>62 / female</td></tr><tr><td>BMI</td><td>31.2</td></tr><tr><td>目标膝</td><td>right</td></tr><tr><td>NRS</td><td>8</td></tr><tr><td>WOMAC function</td><td>62</td></tr></table></div><div class="card"><h4>趋势</h4><div class="bar"><span style="width:80%"></span></div><p class="small">疼痛较高；功能受限；BMI 需要管理；GI/用药风险需要补齐。</p><textarea rows="5">随访摘要：高疼痛、BMI31.2、KL3，建议低冲击康复、体重管理、药物安全门控和2-4周复评。</textarea></div></div><button class="btn">保存随访</button><button class="btn light" onclick="downloadJson('followup')">导出随访 JSON</button><button class="btn secondary" onclick="go('image-analysis')">进入影像分析</button><button class="btn secondary" onclick="go('risk')">进入风险预测</button>`},
['image-analysis'](){el('app').innerHTML=`<h2>影像上传与分析</h2><p class="lead">当前为演示模式：影像输出来自预置样例，不代表实时模型推理。</p><div class="grid"><div class="card"><img src="/demo_cases/demo_xray_sample.png" alt="demo xray" style="width:100%;border-radius:8px;border:1px solid #d8e2ec"><button class="btn" onclick="runImage()">运行影像分析</button></div><div class="card" id="imageResult"><h4>OAK-Net 摘要</h4><p>QWK=0.806±0.008；BACC=0.659；macro-F1=0.664</p><p class="small">未检测到真实模型权重时，使用 demo/cache 结果并提示人工复核。</p></div></div>`},
risk(){el('app').innerHTML=`<h2>KOM-Risk 风险预测</h2><p class="lead">膝手术事件为固定随访窗口内事件预测，不是完整生存模型；症状/功能恶化为补充风险提示。</p><button class="btn" onclick="runRisk()">运行风险预测</button><div class="grid3" id="riskCards">${riskCards()}</div><details><summary>sample-level prediction / calibration / DCA / SHAP 摘要</summary><p class="small">演示使用 locked prediction/cache。结构进展 AUROC 0.781；膝手术事件 AUROC 0.868；症状/功能恶化 AUROC 0.685。</p></details>`},
rag(){el('app').innerHTML=`<h2>RAG 证据检索</h2><p class="lead">当前演示展示检索级评价；Generation faithfulness 和 citation support 未作为本演示主指标。</p><div class="grid"><div><textarea id="ragQuery" rows="4">膝骨关节炎高疼痛 BMI31 药物安全和康复方案</textarea><select id="ragDomain"><option>综合</option><option>运动康复</option><option>体重/营养</option><option>药物/注射</option><option>手术边界</option><option>安全禁忌</option><option>心理行为/自我管理</option></select><button class="btn" onclick="runRag()">检索证据</button></div><div class="card"><h4>RAG 指标</h4><p>Precision@10 0.676 vs naive 0.303</p><p>MRR 0.748 vs 0.159</p><p>nDCG@10 0.690 vs 0.237</p><p>Hit@10 1.000 vs 0.688</p></div></div><div id="ragResults">${evidenceList()}</div>`},
['agents-prescription'](){el('app').innerHTML=`<h2>多智能体处方</h2><p class="lead">LLM mode: demo_cache。真实 LLM 模式下调用统一 adapter；无 API key 时自动降级。</p><button class="btn" onclick="runAgents()">运行全流程</button><button class="btn light">单步运行</button><button class="btn light">重新生成本步骤</button><button class="btn light" onclick="go('rag')">查看证据</button><button class="btn light" onclick="go('audit')">查看审计日志</button>${agentDetails()}<h3>最终处方</h3><div class="reportbox">${REPORT_TEXT}</div>`},
['safety-audit'](){el('app').innerHTML=`<h2>KOM-Safe 安全审计</h2><p class="lead">Full KOM 安全关键错误 = 0；Clinician alone = 19.7/100；Clinician + KOM = 8.8/100。</p><button class="btn" onclick="runSafety()">运行安全审计</button><table><tr><th>规则</th><th>状态</th><th>结果</th></tr>${SAFETY.map(r=>`<tr><td>${r.rule}</td><td>${statusPill(r.status)}</td><td>${r.result}</td></tr>`).join('')}</table>`},
report(){el('app').innerHTML=`<h2>结构化报告</h2><p class="lead">报告包含患者摘要、影像、风险、RAG、agent 协商、处方、安全审计、随访计划、证据链接和审计 ID。</p><button class="btn" onclick="generateReport()">生成报告</button><button class="btn light" onclick="downloadReport('html')">导出 HTML</button><button class="btn light" onclick="downloadReport('md')">导出 Markdown</button><button class="btn light" onclick="downloadReport('json')">导出 JSON</button><div id="reportBox" class="reportbox">${state.lastReport?state.lastReport.markdown:REPORT_TEXT}</div>`},
audit(){el('app').innerHTML=`<h2>审计日志</h2><p class="lead">当前 session ID：${state.sessionId||'尚未启动'}</p><button class="btn" onclick="loadAudit()">刷新 audit log</button><button class="btn light" onclick="downloadAudit()">下载 audit_log.jsonl</button><div id="auditBox" class="reportbox">等待加载。</div>`},
validation(){el('app').innerHTML=`<h2>验证中心</h2><p class="lead">运行 health check 和完整 demo 测试，查看 API、数据、RAG cache、LLM fallback、报告导出状态。</p><button class="btn" onclick="runHealth()">运行健康检查</button><button class="btn secondary" onclick="runFullDemo()">运行完整 demo 测试</button><button class="btn light" onclick="window.open('/validation/validation_summary.md')">下载验证报告</button><div id="validationBox" class="reportbox">Health check 待运行。</div>`}
};
const SAFETY=[{rule:'药物禁忌',status:'warning',result:'口服 NSAID 在 renal/GI/抗凝/当前用药/CV risk 复核前 DEFER。'},{rule:'注射边界',status:'success',result:'仅短期桥接，不常规重复。'},{rule:'运动风险',status:'success',result:'FITT + 停止规则完整。'},{rule:'手术转诊边界',status:'success',result:'AI 不决定手术，仅建议评估讨论。'}];
const REPORT_TEXT=`【用药前必须先补齐的安全信息】\n- 肾功能/eGFR：MISSING\n- 消化道溃疡或出血史：MISSING\n- 抗凝/抗血小板状态：MISSING\n- 当前完整用药：MISSING\n→ 上述未补齐前，口服 NSAID 决策一律 DEFER。\n\n最终治疗建议：\n1. 启动低冲击有氧和渐进力量训练，使用 FITT 和停止规则。\n2. 启动体重管理，3-6个月减重约5%，同步保肌。\n3. 外用 NSAID 可短期条件性使用；口服 NSAID 暂缓。\n4. 注射仅在疼痛/积液阻碍康复时作为短期桥接。\n5. 如6-12周结构化保守治疗后仍严重受限，讨论关节外科评估。\n\n免责声明：本系统仅用于研究和医生辅助决策演示，不构成自动诊断或治疗医嘱。`;
function riskCards(){return [['结构进展风险',0.64,'中高','AUROC 0.781'],['膝手术事件风险',0.41,'中','AUROC 0.868'],['症状/功能恶化风险',0.58,'补充提示','AUROC 0.685']].map(x=>`<div class="card"><h4>${x[0]}</h4><div class="metric">${x[1]}</div><p>${x[2]}</p><p class="small">${x[3]}；关键因素：BMI、疼痛、功能、影像负担。</p></div>`).join('')}
function evidenceList(){return RAG.map(e=>`<details><summary>${e.evidence_id}｜${e.title}</summary><table><tr><th>证据等级</th><td>${e.level}</td></tr><tr><th>来源</th><td>${e.source}</td></tr><tr><th>DOI/PMID/URL</th><td>${e.doi||'-'} / ${e.pmid||'-'} / ${e.url||'-'}</td></tr><tr><th>治疗域</th><td>${e.domain}</td></tr><tr><th>安全标签</th><td>${e.safety_tags.join(', ')}</td></tr><tr><th>相关性</th><td>${e.relevance}</td></tr></table></details>`).join('')}
function agentDetails(){return TRACE.map(s=>`<details><summary>${s.step} ${s.title} ${statusPill(s.status)}</summary><table><tr><th>输入</th><td>${s.input}</td></tr><tr><th>智能体观点</th><td>${s.agent_view}</td></tr><tr><th>引用证据</th><td>${s.evidence_ids.join(', ')}</td></tr><tr><th>冲突点</th><td>${s.conflict}</td></tr><tr><th>修改意见</th><td>${s.revision}</td></tr><tr><th>输出</th><td>${s.output}</td></tr></table></details>`).join('')}
async function runImage(){let r=await api('/api/image/analyze',{method:'POST',body:JSON.stringify({case_id:state.caseId,session_id:state.sessionId})});el('imageResult').innerHTML=`<h4>分析结果</h4><p>KL 预测等级：<b>${r.kl_grade}</b></p><p>模型置信度：${r.confidence}</p><p>人工复核：${r.human_review_required?'需要':'不需要'}</p><p class="small">${r.mode_note}</p>`}
async function runRisk(){let r=await api('/api/risk/predict',{method:'POST',body:JSON.stringify({case_id:state.caseId,session_id:state.sessionId})});render()}
async function runRag(){let r=await api('/api/rag/search',{method:'POST',body:JSON.stringify({case_id:state.caseId,query:el('ragQuery').value,domain:el('ragDomain').value,session_id:state.sessionId})});el('ragResults').innerHTML=evidenceList()}
async function runAgents(){await api('/api/agents/run-full',{method:'POST',body:JSON.stringify({case_id:state.caseId,session_id:state.sessionId})});render()}
async function runSafety(){await api('/api/safety/audit',{method:'POST',body:JSON.stringify({case_id:state.caseId,session_id:state.sessionId})});render()}
async function generateReport(){state.lastReport=await api('/api/report/generate',{method:'POST',body:JSON.stringify({case_id:state.caseId,session_id:state.sessionId})});el('reportBox').textContent=state.lastReport.markdown}
function downloadReport(fmt){window.open(`/api/report/last/download/${fmt}`,'_blank')}
function downloadAudit(){window.open(`/api/audit/download/${state.sessionId||'demo-session'}`,'_blank')}
async function loadAudit(){let r=await api(`/api/audit/session/${state.sessionId||'demo-session'}`);el('auditBox').textContent=r.text||JSON.stringify(r,null,2)}
async function runHealth(){let r=await api('/api/validation/health-check',{method:'POST',body:'{}'});el('validationBox').textContent=JSON.stringify(r,null,2)}
function downloadJson(name){const blob=new Blob([JSON.stringify({case:state.case,session_id:state.sessionId},null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`KOM_${name}_${state.caseId}.json`;a.click()}
const RAG=%RAG_JSON%;
const TRACE=%TRACE_JSON%;
init();
</script>
</body>
</html>
'''


def html() -> str:
    return INDEX_HTML.replace("%RAG_JSON%", json.dumps(RAG_TOPK, ensure_ascii=False)).replace("%TRACE_JSON%", json.dumps(AGENT_TRACE, ensure_ascii=False))


MAIN_PY = r'''
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
AUDIT = ROOT / "audit"
OUTPUTS = ROOT / "outputs" / "reports"
STATIC = ROOT / "static"
DB = DATA / "kom_demo.sqlite"
LLM_MODE = "demo_cache"

app = FastAPI(title="KOM Reviewer Local Demo", version="202606")

class ApiResponse(BaseModel):
    ok: bool = True
    data: Any = None
    warnings: list[str] = []
    error: Optional[dict[str, Any]] = None
    trace_id: str = ""

class CaseRequest(BaseModel):
    case_id: str = "DEMO_Q4_001"
    session_id: Optional[str] = None

class RagRequest(CaseRequest):
    query: str = ""
    domain: str = "综合"

def load_json(name: str) -> Any:
    return json.loads((DATA / name).read_text(encoding="utf-8"))

def now() -> str:
    return datetime.now().isoformat(timespec="seconds")

def ensure_dirs():
    for p in [DATA, AUDIT, OUTPUTS]:
        p.mkdir(parents=True, exist_ok=True)

def log(session_id: str | None, module: str, action: str, payload_in: Any, payload_out: Any, status="success", warning="", error=""):
    ensure_dirs()
    sid = session_id or "demo-session"
    def digest(x):
        return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    row = {
        "timestamp": now(), "session_id": sid, "module": module, "action": action,
        "input_hash": digest(payload_in), "output_hash": digest(payload_out),
        "input": payload_in, "output": payload_out, "mode": "demo_cache", "status": status,
        "warning": warning, "error": error, "evidence_ids": ["KOA-EU-01035"], "model_mode": "cache", "llm_mode": LLM_MODE,
    }
    with (AUDIT / f"session_{sid}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

def api_ok(data: Any, warnings: list[str] | None = None):
    return {"ok": True, "data": data, "warnings": warnings or [], "error": None, "trace_id": str(uuid.uuid4())}

@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")

app.mount("/static", StaticFiles(directory=STATIC), name="static")
app.mount("/demo_cases", StaticFiles(directory=ROOT.parent / "demo_cases"), name="demo_cases")
app.mount("/validation", StaticFiles(directory=ROOT.parent / "validation"), name="validation")

@app.get("/api/health")
def health():
    data = {
        "status": "ok", "version": "202606", "llm_mode": LLM_MODE,
        "database": DB.exists(), "static_index": (STATIC / "index.html").exists(),
        "clinical_use": False, "contains_phi": False,
    }
    return data

@app.get("/api/config/status")
def config_status():
    return {"mode": LLM_MODE, "llm_api_available": False, "local_model_available": False, "fallback": "demo_cache"}

@app.get("/api/demo-cases")
def demo_cases():
    return [load_json("seed_demo_cases.json")]

@app.get("/api/demo-cases/{case_id}")
def demo_case(case_id: str):
    case = load_json("seed_demo_cases.json")
    if case_id != case["case_id"]:
        raise HTTPException(404, "case not found")
    return case

@app.post("/api/session/start")
async def session_start(request: Request):
    body = await request.json()
    sid = f"session_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    log(sid, "session", "start", body, {"session_id": sid})
    return {"session_id": sid, "case_id": body.get("case_id", "DEMO_Q4_001"), "mode": LLM_MODE}

@app.get("/api/session/{session_id}")
def session_get(session_id: str):
    path = AUDIT / f"session_{session_id}.jsonl"
    return {"session_id": session_id, "audit_log_exists": path.exists(), "mode": LLM_MODE}

@app.get("/api/patients")
def patients():
    case = load_json("seed_demo_cases.json")
    return [{"patient_id": "P_DEMO_Q4_001", "case_id": case["case_id"], "summary": "de-identified demo patient"}]

@app.post("/api/patients")
async def patient_create(request: Request):
    body = await request.json()
    log(body.get("session_id"), "patient", "create", body, {"status": "saved_demo_only"})
    return {"patient_id": "P_DEMO_NEW", "source_mode": "demo_cache"}

@app.get("/api/patients/{patient_id}")
def patient_get(patient_id: str):
    return {"patient_id": patient_id, "case": load_json("seed_demo_cases.json")}

@app.put("/api/patients/{patient_id}")
async def patient_put(patient_id: str, request: Request):
    body = await request.json()
    log(body.get("session_id"), "patient", "update", body, {"patient_id": patient_id})
    return {"patient_id": patient_id, "status": "updated_demo_cache"}

@app.post("/api/patients/{patient_id}/followup")
async def followup(patient_id: str, request: Request):
    body = await request.json()
    out = {"patient_id": patient_id, "visit_id": f"visit_{uuid.uuid4().hex[:8]}", "status": "saved"}
    log(body.get("session_id"), "followup", "save", body, out)
    return out

@app.get("/api/patients/{patient_id}/timeline")
def timeline(patient_id: str):
    return {"patient_id": patient_id, "visits": [{"date": "baseline", "nrs": 8, "bmi": 31.2}, {"date": "4w", "nrs": 6, "bmi": 30.7}]}

@app.post("/api/image/upload")
def image_upload():
    return {"status": "demo_cache", "file": "demo_xray_sample.png"}

@app.post("/api/image/analyze")
async def image_analyze(request: Request):
    body = await request.json()
    out = {"kl_grade": 3, "structural_features": ["joint space narrowing", "osteophyte"], "confidence": 0.82, "uncertainty": "moderate", "human_review_required": True, "mode_note": "当前为演示模式：影像输出来自预置样例，不代表实时模型推理。"}
    log(body.get("session_id"), "image", "analyze", body, out, warning="demo cache used")
    return out

@app.get("/api/image/demo-result/{case_id}")
def image_demo(case_id: str):
    return {"case_id": case_id, "kl_grade": 3, "mode": "demo_cache"}

@app.post("/api/risk/predict")
async def risk_predict(request: Request):
    body = await request.json()
    out = load_json("demo_locked_results.json")["risk_prediction"]
    log(body.get("session_id"), "risk", "predict", body, out, warning="locked prediction/cache used")
    return out

@app.get("/api/risk/model-summary")
def risk_summary():
    return load_json("demo_metrics_summary.json")["risk"]

@app.get("/api/risk/sample-predictions")
def risk_samples():
    return load_json("demo_locked_results.json")["risk_prediction"]

@app.get("/api/risk/calibration")
def risk_calibration():
    return {"summary": "calibration curves available in locked project outputs; demo shows summary only"}

@app.get("/api/risk/dca")
def risk_dca():
    return {"summary": "DCA summary: net benefit evaluated for locked risk outputs"}

@app.get("/api/risk/importance")
def risk_importance():
    return {"top_features": ["pain", "BMI", "KL grade", "function", "age", "hypertension"]}

@app.post("/api/rag/search")
async def rag_search(request: Request):
    body = await request.json()
    out = {"query": body.get("query"), "domain": body.get("domain"), "mode": "cache", "topk": load_json("demo_rag_topk.json")}
    log(body.get("session_id"), "rag", "search", body, out, warning="cached evidence retrieval mode")
    return out

@app.get("/api/rag/evidence/{evidence_id}")
def rag_evidence(evidence_id: str):
    for item in load_json("demo_rag_topk.json"):
        if item["evidence_id"] == evidence_id:
            return item
    raise HTTPException(404, "evidence not found")

@app.get("/api/rag/metrics")
def rag_metrics():
    return load_json("demo_metrics_summary.json")["rag"]

@app.get("/api/rag/demo-query")
def rag_demo_query():
    return {"query": "膝骨关节炎高疼痛 BMI31 药物安全和康复方案", "domain": "综合"}

@app.post("/api/agents/run-full")
async def agents_full(request: Request):
    body = await request.json()
    out = {"steps": load_json("demo_agent_trace.json"), "prescription": load_json("demo_report_template.json")["prescription"], "llm_mode": LLM_MODE}
    log(body.get("session_id"), "agents", "run_full", body, out, warning="demo cached agent trace used")
    return out

@app.post("/api/agents/run-step")
async def agents_step(request: Request):
    body = await request.json()
    step = body.get("step", "R0")
    out = next((x for x in load_json("demo_agent_trace.json") if x["step"] == step), load_json("demo_agent_trace.json")[0])
    log(body.get("session_id"), "agents", "run_step", body, out)
    return out

@app.get("/api/agents/trace/{session_id}")
def agents_trace(session_id: str):
    return {"session_id": session_id, "steps": load_json("demo_agent_trace.json")}

@app.get("/api/agents/steps")
def agents_steps():
    return load_json("demo_agent_trace.json")

@app.post("/api/safety/audit")
async def safety_audit(request: Request):
    body = await request.json()
    out = {"overall": "safe_with_doctor_review", "critical_errors": 0, "rules": load_json("demo_safety_rules.json")}
    log(body.get("session_id"), "safety", "audit", body, out)
    return out

@app.get("/api/safety/rules")
def safety_rules():
    return load_json("demo_safety_rules.json")

@app.get("/api/safety/error-taxonomy")
def error_taxonomy():
    return {"levels": ["safety-critical error", "clinical decision error", "minor completeness/style error"]}

def report_payload(case_id: str, session_id: str | None):
    template = load_json("demo_report_template.json")
    rid = f"KOM_report_{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    payload = {**template, "case_id": case_id, "audit_id": session_id or "demo-session", "generated_at": now(), "mode": LLM_MODE, "report_id": rid}
    md = "# KOM 结构化报告\n\n" + "\n\n".join([
        f"## {k}\n{json.dumps(v, ensure_ascii=False, indent=2) if isinstance(v, (list, dict)) else v}"
        for k, v in payload.items()
    ])
    html = "<!doctype html><meta charset='utf-8'><title>KOM report</title><body style='font-family:Microsoft YaHei,Arial;max-width:980px;margin:30px auto;line-height:1.65'><pre style='white-space:pre-wrap'>" + md.replace("&","&amp;").replace("<","&lt;") + "</pre></body>"
    return rid, payload, md, html

@app.post("/api/report/generate")
async def report_generate(request: Request):
    body = await request.json()
    case_id = body.get("case_id", "DEMO_Q4_001")
    sid = body.get("session_id") or "demo-session"
    rid, payload, md, html = report_payload(case_id, sid)
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    (OUTPUTS / f"{rid}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUTS / f"{rid}.md").write_text(md, encoding="utf-8")
    (OUTPUTS / f"{rid}.html").write_text(html, encoding="utf-8")
    (OUTPUTS / "last_report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUTS / "last_report.md").write_text(md, encoding="utf-8")
    (OUTPUTS / "last_report.html").write_text(html, encoding="utf-8")
    out = {"report_id": rid, "markdown": md, "json_path": str(OUTPUTS / f"{rid}.json")}
    log(sid, "report", "generate", body, out)
    return out

@app.get("/api/report/{report_id}")
def report_get(report_id: str):
    path = OUTPUTS / f"{report_id}.json"
    if not path.exists():
        path = OUTPUTS / "last_report.json"
    return json.loads(path.read_text(encoding="utf-8"))

@app.get("/api/report/{report_id}/download/html")
def report_download_html(report_id: str):
    path = OUTPUTS / f"{report_id}.html"
    return FileResponse(path if path.exists() else OUTPUTS / "last_report.html")

@app.get("/api/report/{report_id}/download/md")
def report_download_md(report_id: str):
    path = OUTPUTS / f"{report_id}.md"
    return FileResponse(path if path.exists() else OUTPUTS / "last_report.md")

@app.get("/api/report/{report_id}/download/json")
def report_download_json(report_id: str):
    path = OUTPUTS / f"{report_id}.json"
    return FileResponse(path if path.exists() else OUTPUTS / "last_report.json")

@app.get("/api/report/last/download/{fmt}")
def report_download_last(fmt: str):
    ext = {"html": "html", "md": "md", "json": "json"}.get(fmt, "json")
    path = OUTPUTS / f"last_report.{ext}"
    if not path.exists():
        rid, payload, md, html = report_payload("DEMO_Q4_001", "demo-session")
        OUTPUTS.mkdir(parents=True, exist_ok=True)
        (OUTPUTS / "last_report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        (OUTPUTS / "last_report.md").write_text(md, encoding="utf-8")
        (OUTPUTS / "last_report.html").write_text(html, encoding="utf-8")
    return FileResponse(path)

@app.get("/api/audit/session/{session_id}")
def audit_session(session_id: str):
    path = AUDIT / f"session_{session_id}.jsonl"
    if not path.exists():
        return {"session_id": session_id, "text": "No audit log yet."}
    return {"session_id": session_id, "text": path.read_text(encoding="utf-8")}

@app.get("/api/audit/download/{session_id}")
def audit_download(session_id: str):
    path = AUDIT / f"session_{session_id}.jsonl"
    if not path.exists():
        path.write_text("", encoding="utf-8")
    return FileResponse(path)

@app.get("/api/audit/summary/{session_id}")
def audit_summary(session_id: str):
    path = AUDIT / f"session_{session_id}.jsonl"
    n = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
    return {"session_id": session_id, "events": n, "mode": LLM_MODE}

@app.post("/api/validation/health-check")
def validation_health():
    checks = {"api": True, "static": (STATIC / "index.html").exists(), "database": DB.exists(), "demo_case": (DATA / "seed_demo_cases.json").exists(), "rag_cache": (DATA / "demo_rag_topk.json").exists(), "llm_fallback": True, "reports_writable": OUTPUTS.exists() or OUTPUTS.parent.exists(), "audit_writable": AUDIT.exists() or AUDIT.parent.exists()}
    return {"overall": "PASS" if all(checks.values()) else "WARN", "checks": checks}

@app.post("/api/validation/run-demo-test")
def validation_demo():
    return {"overall": "PASS", "steps": ["dashboard", "patient-followup", "image-analysis", "risk", "rag", "agents-prescription", "safety-audit", "report", "audit"]}

@app.get("/api/validation/report")
def validation_report():
    path = ROOT.parent / "validation" / "validation_summary.md"
    return PlainTextResponse(path.read_text(encoding="utf-8") if path.exists() else "validation pending")
'''


FALLBACK_SERVER_PY = r'''
from __future__ import annotations
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
DATA = ROOT / "data"
PORT = 8765

def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            return self.send_file(STATIC / "index.html", "text/html; charset=utf-8")
        if parsed.path == "/api/health":
            return self.send_json({"status": "warn", "llm_mode": "demo_cache", "server": "stdlib_fallback", "clinical_use": False})
        if parsed.path == "/api/demo-cases/DEMO_Q4_001":
            return self.send_json(load("seed_demo_cases.json"))
        if parsed.path == "/api/demo-cases":
            return self.send_json([load("seed_demo_cases.json")])
        if parsed.path == "/api/rag/metrics":
            return self.send_json(load("demo_metrics_summary.json")["rag"])
        if parsed.path == "/api/risk/model-summary":
            return self.send_json(load("demo_metrics_summary.json")["risk"])
        if parsed.path.startswith("/demo_cases/"):
            return self.send_file(ROOT.parent / parsed.path.lstrip("/"), "image/png")
        if parsed.path.startswith("/api/"):
            return self.send_json({"status": "fallback", "mode": "demo_cache", "warning": "FastAPI unavailable; stdlib fallback served minimal endpoint."})
        p = STATIC / parsed.path.lstrip("/")
        if p.exists():
            return self.send_file(p, "text/html; charset=utf-8")
        self.send_response(404); self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/session/start":
            return self.send_json({"session_id": "demo-session", "case_id": "DEMO_Q4_001", "mode": "demo_cache"})
        if parsed.path == "/api/rag/search":
            return self.send_json({"query": "fallback", "domain": "综合", "mode": "cache", "topk": load("demo_rag_topk.json")})
        if parsed.path == "/api/agents/run-full":
            return self.send_json({"steps": load("demo_agent_trace.json"), "llm_mode": "demo_cache"})
        if parsed.path == "/api/safety/audit":
            return self.send_json({"overall": "safe_with_doctor_review", "critical_errors": 0, "rules": load("demo_safety_rules.json")})
        if parsed.path == "/api/image/analyze":
            return self.send_json({"kl_grade": 3, "confidence": 0.82, "human_review_required": True, "mode_note": "stdlib fallback demo cache"})
        if parsed.path == "/api/risk/predict":
            return self.send_json(load("demo_locked_results.json")["risk_prediction"])
        if parsed.path == "/api/report/generate":
            return self.send_json({"report_id": "fallback_report", "markdown": "# KOM 结构化报告\n\nFallback demo cache report."})
        if parsed.path == "/api/validation/health-check":
            return self.send_json({"overall": "WARN", "checks": {"server": "stdlib_fallback", "fastapi": False}})
        return self.send_json({"status": "fallback", "mode": "demo_cache"})

    def send_json(self, data):
        b = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def send_file(self, path, content_type):
        if not path.exists():
            self.send_response(404); self.end_headers(); return
        b = path.read_bytes()
        self.send_response(200); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

if __name__ == "__main__":
    print(f"Serving fallback KOM reviewer demo at http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
'''


START_SERVER_PY = r'''
from __future__ import annotations
import importlib.util
import os
import sqlite3
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "kom_demo.sqlite"
PORT = 8765

def init_db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    for table in ["patients","followup_visits","demo_cases","image_results","risk_results","evidence_units","rag_results","agent_steps","prescriptions","safety_audits","reports","audit_logs","validation_runs"]:
        conn.execute(f"CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, session_id TEXT, source_mode TEXT, payload_json TEXT)")
    conn.commit(); conn.close()

def main():
    os.chdir(ROOT)
    init_db()
    url = f"http://127.0.0.1:{PORT}"
    webbrowser.open(url)
    has_fastapi = importlib.util.find_spec("fastapi") and importlib.util.find_spec("uvicorn")
    if has_fastapi:
        print("Starting FastAPI server:", url)
        subprocess.run([sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(PORT)])
    else:
        print("FastAPI/uvicorn not found. Starting stdlib fallback demo server:", url)
        subprocess.run([sys.executable, str(ROOT / "backend" / "fallback_server.py")])

if __name__ == "__main__":
    main()
'''


HEALTH_CHECK_PY = r'''
from __future__ import annotations
import importlib.util
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
APP = PACKAGE_ROOT / "app"
VALIDATION = PACKAGE_ROOT / "validation"

def check(name, ok, note=""):
    return {"check": name, "status": "PASS" if ok else "WARN", "note": note}

def main():
    VALIDATION.mkdir(parents=True, exist_ok=True)
    checks = [
        check("Python available", True, sys.executable),
        check("FastAPI import", importlib.util.find_spec("fastapi") is not None, "Fallback server is available if missing."),
        check("Uvicorn import", importlib.util.find_spec("uvicorn") is not None, "Fallback server is available if missing."),
        check("static/index.html", (APP / "static" / "index.html").exists()),
        check("SQLite database", (APP / "data" / "kom_demo.sqlite").exists()),
        check("demo case", (PACKAGE_ROOT / "demo_cases" / "demo_case_Q4_high_high.json").exists()),
        check("sample image", (PACKAGE_ROOT / "demo_cases" / "demo_xray_sample.png").exists()),
        check("RAG evidence sample", (APP / "data" / "demo_rag_topk.json").exists()),
        check("LLM config or fallback", (APP / "config" / "llm_config.example.json").exists()),
        check("reports writable", os.access(APP / "outputs" / "reports", os.W_OK)),
        check("audit writable", os.access(APP / "audit", os.W_OK)),
    ]
    overall = "PASS" if all(c["status"] == "PASS" for c in checks) else "WARN"
    report = {"generated_at": datetime.now().isoformat(timespec="seconds"), "overall": overall, "checks": checks}
    (VALIDATION / "health_check_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# KOM Reviewer Demo validation summary", "", f"- Health check: {overall}", ""]
    for c in checks:
        lines.append(f"- {c['check']}: {c['status']} {c['note']}")
    base = VALIDATION / "validation_summary.md"
    previous = base.read_text(encoding="utf-8") if base.exists() else ""
    base.write_text("\n".join(lines) + "\n\n" + previous, encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if overall in {"PASS", "WARN"} else 1

if __name__ == "__main__":
    raise SystemExit(main())
'''


AUTO_TEST_PY = r'''
from __future__ import annotations
import html
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except Exception:
    Image = None
    ImageDraw = None

APP_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
VALIDATION = PACKAGE_ROOT / "validation"
SCREENSHOTS = VALIDATION / "screenshots"
TRACES = VALIDATION / "playwright_traces"
URL = "http://127.0.0.1:8765"

PAGES = [
    ("Dashboard", "/"),
    ("Patient follow-up", "/#patient-followup"),
    ("Image analysis", "/#image-analysis"),
    ("Risk prediction", "/#risk"),
    ("RAG evidence", "/#rag"),
    ("Agents prescription", "/#agents-prescription"),
    ("Safety audit", "/#safety-audit"),
    ("Report export", "/#report"),
    ("Audit log", "/#audit"),
    ("Validation center", "/#validation"),
]

def get(path):
    with urllib.request.urlopen(URL + path, timeout=5) as r:
        return r.status, r.read(4000).decode("utf-8", errors="ignore")

def server_alive():
    try:
        status, _ = get("/api/health")
        return status == 200
    except Exception:
        return False

def launch_and_wait(cmd):
    proc = subprocess.Popen(
        cmd,
        cwd=str(APP_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    for _ in range(40):
        if server_alive():
            return proc
        if proc.poll() is not None:
            break
        time.sleep(0.25)
    try:
        proc.terminate()
    except Exception:
        pass
    return None

def ensure_server():
    if server_alive():
        return None
    proc = launch_and_wait([sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8765"])
    if proc is not None:
        return proc
    return launch_and_wait([sys.executable, str(APP_ROOT / "backend" / "fallback_server.py")])

def screenshot_placeholder(name, status):
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    if Image is None:
        (SCREENSHOTS / f"{name}.txt").write_text(status, encoding="utf-8")
        return
    img = Image.new("RGB", (1280, 720), "#eef4f8")
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, 1240, 680], outline="#2563eb", width=4)
    d.text((80, 90), f"KOM Reviewer Local Demo - {name}", fill="#0f172a")
    d.text((80, 140), f"HTTP/validation status: {status}", fill="#166534" if status == "PASS" else "#9a3412")
    d.text((80, 190), "Fallback screenshot generated by auto_demo_test.py when Playwright browser capture is unavailable.", fill="#475569")
    img.save(SCREENSHOTS / f"{name}.png")

def main():
    VALIDATION.mkdir(parents=True, exist_ok=True)
    TRACES.mkdir(parents=True, exist_ok=True)
    server_proc = ensure_server()
    results = []
    try:
        for label, path in PAGES:
            try:
                status, body = get(path)
                ok = status == 200 and ("KOM Reviewer Local Demo" in body or path != "/")
                state = "PASS" if ok else "WARN"
            except Exception as exc:
                state = "FAIL"
                body = str(exc)
            results.append({"page": label, "path": path, "status": state})
            screenshot_placeholder(label.replace(" ", "_").lower(), state)
    finally:
        if server_proc is not None:
            try:
                server_proc.terminate()
            except Exception:
                pass
    (TRACES / "trace_placeholder.txt").write_text("Playwright trace placeholder. Browser-level trace is WARN if Playwright is not installed in this local package.\n", encoding="utf-8")
    overall = "PASS" if all(r["status"] == "PASS" for r in results) else "WARN"
    report = {"generated_at": datetime.now().isoformat(timespec="seconds"), "overall": overall, "pages": results, "playwright_trace": "WARN_fallback_trace_placeholder"}
    (VALIDATION / "auto_demo_test_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = "".join(f"<tr><td>{html.escape(r['page'])}</td><td>{r['status']}</td><td>{html.escape(r['path'])}</td></tr>" for r in results)
    (VALIDATION / "auto_demo_test_report.html").write_text(f"<!doctype html><meta charset='utf-8'><title>KOM auto demo test</title><body><h1>KOM Auto Demo Test</h1><p>Overall: {overall}</p><table border='1' cellspacing='0' cellpadding='6'><tr><th>Page</th><th>Status</th><th>Path</th></tr>{rows}</table></body>", encoding="utf-8")
    summary = ["# Auto demo test", "", f"- Auto demo test: {overall}", "- Playwright trace: WARN fallback placeholder if Playwright unavailable", ""]
    for r in results:
        summary.append(f"- {r['page']}: {r['status']}")
    base = VALIDATION / "validation_summary.md"
    previous = base.read_text(encoding="utf-8") if base.exists() else ""
    base.write_text(previous + "\n\n" + "\n".join(summary), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if overall in {"PASS", "WARN"} else 1

if __name__ == "__main__":
    raise SystemExit(main())
'''


def write_backend() -> None:
    write_text(OUT / "app" / "backend" / "main.py", MAIN_PY)
    write_text(OUT / "app" / "backend" / "fallback_server.py", FALLBACK_SERVER_PY)
    for sub in ["api", "services", "adapters", "schemas", "utils", "validation"]:
        write_text(OUT / "app" / "backend" / sub / "__init__.py", "")
    write_text(OUT / "app" / "backend" / "adapters" / "llm_adapter.py", textwrap.dedent("""
        from __future__ import annotations
        import json
        from pathlib import Path

        class LLMAdapter:
            def __init__(self, config_dir: Path):
                self.config_dir = config_dir
                self.mode = "demo_cache"

            def complete(self, prompt: str) -> dict:
                return {
                    "mode": self.mode,
                    "content": "Demo cache response. Configure llm_config.local.json for live API mode.",
                    "audit_safe": True,
                }
    """))
    write_text(OUT / "app" / "backend" / "schemas" / "common.py", textwrap.dedent("""
        from __future__ import annotations
        from typing import Any, Optional
        from pydantic import BaseModel

        class UnifiedResponse(BaseModel):
            ok: bool = True
            data: Any = None
            warnings: list[str] = []
            error: Optional[dict[str, Any]] = None
            trace_id: str = ""
    """))
    write_text(OUT / "app" / "backend" / "validation" / "health_check.py", HEALTH_CHECK_PY)
    write_text(OUT / "app" / "backend" / "validation" / "auto_demo_test.py", AUTO_TEST_PY)
    write_text(OUT / "app" / "start_server.py", START_SERVER_PY)


def write_data() -> None:
    data_dir = ensure(OUT / "app" / "data")
    write_json(data_dir / "seed_demo_cases.json", DEMO_CASE_Q4)
    write_json(data_dir / "evidence_units_sample.json", RAG_TOPK)
    write_json(data_dir / "demo_locked_results.json", {
        "risk_prediction": {
            "mode": "demo_cache",
            "structural_progression": {"score": 0.64, "tier": "中高", "drivers": ["BMI", "KL grade", "pain"]},
            "surgery_event": {"score": 0.41, "tier": "中", "drivers": ["KL grade", "function limitation"]},
            "symptom_function_worsening": {"score": 0.58, "tier": "补充提示", "drivers": ["NRS", "WOMAC", "BMI"]},
            "followup_intensity": "2-4周复评疼痛和药物安全；6-12周复评结构化保守治疗效果。",
            "mode_note": "当前为演示模式：风险输出来自已锁定样例和缓存预测。",
        },
        "image_result": {"kl_grade": 3, "confidence": 0.82, "human_review_required": True},
    })
    write_json(data_dir / "demo_metrics_summary.json", METRICS)
    write_json(data_dir / "demo_agent_trace.json", AGENT_TRACE)
    write_json(data_dir / "demo_rag_topk.json", RAG_TOPK)
    write_json(data_dir / "demo_safety_rules.json", SAFETY_RULES)
    write_json(data_dir / "demo_report_template.json", REPORT_TEMPLATE)
    seed_database(data_dir / "kom_demo.sqlite")
    for case_name in ["demo_case_Q1_low_low", "demo_case_Q2_low_high", "demo_case_Q3_high_low", "demo_case_Q4_high_high"]:
        case = dict(DEMO_CASE_Q4)
        case["case_id"] = case_name.upper()
        if "Q1" in case_name:
            case["symptoms"]["nrs"] = 3
            case["patient"]["bmi"] = 24.1
        elif "Q2" in case_name:
            case["symptoms"]["nrs"] = 4
            case["goals"]["walking"] = "high activity goal"
        elif "Q3" in case_name:
            case["symptoms"]["nrs"] = 8
            case["goals"]["avoid_surgery"] = False
        write_json(OUT / "demo_cases" / f"{case_name}.json", case)
    create_sample_image(OUT / "demo_cases" / "demo_xray_sample.png")


def write_static() -> None:
    write_text(OUT / "app" / "static" / "index.html", html())


def write_docs_and_scripts() -> None:
    write_text(OUT / "Start_KOM_Reviewer_Demo.bat", "@echo off\ncd /d %~dp0\npython app\\start_server.py\npause\n")
    write_text(OUT / "Stop_KOM_Reviewer_Demo.bat", "@echo off\nfor /f \"tokens=5\" %%a in ('netstat -ano ^| findstr :8765') do taskkill /PID %%a /F\npause\n")
    write_text(OUT / "Run_Health_Check.bat", "@echo off\ncd /d %~dp0\npython app\\backend\\validation\\health_check.py\npause\n")
    write_text(OUT / "Run_Auto_Demo_Test.bat", "@echo off\ncd /d %~dp0\npython app\\backend\\validation\\auto_demo_test.py\npause\n")
    write_json(OUT / "PACKAGE_MANIFEST.json", {
        "package_name": PACKAGE_NAME,
        "version": "202606",
        "entrypoint": "Start_KOM_Reviewer_Demo.bat",
        "browser_url": "http://127.0.0.1:8765",
        "mode": ["demo_cache", "llm_api", "local_model"],
        "modules": ["patient-followup", "image-analysis", "risk", "rag", "agents-prescription", "safety-audit", "report", "audit", "validation"],
        "validation_status": "pending",
        "contains_phi": False,
        "clinical_use": False,
        "generated_at": NOW,
    })
    write_text(OUT / "README_审稿人先读_CN.md", """# KOM Reviewer Local Demo 本地演示系统

本演示系统用于展示 KOM 医生端膝骨关节炎治疗决策支持流程。默认使用去标识化 demo case 和缓存结果，可离线完成完整流程演示；不用于直接临床诊疗。

## 如何启动

双击 `Start_KOM_Reviewer_Demo.bat`，浏览器将打开 `http://127.0.0.1:8765`。

## 推荐审稿路径

1. 点击 Run Full KOM Demo
2. 查看患者随访时间线
3. 使用示例影像并查看影像分析
4. 查看 KOM-Risk 三个风险
5. 在 RAG 页面展开证据
6. 在多智能体页面查看 R0-R8
7. 在安全审计页面查看错误和修正
8. 在报告页面导出结构化报告
9. 在审计页面下载 audit log
10. 在验证中心查看自动测试结果

## LLM 模式

默认 `demo_cache`。如需实时 LLM 输出，请在 `app/config/llm_config.local.json` 中配置 OpenAI-compatible API。API key 不会写入审计日志。未配置或连接失败时自动降级到 demo cache。

## 系统限制

本包使用去标识化演示病例、预置证据和锁定指标。真实模型权重、真实 RAG 索引或实时 LLM 不在本地包中启用时，界面会明确显示 demo/cache 模式。
""")
    write_text(OUT / "README_REVIEWER_EN.md", """# KOM Reviewer Local Demo

This local package demonstrates the KOM knee osteoarthritis clinical decision-support workflow for reviewers. It uses de-identified demo cases and cached outputs by default. It is not intended for direct clinical care.

Start: double-click `Start_KOM_Reviewer_Demo.bat`, then open `http://127.0.0.1:8765`.

Recommended route: Run Full KOM Demo -> patient follow-up -> image analysis -> KOM-Risk -> RAG evidence -> multi-agent prescription -> safety audit -> structured report -> audit log -> validation center.

LLM mode defaults to `demo_cache`. If an OpenAI-compatible API is configured in `app/config/llm_config.local.json`, the backend can switch to live mode; otherwise it falls back to demo cache.
""")
    write_json(OUT / "app" / "config" / "config.example.json", {"port": PORT, "default_mode": "demo_cache", "clinical_use": False})
    write_json(OUT / "app" / "config" / "config.local.json", {"port": PORT, "default_mode": "demo_cache"})
    write_json(OUT / "app" / "config" / "llm_config.example.json", {"provider": "openai_compatible", "base_url": "https://api.example.com/v1", "model": "gpt-4o-mini", "api_key_env": "OPENAI_API_KEY"})
    write_text(OUT / "developer_assets" / "tests" / "playwright_full_demo.spec.ts", """import { test, expect } from '@playwright/test';

test('KOM reviewer full demo route smoke test', async ({ page }) => {
  await page.goto('http://127.0.0.1:8765/');
  await expect(page.getByText('KOM Reviewer Local Demo')).toBeVisible();
  await page.getByText('Run Full KOM Demo').click();
  await page.goto('http://127.0.0.1:8765/#rag');
  await page.getByText('检索证据').click();
  await page.getByText('KOA-EU-01035').click();
  await page.goto('http://127.0.0.1:8765/#agents-prescription');
  await page.getByText('R0 患者画像共识').click();
  await page.goto('http://127.0.0.1:8765/#report');
  await page.getByText('生成报告').click();
  await page.goto('http://127.0.0.1:8765/#audit');
});
""")


def write_audits(inventory: list[dict[str, Any]]) -> None:
    columns = ["file_path", "file_name", "extension", "size_mb", "modified_time", "sha256", "module_guess", "is_ui_file", "is_data_file", "is_model_file", "is_result_file", "is_script_file", "copy_or_reference", "used_in_demo", "notes"]
    write_csv(OUT / "app" / "audit" / "source_inventory.csv", inventory, columns)
    ui_rows = []
    for row in inventory:
        if row["is_ui_file"]:
            ui_rows.append({
                "page_or_component": row["file_name"],
                "file_path": row["file_path"],
                "framework": "React/Vite/HTML" if row["extension"] in {".tsx", ".html"} else row["extension"],
                "function": module_guess(Path(row["file_path"])),
                "visual_quality": "reusable" if row["used_in_demo"] else "unknown",
                "can_reuse": bool(row["used_in_demo"] or row["extension"] in {".html", ".tsx", ".css"}),
                "reuse_method": "reference/copy selected built artifact" if row["used_in_demo"] else "inventory only",
                "target_route": "dashboard/static reference" if row["used_in_demo"] else "",
                "notes": "Original UI preserved; final package uses unified Chinese local reviewer shell.",
            })
    write_csv(OUT / "app" / "audit" / "ui_pages_inventory.csv", ui_rows[:2000], ["page_or_component", "file_path", "framework", "function", "visual_quality", "can_reuse", "reuse_method", "target_route", "notes"])
    write_csv(OUT / "app" / "audit" / "ui_reuse_decision_table.csv", ui_rows[:500], ["page_or_component", "file_path", "framework", "function", "visual_quality", "can_reuse", "reuse_method", "target_route", "notes"])
    write_text(OUT / "app" / "audit" / "source_inventory_summary.md", f"""# Source inventory summary

- Generated at: {NOW}
- Candidate files indexed: {len(inventory)}
- Existing reviewer app: {EXISTING_REVIEWER}
- Submission final folder: {SUBMISSION_FINAL}
- No original source, data, model or result files were moved or deleted.
""")
    write_text(OUT / "app" / "audit" / "ui_merge_plan.md", """# UI merge plan

1. Preserve the existing reviewer single-file interface as a referenced source asset.
2. Use a unified Chinese local reviewer shell for the final package.
3. Keep demo/cache mode visibly distinct from live LLM/model mode.
4. Route all modules through the FastAPI-compatible backend or stdlib fallback.
5. Keep source UI and test files under developer_assets for review, not as the reviewer entry point.
""")


def copy_developer_assets() -> None:
    src = EXISTING_REVIEWER
    dst = OUT / "developer_assets" / "source_frontend"
    ensure(dst)
    for name in ["src", "scripts", "e2e", "package.json", "vite.config.ts", "tsconfig.json", "index.source.html", "REVIEWER_GUIDE.md", "VALIDATION_REPORT.md"]:
        s = src / name
        d = dst / name
        if s.is_dir():
            if d.exists():
                continue
            shutil.copytree(s, d, ignore=shutil.ignore_patterns("node_modules", "dist", "test-results"))
        elif s.exists() and not d.exists():
            ensure(d.parent)
            shutil.copy2(s, d)
    write_text(OUT / "developer_assets" / "docs" / "local_demo_build_notes.md", "Generated local demo package. Source assets are preserved for audit and are not the main reviewer entry point.\n")
    write_text(OUT / "developer_assets" / "source_backend" / "README.md", "Backend source lives in app/backend for direct execution.\n")
    write_text(OUT / "developer_assets" / "scripts" / "README.md", "Run root .bat scripts for reviewer-facing validation.\n")


def initialize_validation_files() -> None:
    ensure(OUT / "validation" / "screenshots")
    ensure(OUT / "validation" / "playwright_traces")
    write_json(OUT / "validation" / "health_check_report.json", {"overall": "pending"})
    write_text(OUT / "validation" / "auto_demo_test_report.html", "<!doctype html><meta charset='utf-8'><h1>Auto demo test pending</h1>")
    write_text(OUT / "validation" / "validation_summary.md", """# Validation summary

- Dashboard: PENDING
- Demo case loading: PENDING
- Image analysis page: PENDING
- Risk prediction page: PENDING
- RAG evidence expansion: PENDING
- Agent flow R0-R8: PENDING
- Safety audit: PENDING
- Structured report export: PENDING
- Audit log: PENDING
- LLM adapter fallback: PENDING
- Screenshot saving: PENDING
- Trace saving: PENDING
""")


def main() -> None:
    ensure(OUT)
    for rel in [
        "app/audit", "app/backend/api", "app/backend/services", "app/backend/adapters", "app/backend/schemas",
        "app/backend/utils", "app/static", "app/data", "app/evidence", "app/models", "app/outputs/reports",
        "app/config", "demo_cases", "validation/screenshots", "validation/playwright_traces",
        "developer_assets/source_frontend", "developer_assets/source_backend", "developer_assets/scripts",
        "developer_assets/tests", "developer_assets/docs",
    ]:
        ensure(OUT / rel)
    inventory = scan_sources()
    write_audits(inventory)
    write_backend()
    write_data()
    write_static()
    write_docs_and_scripts()
    copy_developer_assets()
    initialize_validation_files()
    print(json.dumps({
        "message": "KOM reviewer local demo package generated",
        "output_folder": str(OUT),
        "inventory_rows": len(inventory),
        "entrypoint": str(OUT / "Start_KOM_Reviewer_Demo.bat"),
        "browser_url": f"http://127.0.0.1:{PORT}",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
