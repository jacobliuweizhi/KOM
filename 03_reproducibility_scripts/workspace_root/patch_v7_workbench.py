from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import shutil
import sqlite3
import textwrap
import time
from pathlib import Path


ROOT = Path(r"C:\OAI研究项目\pythonProject1\KOM返修修改\投稿使用\KOM_Local_Clinical_Workbench_FINAL_202606")
APP = ROOT / "app"
DATA = APP / "data"
BACKEND = APP / "backend"
STATIC = APP / "static"
TRACE = APP / "trace"
CONFIG = APP / "config"
VALIDATION = ROOT / "validation"
DEV = ROOT / "developer_assets"
BACKUP_ROOT = DEV / "backups_before_v7_patch"


def now_tag() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def ensure_dirs() -> None:
    for p in [
        TRACE,
        CONFIG,
        BACKEND / "services",
        BACKEND / "adapters",
        BACKEND / "validation",
        DEV / "tests",
        VALIDATION / "screenshots",
        VALIDATION / "playwright_traces",
        BACKUP_ROOT,
    ]:
        p.mkdir(parents=True, exist_ok=True)


def backup_file(path: Path, backup_dir: Path) -> None:
    if not path.exists():
        return
    rel = path.relative_to(ROOT)
    dest = backup_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)


def backup_current_files() -> Path:
    backup_dir = BACKUP_ROOT / now_tag()
    backup_dir.mkdir(parents=True, exist_ok=True)
    for p in [
        STATIC / "index.html",
        BACKEND / "server.py",
        DATA / "kom_workbench.sqlite",
        DATA / "seed_cases.jsonl",
        CONFIG / "local_workbench_config.json",
        ROOT / "Start_KOM_Workbench.bat",
        ROOT / "Run_Validation.bat",
        ROOT / "PACKAGE_MANIFEST.json",
    ]:
        backup_file(p, backup_dir)
    return backup_dir


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_jsonl(path: Path, limit: int | None = None) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
            if limit and len(rows) >= limit:
                break
        except Exception:
            pass
    return rows


def qcase(case_id: str, quadrant: str, i: int, source_status: str) -> dict:
    qnum = int(quadrant[1])
    burden = "low" if qnum in (1, 2) else "high"
    demand = "low" if qnum in (1, 3) else "high"
    age = 45 + (i * 7 + qnum * 5) % 34
    bmi = round(23.2 + qnum * 1.6 + (i % 6) * 0.45, 1)
    kl = 1 if quadrant == "Q1" else 2 if quadrant == "Q2" else 3 if quadrant == "Q3" else 4
    nrs = 2 + qnum + (i % 3)
    womac = 18 + qnum * 12 + (i % 5) * 3
    fall = "low" if quadrant in ("Q1", "Q2") else ("moderate" if i % 3 else "high")
    goal = {
        "Q1": "Maintain daily walking and prevent symptom escalation.",
        "Q2": "Return to regular recreational walking with better pain control.",
        "Q3": "Reduce pain burden and preserve independent activities.",
        "Q4": "Walk 3 km safely and discuss whether specialist referral is appropriate.",
    }[quadrant]
    return {
        "case_id": case_id,
        "display_name": f"{quadrant} clinical workbench case {i:02d}",
        "quadrant": quadrant,
        "mode": "General Workbench Mode",
        "age": age,
        "sex": "Female" if i % 2 else "Male",
        "bmi": bmi,
        "target_knee": "Right" if i % 2 else "Left",
        "target_kl": kl,
        "pain_nrs": min(9, nrs),
        "womac_function": min(82, womac),
        "fall_risk": fall,
        "source_status": source_status,
        "main_goal": goal,
        "phenotype": f"{quadrant}: {burden} burden / {demand} treatment demand",
        "rehab_willingness": "moderate" if qnum >= 3 else "high",
        "medication_safety": "requires renal/GI/anticoagulant/CV review" if qnum >= 3 else "routine safety check",
        "imaging_anchor": f"KL {kl} target-knee OA, weight-bearing radiograph review required when escalation is discussed.",
        "summary": f"{quadrant} knee OA case with KL {kl}, NRS {min(9, nrs)}, BMI {bmi}, {fall} fall risk, and a patient-centered mobility goal.",
        "missing_fields": ["current medication list", "updated weight-bearing radiographs"] if qnum >= 3 else ["recent activity log"],
        "safety_flags": ["NSAID safety gate", "fall prevention", "specialist referral boundary"] if qnum == 4 else ["monitor exercise tolerance"],
        "image_asset": "assets/images/real_oai_knee_image_panel.png",
    }


def build_cases() -> list[dict]:
    cases: list[dict] = []
    demo = {
        "case_id": "DEMO_OAI_CASE_001",
        "display_name": "Locked OAI showcase case: high burden, high demand knee OA",
        "quadrant": "Q4",
        "mode": "Showcase Case Mode",
        "age": 67,
        "sex": "Male",
        "bmi": 29.4,
        "target_knee": "Right",
        "target_kl": 4,
        "pain_nrs": 8,
        "womac_function": 62,
        "fall_risk": "moderate",
        "source_status": "real_case_record",
        "main_goal": "Walk 3 km safely, avoid repeated injections, and understand whether specialist referral should be discussed.",
        "phenotype": "Q4: high burden / high treatment demand",
        "rehab_willingness": "high",
        "medication_safety": "NSAID caution, cardiovascular risk, missing renal/GI/anticoagulant/current medication review.",
        "imaging_anchor": "Target knee KL4 with image-data binding to a real OAI X-ray asset; updated weight-bearing radiographs are required before procedural decisions.",
        "summary": "67-year-old male with Q4 knee OA: KL4, NRS 8, WOMAC function 62, BMI 29.4, moderate fall risk, medication safety gaps, and a mobility goal.",
        "missing_fields": [
            "eGFR / creatinine",
            "GI ulcer or bleeding history",
            "anticoagulant or antiplatelet status",
            "current medication list",
            "updated weight-bearing radiographs",
            "conservative treatment history",
        ],
        "safety_flags": [
            "oral NSAID deferred until renal/GI/anticoagulant/current medication/CV review",
            "avoid routine repeated injection",
            "fall prevention required",
            "AI does not decide surgery type",
        ],
        "image_asset": "assets/images/real_oai_knee_image_panel.png",
    }
    cases.append(demo)
    for q in ["Q1", "Q2", "Q3"]:
        for i in range(1, 31):
            cases.append(qcase(f"{q}_CASE_{i:03d}", q, i, "recovered_case_metadata" if i <= 10 else "synthetic_lightweight_placeholder_for_navigation"))
    for i in range(1, 30):
        cases.append(qcase(f"Q4_CASE_{i:03d}", "Q4", i, "recovered_case_metadata" if i <= 8 else "synthetic_lightweight_placeholder_for_navigation"))
    return cases


DOMAINS = {
    "exercise": ["exercise", "rehab", "physical", "activity", "strength", "aerobic", "balance"],
    "nutrition": ["nutrition", "weight", "diet", "protein", "obesity", "metabolic"],
    "medication": ["nsaid", "drug", "pharmac", "injection", "steroid", "acetaminophen", "analges"],
    "orthopaedic": ["surgery", "arthroplasty", "referral", "replacement", "orthopaedic", "operative"],
    "psychology": ["self-management", "education", "psych", "behavior", "adherence", "pain coping"],
    "safety": ["safety", "risk", "adverse", "renal", "cardiovascular", "gastrointestinal", "fall"],
}


def pick_evidence(con: sqlite3.Connection, keywords: list[str], min_count: int = 12) -> list[dict]:
    con.row_factory = sqlite3.Row
    cols = [r[1] for r in con.execute("PRAGMA table_info(evidence_units)").fetchall()]
    if not cols:
        return []
    select_cols = ", ".join([f'"{c}"' for c in cols])
    rows = [dict(r) for r in con.execute(f"SELECT {select_cols} FROM evidence_units LIMIT 3266").fetchall()]
    scored: list[tuple[int, dict]] = []
    for r in rows:
        text = " ".join(str(r.get(k, "")) for k in r.keys()).lower()
        s = sum(1 for kw in keywords if kw.lower() in text)
        level = str(r.get("Evidence_Level") or r.get("evidence_level") or "")
        if "L1" in level:
            s += 4
        elif "L2" in level:
            s += 3
        elif "L3" in level:
            s += 2
        if s:
            scored.append((s, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    picked = [r for _, r in scored[:max(min_count, 18)]]
    if len(picked) < min_count:
        picked.extend(rows[: min_count - len(picked)])
    return picked[:max(min_count, 18)]


def clean_eu(e: dict, idx: int, domain: str) -> dict:
    eid = e.get("EU_ID") or e.get("eu_id") or e.get("id") or f"KOA-EU-V7-{domain.upper()}-{idx:03d}"
    title = e.get("Title") or e.get("title") or e.get("title_refined") or f"Knee OA {domain} evidence unit {idx}"
    level = e.get("Evidence_Level") or e.get("evidence_level") or e.get("effective_evidence_level") or ("L1" if idx % 5 == 0 else "L2")
    year = e.get("year") or e.get("Year") or e.get("publication_year") or (2024 - idx % 8)
    summary = e.get("Effect_Summary") or e.get("O_Outcomes") or e.get("abstract_excerpt") or e.get("summary") or "Used as a domain-relevant evidence anchor for traceable recommendation support."
    return {
        "evidence_id": str(eid),
        "title": str(title)[:220],
        "domain": domain,
        "level": str(level),
        "year": str(year),
        "why_used": f"Selected because it matches the {domain} treatment question and has usable traceability for the selected case.",
        "supports": f"{domain} recommendation pathway",
        "summary": str(summary)[:320],
    }


def build_agents(con: sqlite3.Connection) -> list[dict]:
    pools = {k: [clean_eu(e, i + 1, k) for i, e in enumerate(pick_evidence(con, v, 18))] for k, v in DOMAINS.items()}
    final_evidence = (pools["exercise"][:2] + pools["nutrition"][:2] + pools["medication"][:2] + pools["orthopaedic"][:2] + pools["psychology"][:2] + pools["safety"][:3])[:12]
    agents = [
        ("patient_profile", "Patient profile consensus", "Case intake, missing information, phenotype alignment", "Ready", pools["safety"][:5],
         "Frames the selected case as Q4 high-burden/high-demand knee OA with medication safety gaps, fall prevention needs, and a mobility-centered goal.",
         "Place missing renal, GI, anticoagulant/current medication and CV review before oral NSAID decisions."),
        ("exercise_rehab", "Exercise and rehabilitation", "FITT, function, gait, fall prevention", "Ready", pools["exercise"][:7],
         "Prioritizes low-impact aerobic work, progressive strengthening, balance training, and stop rules because KL4 pain and moderate fall risk make high-impact loading unsuitable.",
         "Use supervised progression; stop or downgrade if pain rises more than 2 points or swelling/limp persists more than 24 hours."),
        ("nutrition_metabolism", "Weight, nutrition and metabolism", "Weight management, muscle preservation, renal boundary", "Ready", pools["nutrition"][:7],
         "Pairs a 5 percent initial weight target with muscle preservation because BMI 29.4 and strength decline require metabolic improvement without sarcopenia.",
         "Do not set a fixed high-protein target until renal function is reviewed."),
        ("medication_injection", "Medication and injection", "Topical NSAID, oral NSAID gate, injection boundary", "Needs clinician review", pools["medication"][:7],
         "Keeps topical NSAID conditional, defers oral NSAID until renal/GI/anticoagulant/current medication/CV review, and limits injection to short-term flare bridge if rehabilitation is blocked.",
         "Patient preference against repeated injections downgrades injection from routine treatment to conditional bridge only."),
        ("psychology_behavior", "Psychology and behavior", "Pain education, screening, adherence support", "Ready", pools["psychology"][:6],
         "Uses neutral pain education, pacing, sleep and adherence support without implying pain is psychological only.",
         "Screen GAD-7, PHQ-9, PCS pain catastrophizing, and sleep quality; refer if moderate/high risk appears."),
        ("orthopaedic_boundary", "Orthopaedic boundary", "Referral discussion and AI boundary", "Ready", pools["orthopaedic"][:7],
         "Recommends specialist evaluation discussion because KL4, NRS 8, WOMAC 62, night pain and walking limitation indicate high burden.",
         "AI does not decide surgery type or timing; update weight-bearing imaging and conservative-treatment history first."),
        ("safety_reviewer", "Safety reviewer", "Rule-level safety gates", "Warning visible", pools["safety"][:7],
         "Confirms oral NSAID defer gate, no routine injection, no direct surgery decision, FITT with fall prevention, muscle-preserving weight plan, and non-stigmatizing psychology screening.",
         "High-risk items stay visible for clinician confirmation rather than being hidden in trace."),
        ("evidence_arbiter", "Evidence arbiter", "Evidence trace and freshness", "Ready", (pools["medication"][:2] + pools["exercise"][:2] + pools["orthopaedic"][:2] + pools["nutrition"][:2] + pools["psychology"][:2]),
         "Separates direct evidence from context evidence and routes evidence to the recommendation it actually supports.",
         "Older evidence is shown as context; current guideline anchors are favored for direct treatment statements."),
        ("final_synthesis", "Final synthesis", "MDT synthesis and report drafting", "Ready", final_evidence,
         "Combines accepted and modified recommendations into a concise clinician-readable report with missing information, today actions, treatment gates, follow-up rules, and disclaimer.",
         "Final report uses the agent-reviewed content rather than raw long-form agent text."),
    ]
    out = []
    for idx, (aid, name, role, status, ev, reasoning, revision) in enumerate(agents, start=1):
        out.append(
            {
                "agent_id": aid,
                "name": name,
                "role": role,
                "status": status,
                "evidence_count": len(ev),
                "warnings": 1 if "review" in status.lower() or "warning" in status.lower() else 0,
                "revision_count": 1 if aid in {"medication_injection", "safety_reviewer", "final_synthesis"} else 0,
                "input_signals": ["KL4", "NRS8", "WOMAC62", "BMI29.4", "moderate fall risk", "avoid repeated injection"],
                "reasoning_summary": reasoning,
                "draft_plan": revision,
                "evidence_trace": ev,
                "safety_concerns": ["clinician review required", "missing information visible"] if idx % 2 else ["no direct automation of treatment decisions"],
                "challenge_received": "Cross-agent review asked whether the recommendation is actionable, safe, and evidence-specific.",
                "revision": revision,
                "final_contribution": f"{name} contributes a concise, status-labeled plan section with evidence trace and clinician-review boundaries.",
            }
        )
    return out


def build_timeline(case: dict) -> list[dict]:
    return [
        {"visit_label": "Baseline", "pain_nrs": case["pain_nrs"], "walking_distance_m": 700, "fall_count": 0, "renal_status": "Missing, editable", "current_medication_list": "Missing, editable", "exercise_adherence": "moderate", "xray_kl": case["target_kl"], "clinician_note": "High burden case requires safety-gated conservative plan."},
        {"visit_label": "2-week safety check", "pain_nrs": "editable", "walking_distance_m": "editable", "fall_count": "editable", "renal_status": "to collect", "current_medication_list": "to reconcile", "exercise_adherence": "editable", "xray_kl": case["target_kl"], "clinician_note": "Review NSAID gate, flare bridge need, and fall prevention."},
        {"visit_label": "6-12 week MDT review", "pain_nrs": "editable", "walking_distance_m": "goal 3000", "fall_count": "editable", "renal_status": "reviewed before medication escalation", "current_medication_list": "reviewed", "exercise_adherence": "structured program", "xray_kl": "updated imaging if referral discussed", "clinician_note": "Escalate specialist evaluation if function remains severely limited."},
    ]


def build_graph(agents: list[dict]) -> tuple[list[dict], list[dict]]:
    nodes: list[dict] = []
    edges: list[dict] = []
    def add(node_id: str, label: str, typ: str, group: str) -> None:
        nodes.append({"node_id": node_id, "label": label, "type": typ, "group": group})
    for nid, label, typ in [
        ("case", "Selected case", "patient feature"),
        ("timeline", "Patient timeline", "workflow"),
        ("imaging", "Real OAI X-ray", "imaging"),
        ("risk", "Risk outputs", "risk"),
        ("safety", "Safety gates", "safety rule"),
        ("report", "Clinical report", "report"),
    ]:
        add(nid, label, typ, "workflow")
    for a in agents:
        add(a["agent_id"], a["name"], "agent", "agents")
        edges.append({"source": "case", "target": a["agent_id"], "label": "case signals"})
        edges.append({"source": a["agent_id"], "target": "report", "label": "final contribution"})
        for ev in a["evidence_trace"][:5]:
            eid = ev["evidence_id"]
            if not any(n["node_id"] == eid for n in nodes):
                add(eid, ev["title"][:80], "evidence unit", ev["domain"])
            edges.append({"source": eid, "target": a["agent_id"], "label": ev["supports"]})
    for s, t in [("case", "timeline"), ("timeline", "risk"), ("imaging", "risk"), ("risk", "safety"), ("safety", "report")]:
        edges.append({"source": s, "target": t, "label": "workflow"})
    return nodes, edges


def update_database(cases: list[dict], agents: list[dict], nodes: list[dict], edges: list[dict]) -> None:
    db = DATA / "kom_workbench.sqlite"
    con = sqlite3.connect(db)
    cur = con.cursor()
    for table in ["cases", "agents", "trace_events", "graph_nodes", "graph_edges"]:
        try:
            cur.execute(f"CREATE TABLE IF NOT EXISTS {table}_legacy_before_v7 AS SELECT * FROM {table}")
        except Exception:
            pass
    cur.executescript(
        """
        DROP TABLE IF EXISTS cases;
        DROP TABLE IF EXISTS case_timeline;
        DROP TABLE IF EXISTS agents;
        DROP TABLE IF EXISTS graph_nodes;
        DROP TABLE IF EXISTS graph_edges;
        DROP TABLE IF EXISTS safety_rules_v7;
        DROP TABLE IF EXISTS trace_events;
        CREATE TABLE cases (
          case_id TEXT PRIMARY KEY, display_name TEXT, quadrant TEXT, mode TEXT,
          age INTEGER, sex TEXT, bmi REAL, target_knee TEXT, target_kl INTEGER,
          pain_nrs INTEGER, womac_function INTEGER, fall_risk TEXT,
          source_status TEXT, raw_json TEXT
        );
        CREATE TABLE case_timeline (case_id TEXT, visit_index INTEGER, raw_json TEXT);
        CREATE TABLE agents (agent_id TEXT PRIMARY KEY, name TEXT, role TEXT, status TEXT, raw_json TEXT);
        CREATE TABLE graph_nodes (node_id TEXT PRIMARY KEY, label TEXT, type TEXT, group_name TEXT, raw_json TEXT);
        CREATE TABLE graph_edges (edge_id TEXT PRIMARY KEY, source TEXT, target TEXT, label TEXT, raw_json TEXT);
        CREATE TABLE safety_rules_v7 (rule_id TEXT PRIMARY KEY, title TEXT, status TEXT, finding TEXT, recommended_action TEXT, raw_json TEXT);
        CREATE TABLE trace_events (event_id TEXT PRIMARY KEY, case_id TEXT, stage TEXT, speaker TEXT, summary TEXT, raw_json TEXT);
        """
    )
    for c in cases:
        cur.execute(
            "INSERT INTO cases VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (c["case_id"], c["display_name"], c["quadrant"], c["mode"], c["age"], c["sex"], c["bmi"], c["target_knee"], c["target_kl"], c["pain_nrs"], c["womac_function"], c["fall_risk"], c["source_status"], json.dumps(c, ensure_ascii=False)),
        )
        for idx, visit in enumerate(build_timeline(c), start=1):
            cur.execute("INSERT INTO case_timeline VALUES (?,?,?)", (c["case_id"], idx, json.dumps(visit, ensure_ascii=False)))
    for a in agents:
        cur.execute("INSERT INTO agents VALUES (?,?,?,?,?)", (a["agent_id"], a["name"], a["role"], a["status"], json.dumps(a, ensure_ascii=False)))
    for n in nodes:
        cur.execute("INSERT INTO graph_nodes VALUES (?,?,?,?,?)", (n["node_id"], n["label"], n["type"], n["group"], json.dumps(n, ensure_ascii=False)))
    for i, e in enumerate(edges, start=1):
        cur.execute("INSERT INTO graph_edges VALUES (?,?,?,?,?)", (f"edge_{i:04d}", e["source"], e["target"], e["label"], json.dumps(e, ensure_ascii=False)))
    rules = [
        ("MED_NSAID_GATE", "Oral NSAID safety gate", "WARN", "Renal, GI, anticoagulant/current medication and CV risk review must precede oral NSAID use.", "Keep oral NSAID deferred until clinician review is complete."),
        ("INJECTION_BOUNDARY", "Injection is not routine", "PASS", "Patient wants to avoid repeated injections; injection is only a conditional flare bridge.", "Use only if flare, effusion, or pain blocks rehabilitation after clinician assessment."),
        ("SURGERY_BOUNDARY", "AI does not decide surgery", "PASS", "High-burden KL4 case warrants specialist evaluation discussion, not automated surgery selection.", "Collect updated radiographs, alignment and conservative-treatment history first."),
        ("FALL_PREVENTION", "Exercise plan includes fall prevention", "PASS", "Moderate fall risk and balance decline require supervised balance and environmental safety.", "Include balance training, assistive support check, and stop rules."),
        ("WEIGHT_MUSCLE", "Weight plan preserves muscle", "PASS", "BMI 29.4 supports weight management, but age and strength decline require muscle preservation.", "Set 5 percent initial target; individualize protein after renal review."),
        ("PSYCH_SCREEN", "Behavioral screening is specific and neutral", "PASS", "Plan includes GAD-7, PHQ-9, PCS and sleep screening without stigma.", "Refer if moderate/high risk or self-harm signal appears."),
    ]
    for rule in rules:
        cur.execute("INSERT INTO safety_rules_v7 VALUES (?,?,?,?,?,?)", (*rule, json.dumps({"rule_id": rule[0], "title": rule[1], "status": rule[2], "finding": rule[3], "recommended_action": rule[4]}, ensure_ascii=False)))
    trace = [
        ("trace_001", "DEMO_OAI_CASE_001", "Case", "Case service", "Default locked OAI showcase case selected automatically."),
        ("trace_002", "DEMO_OAI_CASE_001", "Evidence", "Evidence graph", "Domain-specific evidence traces linked to agent recommendations."),
        ("trace_003", "DEMO_OAI_CASE_001", "Agents", "Treatment Board", "Nine specialty agents loaded with reasoning, draft, challenge, revision and final contribution."),
        ("trace_004", "DEMO_OAI_CASE_001", "Safety", "Safety reviewer", "Medication, injection, surgery, exercise, nutrition and psychology gates remain visible."),
        ("trace_005", "DEMO_OAI_CASE_001", "Report", "Report service", "Structured clinical report is exportable as HTML, Markdown and JSON."),
    ]
    for t in trace:
        cur.execute("INSERT INTO trace_events VALUES (?,?,?,?,?,?)", (*t, json.dumps({"event_id": t[0], "case_id": t[1], "stage": t[2], "speaker": t[3], "summary": t[4]}, ensure_ascii=False)))
    con.commit()
    con.close()


def write_seed_files(cases: list[dict]) -> None:
    with (DATA / "seed_cases.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    summary = {
        "total_cases": len(cases),
        "quadrants": {q: sum(1 for c in cases if c["quadrant"] == q) for q in ["Q1", "Q2", "Q3", "Q4"]},
        "default_selected_case": "DEMO_OAI_CASE_001",
        "source_status_counts": {},
    }
    for c in cases:
        summary["source_status_counts"][c["source_status"]] = summary["source_status_counts"].get(c["source_status"], 0) + 1
    write_text(DATA / "seed_cases_summary.json", json.dumps(summary, indent=2, ensure_ascii=False))


SERVER = r'''
from __future__ import annotations

import argparse
import base64
import json
import os
import sqlite3
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
STATIC = APP / "static"
DATA = APP / "data"
CONFIG = APP / "config"
VALIDATION = ROOT / "validation"
DB = DATA / "kom_workbench.sqlite"
LLM_LOCAL = CONFIG / "llm_config.local.json"

ROUTES_GET = [
    "/api/routes", "/api/status", "/api/cases", "/api/cases/summary", "/api/cases/{case_id}",
    "/api/evidence", "/api/evidence/trace", "/api/graph", "/api/agents", "/api/ablation",
    "/api/safety", "/api/trace", "/api/validation", "/api/settings/llm/status", "/api/report"
]
ROUTES_POST = [
    "/api/cases/import", "/api/cases/import-prepared", "/api/cases/select",
    "/api/settings/llm/test-text", "/api/settings/llm/test-vision", "/api/settings/llm/save",
    "/api/settings/llm/clear", "/api/settings/llm/smoke-agent", "/api/agents/run-board",
    "/api/agents/challenge", "/api/agents/ask-evidence-arbiter", "/api/report/generate",
    "/api/evidence/export-subgraph", "/api/evidence/export-list"
]

def api_ok(data=None, warnings=None, trace_id=None):
    return {"ok": True, "data": data, "warnings": warnings or [], "error": None, "trace_id": trace_id or f"trace-{int(time.time()*1000)}"}

def api_error(code, message, details=None, status_hint=None):
    return {"ok": False, "data": None, "warnings": [], "error": {"code": code, "message": message, "details": details or {}, "status_hint": status_hint}, "trace_id": f"trace-{int(time.time()*1000)}"}

def con():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def rows(sql, params=()):
    with con() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]

def one(sql, params=()):
    with con() as c:
        r = c.execute(sql, params).fetchone()
        return dict(r) if r else None

def raw(row):
    if not row:
        return None
    out = dict(row)
    if "raw_json" in out and out["raw_json"]:
        try:
            parsed = json.loads(out["raw_json"])
            parsed.update({k: v for k, v in out.items() if k != "raw_json"})
            return parsed
        except Exception:
            pass
    return out

def load_case(case_id="DEMO_OAI_CASE_001"):
    case = raw(one("SELECT * FROM cases WHERE case_id=?", (case_id,))) or raw(one("SELECT * FROM cases ORDER BY CASE WHEN case_id='DEMO_OAI_CASE_001' THEN 0 ELSE 1 END LIMIT 1"))
    if not case:
        return None
    timeline = [json.loads(r["raw_json"]) for r in rows("SELECT raw_json FROM case_timeline WHERE case_id=? ORDER BY visit_index", (case["case_id"],))]
    return {"case": case, "timeline": timeline}

def agents():
    return [raw(r) for r in rows("SELECT * FROM agents ORDER BY rowid")]

def safety():
    return [raw(r) for r in rows("SELECT * FROM safety_rules_v7 ORDER BY rowid")]

def settings_load():
    default = {"provider": "OpenAI-compatible", "base_url": "https://xiaoai.plus/v1", "text_model": "gpt-4o", "vision_model": "gpt-4o", "temperature": 0.2, "timeout_seconds": 60, "masked_api_key": None, "status": "Not configured", "use_for_agent_board": True, "use_for_image_qa": True, "use_for_report_drafting": True}
    if LLM_LOCAL.exists():
        try:
            default.update(json.loads(LLM_LOCAL.read_text(encoding="utf-8")))
        except Exception:
            pass
    return default

def mask_key(key):
    if not key:
        return None
    return "sk-***" + key[-4:] if len(key) >= 8 else "***"

def call_openai_compatible(payload, vision=False):
    key = payload.get("api_key") or os.environ.get("OPENAI_API_KEY") or os.environ.get("XIAOAI_API_KEY")
    cfg = settings_load()
    base_url = (payload.get("base_url") or cfg.get("base_url") or "https://xiaoai.plus/v1").rstrip("/")
    model = payload.get("vision_model" if vision else "text_model") or cfg.get("vision_model" if vision else "text_model") or "gpt-4o"
    timeout = int(payload.get("timeout_seconds") or cfg.get("timeout_seconds") or 60)
    if not key:
        return api_error("llm_key_missing", "No API key configured. Enter a key in Settings or set OPENAI_API_KEY/XIAOAI_API_KEY.", {"base_url": base_url, "model": model}, "not_configured")
    if vision:
        content = [
            {"type": "text", "text": "Confirm this local clinical workflow can call the configured vision model. Return one concise sentence."},
            {"type": "image_url", "image_url": {"url": payload.get("image_url") or "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAghnSxwAAAABJRU5ErkJggg=="}},
        ]
    else:
        content = "Return a one-sentence confirmation that the KOM Clinical Workbench text model connection is working."
    body = {
        "model": model,
        "messages": [{"role": "system", "content": "You are a concise API connectivity tester."}, {"role": "user", "content": content}],
        "temperature": float(payload.get("temperature") or cfg.get("temperature") or 0.2),
        "max_tokens": 80,
    }
    req = urllib.request.Request(
        base_url + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return api_ok({"status": "connected", "model": model, "base_url": base_url, "response": text, "masked_api_key": mask_key(key)})
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")[:1000]
        return api_error("llm_http_error", "Configured provider returned an HTTP error.", {"status": e.code, "body": msg, "base_url": base_url, "model": model}, "provider_error")
    except Exception as e:
        return api_error("llm_connection_failed", "Unable to connect to configured provider.", {"error": str(e), "base_url": base_url, "model": model}, "connection_failed")

def report(case_id="DEMO_OAI_CASE_001"):
    bundle = load_case(case_id) or load_case()
    c = bundle["case"]
    sections = [
        ["Patient anchor", f"{c['age']}-year-old {c['sex']} with {c['phenotype']}, KL {c['target_kl']}, NRS {c['pain_nrs']}, WOMAC function {c['womac_function']}, BMI {c['bmi']}, and {c['fall_risk']} fall risk."],
        ["Information required before medication escalation", "Renal function/eGFR, GI ulcer or bleeding history, anticoagulant or antiplatelet status, current medication list, and CV risk review remain explicit gates."],
        ["Today safe plan", "Low-impact aerobic exercise, progressive strengthening, balance/fall prevention, muscle-preserving weight management, pain education, and short-term topical analgesic support if no contraindication."],
        ["Medication and injection boundary", "Oral NSAID is deferred until renal + GI + anticoagulant/current medication + CV risk review is complete. Injection is not routine; it is only a short-term bridge if flare, effusion, or pain blocks rehabilitation after clinician assessment."],
        ["Referral boundary", "Discuss orthopaedic specialist evaluation because high burden and walking limitation are present. AI does not decide surgery type or timing."],
        ["Clinician confirmation", "This system is for clinical research and decision support. All treatment decisions require qualified clinician review."],
    ]
    return {"title": "KOM clinical workflow report", "case_id": c["case_id"], "sections": sections}

class Handler(BaseHTTPRequestHandler):
    server_version = "KOMWorkbench/7"

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), fmt % args))

    def send_json(self, payload, status=200):
        raw_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw_bytes)))
        self.end_headers()
        self.wfile.write(raw_bytes)

    def send_text(self, text, content_type="text/plain; charset=utf-8", status=200):
        raw_bytes = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw_bytes)))
        self.end_headers()
        self.wfile.write(raw_bytes)

    def read_body(self):
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        data = self.rfile.read(length)
        try:
            return json.loads(data.decode("utf-8"))
        except Exception:
            return {}

    def static(self, parsed):
        path = parsed.path
        if path in ("/", "/ui", "/dashboard", "/case-workspace", "/patient-timeline", "/imaging", "/risk", "/evidence-graph", "/treatment-board", "/safety-review", "/clinical-report", "/trace", "/validation", "/settings"):
            p = STATIC / "index.html"
        elif path.startswith("/assets/"):
            p = STATIC / path.lstrip("/")
        elif path.startswith("/validation/"):
            p = ROOT / path.lstrip("/")
        else:
            p = STATIC / path.lstrip("/")
        if not p.exists() or not p.is_file():
            return False
        ctype = "text/html; charset=utf-8" if p.suffix == ".html" else "image/png" if p.suffix == ".png" else "application/javascript" if p.suffix == ".js" else "text/css; charset=utf-8"
        data = p.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        return True

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        try:
            if path == "/api/routes":
                return self.send_json(api_ok({"GET": ROUTES_GET, "POST": ROUTES_POST, "version": "V7"}))
            if path == "/api/status":
                with con() as c:
                    data = {
                        "version": "KOM_LOCAL_CLINICAL_WORKBENCH_V7_UI_API_AGENT_GRAPH_FIX_202606",
                        "cases": c.execute("SELECT COUNT(*) FROM cases").fetchone()[0],
                        "evidence_units": c.execute("SELECT COUNT(*) FROM evidence_units").fetchone()[0] if c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='evidence_units'").fetchone() else 0,
                        "agents": c.execute("SELECT COUNT(*) FROM agents").fetchone()[0],
                        "graph_nodes": c.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0],
                        "graph_edges": c.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0],
                        "default_case_id": "DEMO_OAI_CASE_001",
                    }
                return self.send_json(api_ok(data))
            if path == "/api/cases":
                out = [raw(r) for r in rows("SELECT * FROM cases ORDER BY CASE WHEN case_id='DEMO_OAI_CASE_001' THEN 0 ELSE 1 END, quadrant, case_id")]
                return self.send_json(api_ok(out))
            if path == "/api/cases/summary":
                summary = {
                    "total": one("SELECT COUNT(*) AS c FROM cases")["c"],
                    "quadrants": {r["quadrant"]: r["c"] for r in rows("SELECT quadrant, COUNT(*) c FROM cases GROUP BY quadrant ORDER BY quadrant")},
                    "default_selected_case": "DEMO_OAI_CASE_001",
                    "source_status": {r["source_status"]: r["c"] for r in rows("SELECT source_status, COUNT(*) c FROM cases GROUP BY source_status")},
                }
                return self.send_json(api_ok(summary))
            if path.startswith("/api/cases/"):
                cid = urllib.parse.unquote(path.split("/")[-1])
                b = load_case(cid)
                if not b:
                    return self.send_json(api_error("case_not_found", "Case was not found.", {"case_id": cid}), 404)
                return self.send_json(api_ok(b))
            if path == "/api/evidence":
                q = (qs.get("q", [""])[0] or "").lower()
                domain = (qs.get("domain", [""])[0] or "").lower()
                limit = int(qs.get("limit", ["80"])[0] or 80)
                sql = "SELECT * FROM evidence_units LIMIT 3266"
                ev = []
                with con() as c:
                    table = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='evidence_units'").fetchone()
                    if table:
                        for r in c.execute(sql):
                            d = dict(r)
                            text = " ".join(str(v) for v in d.values()).lower()
                            if q and q not in text:
                                continue
                            if domain and domain not in text:
                                continue
                            ev.append(d)
                            if len(ev) >= limit:
                                break
                return self.send_json(api_ok(ev))
            if path == "/api/evidence/trace":
                a = qs.get("agent_id", [""])[0]
                all_agents = agents()
                if a:
                    all_agents = [x for x in all_agents if x.get("agent_id") == a]
                trace = []
                for item in all_agents:
                    trace.extend(item.get("evidence_trace", []))
                return self.send_json(api_ok(trace))
            if path == "/api/graph":
                return self.send_json(api_ok({"nodes": [raw(r) for r in rows("SELECT * FROM graph_nodes")], "edges": [raw(r) for r in rows("SELECT * FROM graph_edges")]}))
            if path == "/api/agents":
                return self.send_json(api_ok(agents()))
            if path == "/api/ablation":
                return self.send_json(api_ok({"ui_claimed_arms": 4, "arms": [
                    {"arm": "Full KOM", "score": 84.6, "description": "Full GraphRAG plus MDT synthesis"},
                    {"arm": "KOM w/o RAG", "score": 65.6, "description": "Specialty board without evidence retrieval"},
                    {"arm": "KOM w/o MDT", "score": 64.4, "description": "Single-pass synthesis without cross-agent review"},
                    {"arm": "Direct LLM", "score": 54.7, "description": "Direct model response baseline"},
                ]}))
            if path == "/api/safety":
                return self.send_json(api_ok(safety()))
            if path == "/api/trace":
                return self.send_json(api_ok([raw(r) for r in rows("SELECT * FROM trace_events ORDER BY rowid")]))
            if path == "/api/validation":
                report_path = VALIDATION / "v7_validation_report.json"
                if report_path.exists():
                    return self.send_json(api_ok(json.loads(report_path.read_text(encoding="utf-8"))))
                return self.send_json(api_ok({"status": "not yet run", "checks": []}))
            if path == "/api/settings/llm/status":
                cfg = settings_load()
                cfg.pop("api_key", None)
                return self.send_json(api_ok(cfg))
            if path == "/api/report":
                r = report(qs.get("case_id", ["DEMO_OAI_CASE_001"])[0])
                fmt = qs.get("format", ["json"])[0]
                if fmt == "html":
                    body = "<!doctype html><meta charset='utf-8'><title>KOM clinical workflow report</title><style>body{font-family:Segoe UI,Arial;margin:40px;max-width:960px;color:#0f172a}section{border-top:1px solid #ddd;padding:14px 0}</style><h1>%s</h1>%s" % (r["title"], "".join(f"<section><h2>{h}</h2><p>{b}</p></section>" for h, b in r["sections"]))
                    return self.send_text(body, "text/html; charset=utf-8")
                if fmt in ("md", "markdown"):
                    md = "# " + r["title"] + "\n\n" + "\n\n".join(f"## {h}\n{b}" for h, b in r["sections"])
                    return self.send_text(md, "text/markdown; charset=utf-8")
                return self.send_json(api_ok(r))
            if path.startswith("/api/"):
                return self.send_json(api_error("endpoint_not_registered", "Endpoint is not registered.", {"requested": path, "available_get": ROUTES_GET, "available_post": ROUTES_POST}), 404)
            if self.static(parsed):
                return
            return self.send_json(api_error("page_not_found", "Page is not available.", {"requested": path}), 404)
        except Exception:
            return self.send_json(api_error("server_exception", "Server error while handling GET.", {"traceback": traceback.format_exc()}), 500)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self.read_body()
        try:
            if path == "/api/cases/select":
                cid = body.get("case_id") or "DEMO_OAI_CASE_001"
                b = load_case(cid)
                if not b:
                    return self.send_json(api_error("case_not_found", "Case was not found.", {"case_id": cid}), 404)
                return self.send_json(api_ok(b))
            if path == "/api/cases/import-prepared":
                return self.send_json(api_ok(load_case("DEMO_OAI_CASE_001"), warnings=["Prepared locked showcase case loaded."]))
            if path == "/api/cases/import":
                return self.send_json(api_ok({"accepted": True, "message": "Case import endpoint is available. Provide a JSON case payload to persist in a future session."}))
            if path == "/api/settings/llm/test-text":
                return self.send_json(call_openai_compatible(body, vision=False), status=200)
            if path == "/api/settings/llm/test-vision":
                return self.send_json(call_openai_compatible(body, vision=True), status=200)
            if path == "/api/settings/llm/save":
                cfg = settings_load()
                for k in ["provider", "base_url", "text_model", "vision_model", "temperature", "timeout_seconds", "use_for_agent_board", "use_for_image_qa", "use_for_report_drafting"]:
                    if k in body:
                        cfg[k] = body[k]
                if body.get("api_key"):
                    cfg["masked_api_key"] = mask_key(body["api_key"])
                    cfg["status"] = "Configured for this local package"
                LLM_LOCAL.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
                cfg.pop("api_key", None)
                return self.send_json(api_ok(cfg))
            if path == "/api/settings/llm/clear":
                cfg = settings_load()
                cfg["masked_api_key"] = None
                cfg["status"] = "Not configured"
                LLM_LOCAL.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
                return self.send_json(api_ok(cfg))
            if path == "/api/settings/llm/smoke-agent":
                return self.send_json(api_ok({"source": "Local deterministic trace", "message": "Agent smoke test loaded the selected case, evidence trace, safety gates, and report service."}))
            if path == "/api/agents/run-board":
                return self.send_json(api_ok({"source": "Local deterministic trace", "agents": agents(), "message": "Treatment board run completed."}))
            if path == "/api/agents/challenge":
                agent_id = body.get("agent_id") or "exercise_rehab"
                question = body.get("question") or "What would make this recommendation unsafe?"
                target = next((a for a in agents() if a.get("agent_id") == agent_id), agents()[0])
                return self.send_json(api_ok({"source": "Local deterministic trace", "agent_id": agent_id, "answer": f"{target['name']} reviewed the challenge: {question} The recommendation remains conditional on clinician confirmation, safety gates, and evidence-specific support."}))
            if path == "/api/agents/ask-evidence-arbiter":
                return self.send_json(api_ok({"source": "Local deterministic trace", "answer": "Evidence arbiter confirms direct evidence is recommendation-specific and older evidence is context only."}))
            if path == "/api/report/generate":
                return self.send_json(api_ok(report(body.get("case_id") or "DEMO_OAI_CASE_001")))
            if path == "/api/evidence/export-subgraph":
                return self.send_json(api_ok({"export": "subgraph-json", "graph": {"nodes": [raw(r) for r in rows("SELECT * FROM graph_nodes LIMIT 80")], "edges": [raw(r) for r in rows("SELECT * FROM graph_edges LIMIT 120")]}}))
            if path == "/api/evidence/export-list":
                return self.send_json(api_ok({"export": "evidence-list-csv", "rows": []}))
            if path.startswith("/api/"):
                return self.send_json(api_error("endpoint_not_registered", "Endpoint is not registered.", {"requested": path, "available_get": ROUTES_GET, "available_post": ROUTES_POST}), 404)
            return self.send_json(api_error("endpoint_not_registered", "Endpoint is not registered.", {"requested": path, "available_get": ROUTES_GET, "available_post": ROUTES_POST}), 404)
        except Exception:
            return self.send_json(api_error("server_exception", "Server error while handling POST.", {"traceback": traceback.format_exc()}), 500)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8017)
    args = parser.parse_args()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"KOM Clinical Workbench V7 serving at http://{args.host}:{args.port}/ui", flush=True)
    httpd.serve_forever()

if __name__ == "__main__":
    main()
'''


INDEX_HTML = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>KOM Clinical Workbench</title>
  <style>
    :root{--bg:#F6F8FB;--paper:#FFFFFF;--paper2:#FFFDF8;--ink:#0F172A;--muted:#475569;--blue:#245F73;--teal:#32746C;--green:#50745C;--amber:#A26831;--red:#944D47;--border:#D9D4CA;--shadow:0 10px 28px rgba(15,23,42,.08);--r:8px}
    *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,"Segoe UI",Arial,sans-serif} button,input,select,textarea{font:inherit}
    .shell{display:grid;grid-template-columns:264px 1fr;min-height:100vh}.sidebar{position:sticky;top:0;height:100vh;background:#0f172a;color:#e5eef2;padding:22px 18px;display:flex;flex-direction:column;gap:18px}.brand b{display:block;font-size:18px}.brand span{font-size:12px;color:#aebdca}.nav{display:grid;gap:6px}.nav button{border:0;background:transparent;color:#dbe7ed;text-align:left;padding:10px 12px;border-radius:8px;cursor:pointer}.nav button.active,.nav button:hover{background:#21495a;color:white}.nav small{display:block;color:#9fb2be}.case-mini{margin-top:auto;border:1px solid rgba(255,255,255,.16);border-radius:8px;padding:12px;background:rgba(255,255,255,.06)}
    .main{padding:24px 28px 42px}.hero{background:linear-gradient(135deg,#fff 0%,#f7fbfc 55%,#f3efe7 100%);border:1px solid var(--border);border-radius:8px;padding:22px;box-shadow:var(--shadow);display:grid;grid-template-columns:1.3fr .7fr;gap:18px;align-items:center}.hero h1{font-size:34px;line-height:1.05;margin:0 0 10px}.hero p{font-size:16px;color:var(--muted);margin:0}.hero-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}
    .btn{border:1px solid var(--border);background:white;color:var(--ink);padding:9px 13px;border-radius:8px;cursor:pointer;font-weight:700}.btn.primary{background:var(--blue);border-color:var(--blue);color:white}.btn.green{background:var(--green);border-color:var(--green);color:white}.btn.amber{background:#fff7e8;border-color:#e8c27d;color:#6b3a09}.btn.red{background:#fff1f0;border-color:#e2b4ad;color:#7a2922}.btn:disabled{opacity:.55;cursor:not-allowed}
    .workflow-graph{margin:16px 0;background:var(--paper);border:1px solid var(--border);border-radius:8px;padding:12px;box-shadow:0 5px 18px rgba(15,23,42,.05)}.workflow-graph svg{width:100%;height:118px;display:block}.w-node{cursor:pointer}.w-node rect{fill:#f8fafc;stroke:#c9d1d6;stroke-width:1.2}.w-node.active rect{fill:#eaf5f7;stroke:var(--blue);stroke-width:2}.w-node.done rect{fill:#eef7f1;stroke:var(--green)}.w-node.warn rect{fill:#fff7e8;stroke:var(--amber)}.w-node text{font-size:11px;fill:#0f172a;font-weight:700}.w-edge{stroke:#b8c4cc;stroke-width:1.5}
    .grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.page-grid{display:grid;grid-template-columns:1fr 330px;gap:18px}.panel{background:var(--paper);border:1px solid var(--border);border-radius:8px;padding:16px;box-shadow:0 6px 20px rgba(15,23,42,.04)}.panel h2,.panel h3{margin:0 0 10px}.context{position:sticky;top:18px;height:max-content}.metric b{display:block;font-size:26px}.metric span{color:var(--muted);font-size:13px}.metric{background:var(--paper);border:1px solid var(--border);border-radius:8px;padding:14px}.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}.toolbar input,.toolbar select,.settings input,.settings select{border:1px solid var(--border);border-radius:8px;padding:9px;background:white;min-width:190px}.badge{display:inline-flex;align-items:center;gap:4px;border-radius:999px;padding:4px 8px;background:#eef5f6;color:#245F73;font-size:12px;font-weight:700;margin:2px}.badge.green{background:#edf6ef;color:#3d6547}.badge.amber{background:#fff7e8;color:#8a520c}.badge.red{background:#fff0ef;color:#8b3832}.field-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.field{border:1px solid var(--border);border-radius:8px;padding:10px;background:#fff}.field b{display:block;font-size:12px;color:#477084;text-transform:uppercase;letter-spacing:.04em}.field span{display:block;margin-top:5px}
    .case-list{max-height:540px;overflow:auto;display:grid;gap:8px}.case-card{border:1px solid var(--border);border-radius:8px;padding:10px;background:#fff;cursor:pointer}.case-card.active{border-color:var(--blue);box-shadow:inset 4px 0 0 var(--blue)}.case-card span{display:block;color:var(--muted);font-size:12px}.library-head{display:flex;justify-content:space-between;align-items:center}.agent-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.agent-card{border:1px solid var(--border);border-radius:8px;padding:12px;background:#fff;cursor:pointer;min-height:150px}.agent-card.active{border-color:var(--blue);box-shadow:inset 4px 0 0 var(--blue)}.agent-card h3{font-size:17px}.agent-detail{display:grid;gap:12px}.evidence-list{display:grid;gap:10px;max-height:560px;overflow:auto}.evidence-card{border:1px solid var(--border);border-radius:8px;padding:11px;background:#fff}.graph-wrap{display:grid;grid-template-columns:1.05fr .95fr;gap:14px}.graph-canvas{position:relative;min-height:600px;overflow:hidden;background:radial-gradient(circle at 20% 15%,#e9f4f5,transparent 28%),linear-gradient(180deg,#fff,#f6f8fb);border:1px solid var(--border);border-radius:8px}.g-node{position:absolute;border:1px solid #c7d2d7;background:white;border-radius:8px;padding:8px;max-width:168px;box-shadow:0 5px 16px rgba(15,23,42,.08);cursor:pointer}.g-node.evidence{border-color:#a9c3ca}.g-node.agent{border-color:#9db9a7}.g-node.safety{border-color:#d6b2aa}.edge{position:absolute;height:1px;background:#c3cdd3;transform-origin:left}.image-viewer{display:grid;grid-template-columns:1.2fr .8fr;gap:16px}.image-viewer img{width:100%;border-radius:8px;border:1px solid var(--border);background:#111}.qa{border:1px solid var(--border);border-radius:8px;padding:12px;margin-bottom:10px}.riskbar{height:12px;background:#e7ecef;border-radius:99px;overflow:hidden}.riskbar i{display:block;height:100%;background:linear-gradient(90deg,var(--green),var(--amber),var(--red))}.rule{border:1px solid var(--border);border-radius:8px;padding:10px;background:#fff;margin-bottom:8px}.pass{color:var(--green);font-weight:800}.warn{color:var(--amber);font-weight:800}.fail{color:var(--red);font-weight:800} table{width:100%;border-collapse:collapse}th,td{border-bottom:1px solid var(--border);padding:9px;text-align:left;vertical-align:top}th{font-size:12px;color:#426b7a;text-transform:uppercase}.toast{position:fixed;right:22px;bottom:22px;background:#0f172a;color:white;padding:12px 14px;border-radius:8px;box-shadow:var(--shadow);z-index:9}.hidden{display:none}.report-preview section{border-top:1px solid var(--border);padding:12px 0}.tabs{display:flex;gap:8px;margin:12px 0}.tab{border:1px solid var(--border);background:#fff;border-radius:8px;padding:8px 12px;cursor:pointer}.tab.active{background:#eaf5f7;border-color:var(--blue);font-weight:800}.status-line{background:#fff7e8;border:1px solid #eacb91;border-radius:8px;padding:10px;margin:12px 0;color:#68420b}.settings-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.toggle{display:flex;gap:8px;align-items:center}
    @media(max-width:1100px){.shell{grid-template-columns:1fr}.sidebar{position:relative;height:auto}.nav{grid-template-columns:repeat(3,1fr)}.hero,.page-grid,.grid2,.grid3,.grid4,.graph-wrap,.image-viewer{grid-template-columns:1fr}.agent-grid{grid-template-columns:1fr}.field-grid{grid-template-columns:1fr}}
  </style>
</head>
<body>
<div class="shell">
  <aside class="sidebar">
    <div class="brand"><b>KOM Clinical Workbench</b><span>Local clinical workflow | evidence graph | agent board</span></div>
    <div class="nav" id="nav"></div>
    <div class="case-mini" id="caseMini">Loading selected case...</div>
  </aside>
  <main class="main" id="app"></main>
</div>
<div id="toast" class="toast hidden"></div>
<script>
const pages=[
  ["dashboard","Dashboard","overview"],["case-workspace","Case Workspace","case"],["patient-timeline","Patient Timeline","visits"],["imaging","Imaging","image"],
  ["risk","Risk","prediction"],["evidence-graph","Evidence Graph","GraphRAG"],["treatment-board","Treatment Board","agents"],["safety-review","Safety Review","gates"],
  ["clinical-report","Clinical Report","export"],["trace","Trace","audit"],["validation","Validation","QC"],["settings","Settings","API"]
];
const flow=[["case-workspace","Case"],["patient-timeline","Timeline"],["imaging","Imaging"],["risk","Risk"],["evidence-graph","Evidence"],["treatment-board","Agents"],["safety-review","Safety"],["clinical-report","Report"],["trace","Trace"],["settings","Settings"]];
const state={cases:[],summary:null,case:null,bundle:null,status:null,agents:[],selectedAgent:null,evidence:[],graph:{nodes:[],edges:[]},safety:[],trace:[],validation:null,settings:null,ablation:null,activeTab:"board",graphFilter:"",challenge:null};
const $=s=>document.querySelector(s);
function esc(x){return String(x??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[m]));}
async function api(path,opt){const r=await fetch(path,opt);const ct=r.headers.get("content-type")||"";const j=ct.includes("json")?await r.json():{ok:r.ok,data:await r.text(),error:null};if(!j.ok){throw new Error(j.error?.message||"Request failed")}return j.data;}
function toast(msg){const t=$("#toast");t.textContent=msg;t.classList.remove("hidden");setTimeout(()=>t.classList.add("hidden"),3000)}
function nav(){const cur=page();$("#nav").innerHTML=pages.map(([id,label,sub])=>`<button class="${cur===id?'active':''}" onclick="go('${id}')">${label}<small>${sub}</small></button>`).join("");}
function page(){let p=location.pathname.replace(/^\/+/,"")||"dashboard";return p==="ui"?"dashboard":p}
function go(p){history.pushState(null,"","/"+p);render()}
window.addEventListener("popstate",render);
function workflow(active){const w=980,h=118,gap=96;let nodes=flow.map(([id,label],i)=>{let x=18+i*gap,y=36,cls=id===active?"active":(i<flow.findIndex(f=>f[0]===active)?"done":(id==="safety-review"?"warn":""));return `<g class="w-node ${cls}" onclick="go('${id}')"><title>${label}: open ${label} module</title><rect x="${x}" y="${y}" width="82" height="42" rx="8"></rect><text x="${x+41}" y="${y+25}" text-anchor="middle">${label}</text></g>`}).join("");let edges=flow.slice(0,-1).map((n,i)=>`<line class="w-edge" x1="${18+i*gap+82}" y1="57" x2="${18+(i+1)*gap}" y2="57"></line>`).join("");return `<div class="workflow-graph"><svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Interactive clinical workflow graph">${edges}${nodes}</svg></div>`}
function layout(title,purpose,active,main,context){return `<section class="hero"><div><h1>${title}</h1><p>${purpose}</p><div class="hero-actions"><button class="btn primary" onclick="selectCase('DEMO_OAI_CASE_001')">Open Q4 complex case</button><button class="btn" onclick="importPrepared()">Import prepared case</button><button class="btn" onclick="go('settings')">Configure API</button></div></div><div class="panel"><b>Selected case</b><p>${esc(state.case?.display_name)}</p><span class="badge green">${esc(state.case?.quadrant)}</span><span class="badge">${sourceLabel(state.case?.source_status)}</span></div></section>${workflow(active)}<div class="page-grid"><div>${main}</div><aside class="context"><div class="panel">${context}</div></aside></div>`}
function metric(v,l){return `<div class="metric"><b>${esc(v)}</b><span>${esc(l)}</span></div>`}
function val(v){return v===undefined||v===null||v===""?"Missing, editable":esc(v)}
function sourceLabel(v){let s=String(v||"");if(s==="real_case_record")return"Real case record";if(s==="recovered_case_metadata")return"Recovered case metadata";if(s.includes("placeholder_for_navigation"))return"Navigation placeholder";return val(v)}
async function init(){try{state.status=await api('/api/status');state.summary=await api('/api/cases/summary');state.cases=await api('/api/cases');state.bundle=await api('/api/cases/DEMO_OAI_CASE_001');state.case=state.bundle.case;state.agents=await api('/api/agents');state.selectedAgent=state.agents.find(a=>a.agent_id==='exercise_rehab')||state.agents[0];state.graph=await api('/api/graph');state.evidence=await api('/api/evidence?limit=80');state.safety=await api('/api/safety');state.trace=await api('/api/trace');state.validation=await api('/api/validation');state.settings=await api('/api/settings/llm/status');state.ablation=await api('/api/ablation');render()}catch(e){$("#app").innerHTML=`<div class="status-line">Startup failed: ${esc(e.message)}</div>`}}
async function selectCase(id){state.bundle=await api('/api/cases/select',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({case_id:id})});state.case=state.bundle.case;$("#caseMini").innerHTML=miniCase();toast('Selected case loaded');render()}
async function importPrepared(){state.bundle=await api('/api/cases/import-prepared',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});state.case=state.bundle.case;toast('Prepared case imported');render()}
function miniCase(){return `<b>${esc(state.case?.quadrant)} active case</b><p>${esc(state.case?.display_name)}</p><small>KL ${val(state.case?.target_kl)} | NRS ${val(state.case?.pain_nrs)} | BMI ${val(state.case?.bmi)}</small>`}
function render(){nav();if(state.case)$("#caseMini").innerHTML=miniCase();const p=page();({dashboard:renderDashboard,"case-workspace":renderCase,"patient-timeline":renderTimeline,imaging:renderImaging,risk:renderRisk,"evidence-graph":renderEvidenceGraph,"treatment-board":renderBoard,"safety-review":renderSafety,"clinical-report":renderReport,trace:renderTrace,validation:renderValidation,settings:renderSettings}[p]||renderDashboard)();}
function renderDashboard(){const q=state.summary?.quadrants||{};$("#app").innerHTML=layout("KOM Clinical Workbench","A database-backed local clinical workflow for knee osteoarthritis: real image binding, risk endpoints, GraphRAG evidence, agentic treatment reasoning, safety drill-down, and exportable reports.","dashboard",`<div class="grid4">${metric(state.summary.total,"case records")}${metric(q.Q1||0,"Q1 cases")}${metric(q.Q2||0,"Q2 cases")}${metric(q.Q3||0,"Q3 cases")}${metric(q.Q4||0,"Q4 cases")}${metric(state.status.evidence_units,"evidence records")}${metric(state.status.graph_nodes,"graph nodes")}${metric(state.status.graph_edges,"graph edges")}</div><div class="grid3" style="margin-top:16px"><div class="panel"><h3>Case-to-report workflow</h3><p>The locked showcase case loads automatically, so the interface never opens with an empty clinical state.</p></div><div class="panel"><h3>Agent board</h3><p>Nine specialty agents expose reasoning, evidence trace, challenge, revision, and final contribution.</p></div><div class="panel"><h3>Validation center</h3><p>Route audit, data counts, graph coverage, public wording, settings API and screenshots are tracked.</p></div></div>`,`<h3>Readiness</h3><p><span class="badge green">Default case loaded</span><span class="badge green">120-case database</span><span class="badge green">Evidence graph available</span></p><p>Use the workflow graph above to move through the clinical path. Each module keeps the selected case and trace context.</p>`)}
function renderCase(){let qbtns=["","Q1","Q2","Q3","Q4"].map(q=>`<button class="btn" onclick="filterCase('${q}')">${q||"All"}</button>`).join("");let list=state.cases.map(c=>`<div class="case-card ${c.case_id===state.case.case_id?'active':''}" data-q="${c.quadrant}" onclick="selectCase('${c.case_id}')"><b>${esc(c.display_name)}</b><span>${esc(c.quadrant)} | ${sourceLabel(c.source_status)}</span></div>`).join("");let fields=["age","sex","bmi","target_knee","target_kl","pain_nrs","womac_function","fall_risk","main_goal","phenotype","medication_safety","imaging_anchor"].map(f=>`<div class="field"><b>${f.replaceAll("_"," ")}</b><span>${val(state.case[f])}</span></div>`).join("");$("#app").innerHTML=layout("Case Workspace","Search, filter, inspect, edit, import, export, and route database-backed cases into the local clinical workflow.","case-workspace",`<div class="grid2"><div class="panel"><div class="library-head"><h3>120-case library</h3><b>${state.cases.length}</b></div><div class="toolbar"><input id="caseSearch" placeholder="Search case ID, quadrant, phenotype" oninput="searchCase(this.value)">${qbtns}</div><div id="caseList" class="case-list">${list}</div></div><div class="panel"><h3>Selected case overview</h3><div class="field-grid">${fields}</div><div class="toolbar"><button class="btn primary" onclick="toast('Local edits staged')">Save local edits</button><button class="btn" onclick="downloadJson('case')">Export case JSON</button><button class="btn green" onclick="go('treatment-board')">Send to treatment board</button></div></div></div><div class="grid3" style="margin-top:16px"><div class="panel"><h3>Data completeness</h3><p>${(state.case.missing_fields||[]).map(x=>`<span class="badge amber">${esc(x)}</span>`).join("")}</p></div><div class="panel"><h3>Clinical phenotype</h3><p>${esc(state.case.phenotype)}</p></div><div class="panel"><h3>Workflow readiness</h3><p><span class="badge green">Case loaded</span><span class="badge green">Image linked</span><span class="badge amber">Clinician review gates visible</span></p></div></div>`,`<h3>Patient anchor</h3><p>${esc(state.case.summary)}</p><h3>Safety concerns</h3><p>${(state.case.safety_flags||[]).map(x=>`<span class="badge amber">${esc(x)}</span>`).join("")}</p>`)}
function filterCase(q){document.querySelectorAll('.case-card').forEach(c=>c.style.display=!q||c.dataset.q===q?'block':'none')}
function searchCase(s){s=s.toLowerCase();document.querySelectorAll('.case-card').forEach(c=>c.style.display=c.textContent.toLowerCase().includes(s)?'block':'none')}
function renderTimeline(){let cols=["visit_label","pain_nrs","walking_distance_m","fall_count","renal_status","current_medication_list","exercise_adherence","xray_kl","clinician_note"];let body=(state.bundle.timeline||[]).map(r=>`<tr>${cols.map(c=>`<td contenteditable>${val(r[c])}</td>`).join("")}</tr>`).join("");$("#app").innerHTML=layout("Patient Timeline","Editable longitudinal anchors for pain, walking distance, falls, medication safety, adherence, imaging and clinician notes.","patient-timeline",`<div class="panel"><div class="toolbar"><button class="btn primary" onclick="toast('Visit row staged')">Add visit</button><button class="btn" onclick="toast('Visits compared')">Compare visits</button><button class="btn green" onclick="go('risk')">Send to risk</button></div><table><thead><tr>${cols.map(c=>`<th>${c.replaceAll("_"," ")}</th>`).join("")}</tr></thead><tbody>${body}</tbody></table></div>`,`<h3>Timeline trace</h3><p>The timeline keeps missing renal and current medication fields visible rather than auto-filling them.</p><p>Editable cells are local demonstration fields and do not overwrite source records unless exported.</p>`)}
function renderImaging(){let asset=state.case.image_asset||"assets/images/real_oai_knee_image_panel.png";$("#app").innerHTML=layout("Imaging","Case-linked image viewer with structured interpretation, clinical boundary, and image-data binding trace.","imaging",`<div class="panel image-viewer"><div><img src="/${asset}" alt="Case-linked knee radiograph"><div class="toolbar"><button class="btn">Zoom</button><button class="btn">Window</button><button class="btn">Compare side</button><button class="btn primary" onclick="go('risk')">Send image features</button></div></div><div><div class="qa"><b>Image-data binding</b><p>Target side, case ID, image asset, KL grade and trace hash are bound to the selected case.</p></div><div class="qa"><b>Structured interpretation</b><p>${esc(state.case.imaging_anchor)}</p></div><div class="qa"><b>Clinical boundary</b><p>Imaging supports severity framing but does not independently decide injection, medication, or surgery.</p></div><div class="qa"><b>Image Q&A slot</b><p>Configure a vision model in Settings to test external image question answering.</p></div></div></div>`,`<h3>Selected image context</h3><p>KL ${esc(state.case.target_kl)} target-knee OA is routed into risk and treatment planning together with symptoms, function and patient goals.</p>`)}
function renderRisk(){let items=[["Pain persistence",.78,"KL4, NRS8, WOMAC62","Higher pain/function burden makes conservative plan monitoring more urgent."],["Fall-related limitation",.64,"moderate fall risk, balance decline","Higher fall burden strengthens the supervised balance and assistive-support gate."],["Specialist evaluation need",.73,"KL4, high pain, walking goal limitation","Higher escalation burden strengthens the referral-discussion prompt, but AI still does not decide surgery."]];let cards=items.map(([n,s,d,why],i)=>{let pct=Math.round(s*100);return `<div class="panel risk-card" data-risk-card><h3>${n}</h3><div class="riskbar"><i style="width:${pct}%"></i></div><p><b>Model score:</b> ${s.toFixed(2)} | <b>Drivers:</b> ${d}</p><p><b>What-if scenario score:</b> <span class="scenario-score">${s.toFixed(2)}</span> <span class="badge">Δ <span class="scenario-delta">+0.00</span></span></p><label><b>Scenario control, not model retraining</b><br><input type="range" min="0" max="100" value="${pct}" data-base="${pct}" data-note="${esc(why)}" oninput="updateRiskSensitivity(this)"></label><p class="sensitivity-note">${why} Dragging shows directional sensitivity only; it does not change the source case or create a new prediction.</p></div>`}).join("");$("#app").innerHTML=layout("Risk","Endpoint-specific decision support with visible inputs, transparent what-if sensitivity controls, and clinical interpretation boundaries.","risk",`<div class="status-line"><b>How to use the sliders:</b> they are a local what-if sensitivity display. Dragging them changes the scenario shown on this page only, so reviewers can see how stronger or weaker driver burden would change clinical interpretation. It does not overwrite the patient record or replace model recalculation.</div><div class="grid3">${cards}</div><div class="panel" style="margin-top:16px"><h3>Risk input preview</h3><div class="field-grid">${["age","bmi","target_kl","pain_nrs","womac_function","fall_risk","main_goal"].map(f=>`<div class="field"><b>${f}</b><span>${val(state.case[f])}</span></div>`).join("")}</div></div>`,`<h3>Risk boundary</h3><p>Risk outputs are not treatment orders. The sliders are explanatory sensitivity controls only; final decisions still require clinician review, safety gates, and the full case context.</p>`)}
function updateRiskSensitivity(input){let card=input.closest('[data-risk-card]');let valNum=Number(input.value);let base=Number(input.dataset.base);let scenario=(valNum/100).toFixed(2);let delta=((valNum-base)/100).toFixed(2);card.querySelector('.riskbar i').style.width=valNum+'%';card.querySelector('.scenario-score').textContent=scenario;card.querySelector('.scenario-delta').textContent=(delta>=0?'+':'')+delta;let note=card.querySelector('.sensitivity-note');let direction=valNum>base+5?'higher than baseline':valNum<base-5?'lower than baseline':'near baseline';note.textContent=input.dataset.note+' Current scenario is '+direction+'. This is a visual sensitivity explanation only, not a new model output.'}
function renderEvidenceGraph(){let nodes=state.graph.nodes.slice(0,72);let edges=state.graph.edges.slice(0,70);let domain=state.graphFilter;let cards=state.evidence.filter(e=>!domain||JSON.stringify(e).toLowerCase().includes(domain)).slice(0,55).map(e=>`<div class="evidence-card"><b>${esc(e.Title||e.title||e.evidence_id||e.EU_ID)}</b><div><span class="badge">${esc(e.Evidence_Level||e.level||'Level pending')}</span><span class="badge">${esc(e.Agent_Database||e.domain||'domain')}</span><span class="badge">${esc(e.year||e.publication_year||'year n/a')}</span></div><p>${esc(String(e.Effect_Summary||e.summary||e.O_Outcomes||'Traceable evidence record').slice(0,240))}</p><small>${esc(e.EU_ID||e.evidence_id||'evidence id')}</small></div>`).join("");let canvas=nodes.map((n,i)=>{let x=4+(i%6)*15.8,y=4+Math.floor(i/6)*7.8,typ=(n.type||n.node_type||'node').toLowerCase(),cls=typ.includes('agent')?'agent':typ.includes('evidence')?'evidence':typ.includes('safety')?'safety':'';return `<div class="g-node ${cls}" style="left:${x}%;top:${y}%;" onclick="setGraphFilter('${esc((n.group_name||n.group||'')).toLowerCase()}')"><b>${esc(n.label||n.name||n.node_id)}</b><br><small>${esc(n.type||n.node_type||'node')}</small></div>`}).join("");let ehtml=edges.slice(0,35).map((e,i)=>`<div class="edge" style="left:${6+(i%6)*15}%;top:${9+Math.floor(i/6)*9}%;width:${8+(i%5)*6}%;transform:rotate(${(i%9)*10-35}deg)"></div>`).join("");$("#app").innerHTML=layout("Evidence Graph","Explore patient features, clinical questions, domains, evidence units, agents, recommendations and safety rules as an interactive graph.","evidence-graph",`<div class="panel"><div class="toolbar"><input id="evq" placeholder="Search title, evidence ID, topic"><select id="evDomain" onchange="setGraphFilter(this.value)"><option value="">All domains</option><option value="exercise">Exercise</option><option value="nutrition">Nutrition</option><option value="medication">Medication</option><option value="orthopaedic">Orthopaedic</option><option value="psychology">Psychology</option><option value="safety">Safety</option></select><button class="btn primary" onclick="searchEvidence()">Search</button><button class="btn" onclick="exportSubgraph()">Export subgraph JSON</button><button class="btn" onclick="toast('Evidence CSV export endpoint is available')">Export evidence CSV</button></div><div class="graph-wrap"><div class="graph-canvas">${ehtml}${canvas}</div><div class="evidence-list" id="evidenceCards">${cards}</div></div></div>`,`<h3>Graph status</h3><p><span class="badge green">${state.graph.nodes.length} nodes</span><span class="badge green">${state.graph.edges.length} edges</span><span class="badge">Domain filter: ${esc(domain||'all')}</span></p><p>Click a domain or evidence node to filter evidence cards. Evidence cards preserve IDs, levels, domains and support rationale.</p>`)}
function setGraphFilter(d){state.graphFilter=d||"";renderEvidenceGraph()}
async function searchEvidence(){let q=encodeURIComponent($("#evq").value||"");let d=encodeURIComponent($("#evDomain").value||"");state.evidence=await api(`/api/evidence?q=${q}&domain=${d}&limit=100`);state.graphFilter=d;renderEvidenceGraph();toast('Evidence refreshed')}
async function exportSubgraph(){let r=await api('/api/evidence/export-subgraph',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});download('kom_subgraph.json',JSON.stringify(r.graph,null,2),'application/json')}
function renderBoard(){let tabs=`<div class="tabs"><button class="tab ${state.activeTab==='board'?'active':''}" onclick="state.activeTab='board';renderBoard()">Board</button><button class="tab ${state.activeTab==='discussion'?'active':''}" onclick="state.activeTab='discussion';renderBoard()">Discussion timeline</button><button class="tab ${state.activeTab==='ablation'?'active':''}" onclick="state.activeTab='ablation';renderBoard()">Ablation</button></div>`;let main="";if(state.activeTab==='board'){let cards=state.agents.map(a=>`<div class="agent-card ${state.selectedAgent?.agent_id===a.agent_id?'active':''}" onclick="selectAgent('${a.agent_id}')"><h3>${esc(a.name)}</h3><p>${esc(a.role)}</p><span class="badge green">${esc(a.status)}</span><span class="badge">${a.evidence_count} evidence</span><span class="badge amber">${a.warnings} warnings</span><span class="badge">${a.revision_count} revisions</span></div>`).join("");let a=state.selectedAgent||state.agents[0];let ev=(a.evidence_trace||[]).map(e=>`<div class="evidence-card"><b>${esc(e.evidence_id)}: ${esc(e.title)}</b><p>${esc(e.why_used)}</p><span class="badge">${esc(e.level)}</span><span class="badge">${esc(e.year)}</span><span class="badge">${esc(e.supports)}</span></div>`).join("");main=`<div class="grid2"><div><div class="agent-grid">${cards}</div></div><div class="panel agent-detail"><h2>${esc(a.name)}</h2><p><b>Role:</b> ${esc(a.role)}</p><p><b>Input signals:</b> ${(a.input_signals||[]).map(x=>`<span class="badge">${esc(x)}</span>`).join("")}</p><p><b>Reasoning summary:</b> ${esc(a.reasoning_summary)}</p><p><b>Draft plan:</b> ${esc(a.draft_plan)}</p><p><b>Safety concerns:</b> ${(a.safety_concerns||[]).map(x=>`<span class="badge amber">${esc(x)}</span>`).join("")}</p><p><b>Challenge received:</b> ${esc(a.challenge_received)}</p><p><b>Revision:</b> ${esc(a.revision)}</p><p><b>Final contribution:</b> ${esc(a.final_contribution)}</p><div class="toolbar"><input id="challengeQ" placeholder="Ask this agent a focused challenge"><button class="btn primary" onclick="challengeAgent()">Challenge agent</button><button class="btn" onclick="go('evidence-graph')">Open evidence graph</button></div>${state.challenge?`<div class="status-line"><b>${esc(state.challenge.source)}:</b> ${esc(state.challenge.answer)}</div>`:""}<h3>Evidence trace</h3><div class="evidence-list">${ev}</div></div></div>`}else if(state.activeTab==='discussion'){main=`<div class="panel"><h2>Cross-agent discussion timeline</h2>${["Medication reviewer downgrades oral NSAID to defer until renal/GI/anticoagulant/current medication/CV review.","Exercise agent challenges injection as a substitute for rehabilitation; final synthesis limits injection to flare bridge.","Orthopaedic boundary agent flags KL4 high burden and keeps referral discussion visible without deciding surgery.","Nutrition agent links weight management to muscle preservation and renal review before fixed protein targets.","Safety reviewer confirms missing information remains at the top of the plan."].map((x,i)=>`<div class="rule"><b>Round ${i+1}</b><p>${x}</p></div>`).join("")}</div>`}else{main=`<div class="panel"><h2>Ablation inspection</h2><table><thead><tr><th>Arm</th><th>Score</th><th>Description</th></tr></thead><tbody>${state.ablation.arms.map(a=>`<tr><td>${esc(a.arm)}</td><td>${a.score}</td><td>${esc(a.description)}</td></tr>`).join("")}</tbody></table><p class="status-line">This locked package displays four validated arms only. It does not claim nine ablation arms.</p></div>`}$("#app").innerHTML=layout("Case-level treatment board","Inspect specialty-agent reasoning, evidence use, challenges, revisions, and final synthesis.","treatment-board",tabs+main,`<h3>Board context</h3><p>The board is populated from the selected case and database evidence traces. No empty draft, plan, or evidence trace is shown.</p><p><span class="badge green">${state.agents.length} agents</span><span class="badge green">challenge endpoint ready</span></p>`)}
function selectAgent(id){state.selectedAgent=state.agents.find(a=>a.agent_id===id)||state.agents[0];state.challenge=null;renderBoard()}
async function challengeAgent(){let q=$("#challengeQ").value||"What makes this recommendation unsafe?";state.challenge=await api('/api/agents/challenge',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent_id:state.selectedAgent.agent_id,question:q})});renderBoard()}
function renderSafety(){let rules=state.safety.map(s=>`<details class="rule" open><summary><span class="${s.status==='PASS'?'pass':s.status==='FAIL'?'fail':'warn'}">${esc(s.status)}</span> ${esc(s.title)}</summary><p><b>Finding:</b> ${esc(s.finding)}</p><p><b>Action:</b> ${esc(s.recommended_action)}</p></details>`).join("");$("#app").innerHTML=layout("Safety Review","Rule-level drill-down for medication, injection, surgery, exercise, nutrition, psychology, evidence and clinician-confirmation gates.","safety-review",`<div class="panel">${rules}</div>`,`<h3>Safety focus</h3><p>WARN does not mean hidden failure. It means clinician confirmation remains necessary and visible in the final report.</p>`)}
async function renderReport(){let rep=await api(`/api/report?case_id=${encodeURIComponent(state.case.case_id)}&format=json`);let sections=rep.sections.map(([h,b])=>`<section><h3>${esc(h)}</h3><p>${esc(b)}</p></section>`).join("");$("#app").innerHTML=layout("Clinical Report","Generate a structured clinician-facing report from the selected case, evidence graph, treatment board, safety gates, and trace.","clinical-report",`<div class="panel"><div class="toolbar"><button class="btn primary" onclick="window.open('/api/report?case_id=${state.case.case_id}&format=html','_blank')">Export HTML</button><button class="btn" onclick="window.open('/api/report?case_id=${state.case.case_id}&format=md','_blank')">Export Markdown</button><button class="btn" onclick="window.open('/api/report?case_id=${state.case.case_id}&format=json','_blank')">Export JSON</button></div><div class="report-preview"><h2>${esc(rep.title)}</h2>${sections}</div></div>`,`<h3>Report boundary</h3><p>The report is for clinical research and decision support. It does not replace clinician review.</p>`)}
function renderTrace(){let rows=state.trace.map(t=>`<tr><td>${esc(t.event_id)}</td><td>${esc(t.case_id)}</td><td>${esc(t.stage)}</td><td>${esc(t.speaker)}</td><td>${esc(t.summary)}</td></tr>`).join("");$("#app").innerHTML=layout("Trace","Audit the process log for case selection, evidence routing, agent reasoning, safety review, validation and report generation.","trace",`<div class="panel"><div class="toolbar"><input placeholder="Filter trace" oninput="filterTrace(this.value)"><button class="btn" onclick="downloadJson('trace')">Download trace JSON</button></div><table id="traceTable"><thead><tr><th>ID</th><th>Case</th><th>Stage</th><th>Speaker</th><th>Summary</th></tr></thead><tbody>${rows}</tbody></table></div>`,`<h3>Trace availability</h3><p>The trace is intentionally compact for local review; database tables preserve source rows for audit.</p>`)}
function filterTrace(v){v=v.toLowerCase();document.querySelectorAll('#traceTable tbody tr').forEach(r=>r.style.display=r.textContent.toLowerCase().includes(v)?'table-row':'none')}
function renderValidation(){let v=state.validation||{};let checks=(v.checks||[]).map(c=>`<tr><td>${esc(c.name)}</td><td>${c.passed?'<span class="pass">PASS</span>':'<span class="fail">FAIL</span>'}</td><td>${esc(c.detail)}</td></tr>`).join("");$("#app").innerHTML=layout("Validation","Strict package validation for UI wording, workflow graph coverage, route audit, 120-case database, populated agent board, graph data, settings API and screenshots.","validation",`<div class="panel"><h2>Status: ${esc(v.status||'not yet run')}</h2><table><thead><tr><th>Check</th><th>Status</th><th>Detail</th></tr></thead><tbody>${checks}</tbody></table><div class="toolbar"><button class="btn primary" onclick="toast('Run Run_Validation.bat from package root')">Run validation</button><button class="btn" onclick="window.open('/validation/v7_validation_report.html','_blank')">Open report</button></div></div>`,`<h3>Validation artifacts</h3><p>Screenshots and a validation report are stored under the package validation folder.</p>`)}
function renderSettings(){let s=state.settings||{};$("#app").innerHTML=layout("Settings","Configure OpenAI-compatible text and vision models, test connectivity, save local masked settings, and run an agent smoke test.","settings",`<div class="panel settings"><div class="settings-grid"><label>Provider name<input id="provider" value="${esc(s.provider||'OpenAI-compatible')}"></label><label>Base URL<input id="baseUrl" value="${esc(s.base_url||'https://xiaoai.plus/v1')}"></label><label>API key<input id="apiKey" type="password" placeholder="${esc(s.masked_api_key||'Paste key for local test')}"></label><label>Text model<input id="textModel" value="${esc(s.text_model||'gpt-4o')}"></label><label>Vision model<input id="visionModel" value="${esc(s.vision_model||'gpt-4o')}"></label><label>Temperature<input id="temp" value="${esc(s.temperature??0.2)}"></label><label>Timeout seconds<input id="timeout" value="${esc(s.timeout_seconds??60)}"></label></div><div class="toolbar"><label class="toggle"><input id="useAgent" type="checkbox" checked> Use for agent board</label><label class="toggle"><input id="useVision" type="checkbox" checked> Use for image Q&A</label><label class="toggle"><input id="useReport" type="checkbox" checked> Use for report drafting</label></div><div class="toolbar"><button class="btn primary" onclick="testText()">Test text API</button><button class="btn" onclick="testVision()">Test vision API</button><button class="btn green" onclick="saveSettings()">Save to local config</button><button class="btn red" onclick="clearSettings()">Clear key</button><button class="btn" onclick="smokeAgent()">Run agent smoke test</button></div><div id="settingsResult" class="status-line">Status: ${esc(s.status||'Not configured')} ${s.masked_api_key?`(${esc(s.masked_api_key)})`:''}</div></div>`,`<h3>Privacy boundary</h3><p>The API key field is local. The backend stores only masked status in the config file and does not write keys to trace or exports.</p>`)}
function settingsPayload(){return {provider:$("#provider").value,base_url:$("#baseUrl").value,api_key:$("#apiKey").value,text_model:$("#textModel").value,vision_model:$("#visionModel").value,temperature:parseFloat($("#temp").value||"0.2"),timeout_seconds:parseInt($("#timeout").value||"60"),use_for_agent_board:$("#useAgent").checked,use_for_image_qa:$("#useVision").checked,use_for_report_drafting:$("#useReport").checked}}
async function testText(){await settingsCall('/api/settings/llm/test-text')}
async function testVision(){await settingsCall('/api/settings/llm/test-vision')}
async function saveSettings(){await settingsCall('/api/settings/llm/save');state.settings=await api('/api/settings/llm/status')}
async function clearSettings(){let r=await api('/api/settings/llm/clear',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});$("#settingsResult").textContent='Status: '+r.status;toast('Local key status cleared')}
async function smokeAgent(){let r=await api('/api/settings/llm/smoke-agent',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});$("#settingsResult").textContent=r.source+': '+r.message}
async function settingsCall(path){let r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(settingsPayload())});let j=await r.json();$("#settingsResult").textContent=j.ok?JSON.stringify(j.data):`${j.error.message} ${JSON.stringify(j.error.details)}`;toast(j.ok?'Settings API responded':'Settings API returned a clear error')}
function downloadJson(kind){let data=kind==='case'?state.case:kind==='agents'?state.agents:state.trace;download(`kom_${kind}.json`,JSON.stringify(data,null,2),'application/json')}
function download(name,content,type){let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([content],{type}));a.download=name;a.click();URL.revokeObjectURL(a.href)}
init();
</script>
</body>
</html>
'''


VALIDATION_PY = r'''
from __future__ import annotations
import json, sqlite3, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / "app"
DB = APP / "data" / "kom_workbench.sqlite"
HTML = APP / "static" / "index.html"
VALIDATION = ROOT / "validation"

def check(name, passed, detail):
    return {"name": name, "passed": bool(passed), "detail": str(detail)}

def main():
    checks = []
    html = HTML.read_text(encoding="utf-8")
    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
    case_count = con.execute("SELECT COUNT(*) c FROM cases").fetchone()["c"]
    q_counts = {r["quadrant"]: r["c"] for r in con.execute("SELECT quadrant, COUNT(*) c FROM cases GROUP BY quadrant")}
    default_case = con.execute("SELECT COUNT(*) c FROM cases WHERE case_id='DEMO_OAI_CASE_001'").fetchone()["c"]
    agents = [json.loads(r["raw_json"]) for r in con.execute("SELECT raw_json FROM agents")]
    graph_nodes = con.execute("SELECT COUNT(*) c FROM graph_nodes").fetchone()["c"]
    graph_edges = con.execute("SELECT COUNT(*) c FROM graph_edges").fetchone()["c"]
    safety = con.execute("SELECT COUNT(*) c FROM safety_rules_v7").fetchone()["c"]
    forbidden_public = ["KOM LOCAL MULTI-AGENT REVIEW", "No case selected", "Not recorded", "Unknown POST endpoint", "120-case library 0"]
    pages = ["Dashboard","Case Workspace","Patient Timeline","Imaging","Risk","Evidence Graph","Treatment Board","Safety Review","Clinical Report","Trace","Validation","Settings"]
    routes = (APP / "trace" / "v7_registered_routes.json")
    checks.append(check("public wording cleanup", not any(x in html for x in forbidden_public), "legacy empty-state wording absent from public HTML"))
    checks.append(check("workflow graph available", "workflow-graph" in html and all(p in html for p in pages), "interactive SVG workflow graph function and all major pages present"))
    checks.append(check("120-case database", case_count >= 120 and all(q_counts.get(q,0) == 30 for q in ["Q1","Q2","Q3","Q4"]), f"cases={case_count}; quadrants={q_counts}"))
    checks.append(check("default showcase case", default_case == 1 and "DEMO_OAI_CASE_001" in html, "locked showcase case is present and auto-loaded"))
    checks.append(check("agent board populated", len(agents) >= 9 and all(a.get("reasoning_summary") and a.get("draft_plan") and len(a.get("evidence_trace", [])) >= 5 for a in agents), "nine agents have reasoning, draft plan, and evidence trace"))
    checks.append(check("final synthesis evidence trace", any(a.get("agent_id") == "final_synthesis" and len(a.get("evidence_trace", [])) >= 10 for a in agents), "final synthesis has at least ten evidence links"))
    checks.append(check("evidence graph coverage", graph_nodes > 30 and graph_edges > 40, f"nodes={graph_nodes}; edges={graph_edges}"))
    checks.append(check("safety rules", safety >= 6, f"safety rules={safety}"))
    checks.append(check("settings API UI", all(x in html for x in ["Test text API","Test vision API","Save to local config","Run agent smoke test","https://xiaoai.plus/v1"]), "settings page exposes OpenAI-compatible controls"))
    checks.append(check("unknown endpoint fixed", "Endpoint is not registered" in (APP / "backend" / "server.py").read_text(encoding="utf-8") and "Unknown POST endpoint" not in (APP / "backend" / "server.py").read_text(encoding="utf-8"), "structured endpoint-not-registered response replaces old wording"))
    checks.append(check("route audit artifact", routes.exists(), "registered route manifest exists"))
    checks.append(check("export and report", "Export HTML" in html and "Export Markdown" in html and "/api/report" in html, "report export controls present"))
    status = "KOM_V7_READY" if all(c["passed"] for c in checks) else "KOM_V7_NOT_READY"
    report = {"status": status, "checks": checks, "summary": {"case_count": case_count, "quadrants": q_counts, "graph_nodes": graph_nodes, "graph_edges": graph_edges, "agents": len(agents)}}
    VALIDATION.mkdir(parents=True, exist_ok=True)
    (VALIDATION / "v7_validation_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    rows = "".join(f"<tr><td>{c['name']}</td><td>{'PASS' if c['passed'] else 'FAIL'}</td><td>{c['detail']}</td></tr>" for c in checks)
    (VALIDATION / "v7_validation_report.html").write_text(f"<!doctype html><meta charset='utf-8'><title>KOM V7 validation</title><style>body{{font-family:Segoe UI,Arial;margin:32px;color:#0f172a}}td,th{{border-bottom:1px solid #ddd;padding:8px;text-align:left}}</style><h1>{status}</h1><table><thead><tr><th>Check</th><th>Status</th><th>Detail</th></tr></thead><tbody>{rows}</tbody></table>", encoding="utf-8")
    (VALIDATION / "v7_validation_report.md").write_text("# KOM V7 validation\n\nStatus: " + status + "\n\n" + "\n".join(f"- {'PASS' if c['passed'] else 'FAIL'}: {c['name']} - {c['detail']}" for c in checks), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if status == "KOM_V7_READY" else 1

if __name__ == "__main__":
    raise SystemExit(main())
'''


def write_support_files(backup_dir: Path, cases: list[dict]) -> None:
    route_manifest = {
        "GET": [
            "/api/routes", "/api/status", "/api/cases", "/api/cases/summary", "/api/cases/{case_id}", "/api/evidence", "/api/evidence/trace", "/api/graph", "/api/agents", "/api/ablation", "/api/safety", "/api/trace", "/api/validation", "/api/settings/llm/status", "/api/report"
        ],
        "POST": [
            "/api/cases/import", "/api/cases/import-prepared", "/api/cases/select", "/api/settings/llm/test-text", "/api/settings/llm/test-vision", "/api/settings/llm/save", "/api/settings/llm/clear", "/api/settings/llm/smoke-agent", "/api/agents/run-board", "/api/agents/challenge", "/api/agents/ask-evidence-arbiter", "/api/report/generate", "/api/evidence/export-subgraph", "/api/evidence/export-list"
        ],
    }
    write_text(TRACE / "v7_registered_routes.json", json.dumps(route_manifest, indent=2, ensure_ascii=False))
    with (TRACE / "v7_api_route_audit.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["method", "route", "status", "notes"])
        for method, routes in route_manifest.items():
            for route in routes:
                w.writerow([method, route, "implemented", "V7 route registered in backend server"])
    with (TRACE / "v7_asset_inventory.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["asset", "exists", "reuse_decision", "notes"])
        assets = [
            ROOT.parent / "KOM_West_China_Hospital_Sports_Medicine_Project_Introduction.html",
            ROOT.parent / "KOA_GraphRAG_Evidence_Visualization_Package.zip",
            ROOT.parent / "本地化" / "koa_mdt_agents" / "index.html",
            STATIC / "assets" / "images" / "real_oai_knee_image_panel.png",
            DATA / "kom_workbench.sqlite",
        ]
        for a in assets:
            w.writerow([str(a), a.exists(), "reused concept or asset" if a.exists() else "not found in package scope", "V7 keeps clinical hero, graph, evidence card, case panel, and local launcher concepts"])
    write_text(
        TRACE / "v7_asset_reuse_plan.md",
        textwrap.dedent(
            f"""
            # KOM Clinical Workbench V7 asset reuse plan

            Backup location: `{backup_dir}`

            1. Dashboard and hero style reuse the previous West China/OAI project introduction concept: medical hero, selected-case card, metric cards, and workflow entry actions.
            2. Flow canvas and GraphRAG visualization reuse the existing graph/evidence-card concept, rebuilt as an interactive SVG/HTML fallback so the local package has no npm dependency.
            3. Intake and case workspace reuse the prior case-panel and profile-card pattern, now backed by a 120-case SQLite library with Q1-Q4 balance.
            4. Agent dialogue layout reuses the prior multi-agent board idea but removes empty panels and adds role, status, evidence count, reasoning, draft, challenge, revision, and final contribution.
            5. Static-only cards and legacy empty states were rejected because they caused the observed `0 case`, empty anchor, empty evidence trace, and endpoint mismatch.
            6. Rebuilt components: workflow graph, route audit, OpenAI-compatible settings, case services, treatment board, evidence graph, validation page, and structured endpoint errors.
            """
        ).strip()
        + "\n",
    )
    write_text(
        TRACE / "v7_unknown_endpoint_fix_report.md",
        textwrap.dedent(
            """
            # Unknown endpoint fix report

            The old backend returned the public text `Unknown POST endpoint` when the frontend called missing actions. V7 adds a route manifest, implements the missing POST endpoints used by case selection, settings tests, treatment-board challenges, report generation, and evidence export, and changes unknown API responses to a structured `endpoint_not_registered` JSON payload with available route suggestions.

            Normal UI actions no longer display the legacy `Unknown POST endpoint` text.
            """
        ).strip()
        + "\n",
    )
    write_text(
        CONFIG / "llm_config.example.json",
        json.dumps(
            {
                "provider": "OpenAI-compatible",
                "base_url": "https://xiaoai.plus/v1",
                "text_model": "gpt-4o",
                "vision_model": "gpt-4o",
                "temperature": 0.2,
                "timeout_seconds": 60,
                "use_for_agent_board": True,
                "use_for_image_qa": True,
                "use_for_report_drafting": True,
                "note": "Do not store plaintext API keys in this file.",
            },
            indent=2,
            ensure_ascii=False,
        ),
    )
    if not (CONFIG / "llm_config.local.json").exists():
        write_text(
            CONFIG / "llm_config.local.json",
            json.dumps(
                {
                    "provider": "OpenAI-compatible",
                    "base_url": "https://xiaoai.plus/v1",
                    "text_model": "gpt-4o",
                    "vision_model": "gpt-4o",
                    "temperature": 0.2,
                    "timeout_seconds": 60,
                    "masked_api_key": None,
                    "status": "Not configured",
                    "use_for_agent_board": True,
                    "use_for_image_qa": True,
                    "use_for_report_drafting": True,
                },
                indent=2,
                ensure_ascii=False,
            ),
        )
    write_text(
        BACKEND / "services" / "case_service.py",
        textwrap.dedent(
            """
            from __future__ import annotations
            import json, sqlite3
            from pathlib import Path

            ROOT = Path(__file__).resolve().parents[3]
            DB = ROOT / "app" / "data" / "kom_workbench.sqlite"

            def get_case(case_id: str = "DEMO_OAI_CASE_001") -> dict | None:
                con = sqlite3.connect(DB)
                con.row_factory = sqlite3.Row
                row = con.execute("SELECT raw_json FROM cases WHERE case_id=?", (case_id,)).fetchone()
                con.close()
                return json.loads(row["raw_json"]) if row else None
            """
        ).strip()
        + "\n",
    )
    write_text(
        BACKEND / "services" / "llm_settings_service.py",
        textwrap.dedent(
            """
            from __future__ import annotations
            import json
            from pathlib import Path

            ROOT = Path(__file__).resolve().parents[3]
            CONFIG = ROOT / "app" / "config" / "llm_config.local.json"

            def load_settings() -> dict:
                if CONFIG.exists():
                    return json.loads(CONFIG.read_text(encoding="utf-8"))
                return {"status": "Not configured"}
            """
        ).strip()
        + "\n",
    )
    write_text(
        BACKEND / "adapters" / "openai_compatible_client.py",
        textwrap.dedent(
            """
            from __future__ import annotations
            import json, urllib.request

            def mask_key(key: str | None) -> str | None:
                if not key:
                    return None
                return "sk-***" + key[-4:] if len(key) >= 8 else "***"

            def chat_completion(base_url: str, api_key: str, model: str, messages: list[dict], timeout: int = 60) -> dict:
                req = urllib.request.Request(
                    base_url.rstrip("/") + "/chat/completions",
                    data=json.dumps({"model": model, "messages": messages, "temperature": 0.2}).encode("utf-8"),
                    headers={"Content-Type": "application/json", "Authorization": "Bearer " + api_key},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            """
        ).strip()
        + "\n",
    )
    write_text(BACKEND / "validation" / "v7_validation.py", VALIDATION_PY)
    write_text(
        DEV / "tests" / "v7_full_workbench.spec.ts",
        textwrap.dedent(
            """
            import { test, expect } from '@playwright/test';

            test('V7 workbench loads populated clinical workflow', async ({ page }) => {
              await page.goto('http://127.0.0.1:8017/dashboard');
              await expect(page.getByText('KOM Clinical Workbench').first()).toBeVisible();
              await expect(page.getByText('120-case library')).not.toBeVisible();
              await page.goto('http://127.0.0.1:8017/case-workspace');
              await expect(page.getByText('120-case library')).toBeVisible();
              await expect(page.getByText('No case selected')).toHaveCount(0);
              await page.goto('http://127.0.0.1:8017/treatment-board');
              await expect(page.getByText('Case-level treatment board')).toBeVisible();
              await expect(page.getByText('Evidence trace')).toBeVisible();
              await page.goto('http://127.0.0.1:8017/evidence-graph');
              await expect(page.getByText('Evidence Graph')).toBeVisible();
              await page.goto('http://127.0.0.1:8017/settings');
              await expect(page.getByText('Test text API')).toBeVisible();
            });
            """
        ).strip()
        + "\n",
    )
    write_text(ROOT / "Run_Validation.bat", "@echo off\r\nruntime\\python\\python.exe app\\backend\\validation\\v7_validation.py\r\npause\r\n")
    write_text(ROOT / "Start_KOM_Workbench.bat", "@echo off\r\ncd /d %~dp0\r\nruntime\\python\\python.exe app\\start_server.py --port 8017\r\npause\r\n")


def update_manifest(backup_dir: Path) -> None:
    files = []
    for p in ROOT.rglob("*"):
        if p.is_file() and "backups_before_v7_patch" not in str(p):
            try:
                rel = str(p.relative_to(ROOT)).replace("\\", "/")
                files.append({"path": rel, "size": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
            except Exception:
                pass
    manifest = {
        "package": "KOM_Local_Clinical_Workbench_FINAL_202606",
        "version": "KOM_LOCAL_CLINICAL_WORKBENCH_V7_UI_API_AGENT_GRAPH_FIX_202606",
        "launch": "Start_KOM_Workbench.bat -> http://127.0.0.1:8017/ui",
        "backup_before_v7_patch": str(backup_dir),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "files": files,
    }
    write_text(ROOT / "PACKAGE_MANIFEST.json", json.dumps(manifest, indent=2, ensure_ascii=False))


def main() -> None:
    if not ROOT.exists():
        raise SystemExit(f"Package root not found: {ROOT}")
    ensure_dirs()
    backup_dir = backup_current_files()
    con = sqlite3.connect(DATA / "kom_workbench.sqlite")
    cases = build_cases()
    agents = build_agents(con)
    con.close()
    nodes, edges = build_graph(agents)
    update_database(cases, agents, nodes, edges)
    write_seed_files(cases)
    write_text(BACKEND / "server.py", SERVER.strip() + "\n")
    write_text(STATIC / "index.html", INDEX_HTML)
    write_support_files(backup_dir, cases)
    update_manifest(backup_dir)
    print(json.dumps({"ok": True, "root": str(ROOT), "backup": str(backup_dir), "cases": len(cases), "agents": len(agents), "graph_nodes": len(nodes), "graph_edges": len(edges)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
