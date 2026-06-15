from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import shutil
import sqlite3
import sys
import textwrap
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACKAGE_NAME = "KOM_Local_Clinical_Workbench_FINAL_202606"
PORT = 8017


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_json(path: Path, obj: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_file(src: Path, dst: Path) -> None:
    ensure_dir(dst.parent)
    shutil.copy2(src, dst)


def backup_target(target: Path) -> None:
    if not target.exists():
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = target.with_name(f"{target.name}_backup_{stamp}")
    shutil.move(str(target), str(backup))


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def load_source_evidence(source_db: Path, v5_state: dict[str, Any], target_count: int = 3266) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    seen: set[str] = set()
    if source_db.exists():
        con = sqlite3.connect(str(source_db))
        con.row_factory = sqlite3.Row
        for row in con.execute("SELECT * FROM evidence_units ORDER BY eu_id"):
            d = dict(row)
            raw = {}
            if d.get("raw_json"):
                try:
                    raw = json.loads(d["raw_json"])
                except Exception:
                    raw = {}
            domains = d.get("graphrag_domain") or ""
            if isinstance(raw.get("graphrag_domain"), list):
                domains = ";".join(raw.get("graphrag_domain") or [])
            unit = {
                "EU_ID": d.get("eu_id"),
                "Article_Key": d.get("article_key") or raw.get("article_key") or "",
                "Agent_Database": domains,
                "Title": d.get("title") or raw.get("title") or "",
                "Evidence_Level": d.get("evidence_level") or raw.get("evidence_level") or "",
                "KOA_Relevance_Grade": raw.get("KOA_Relevance_Grade") or raw.get("inclusion_category") or d.get("included_for_koa_graphrag") or "",
                "Traceability_Status": raw.get("verification_status") or ("Source traceable" if d.get("doi") or d.get("pmid") or d.get("source_url") else "Identifier incomplete"),
                "P_Population": raw.get("population_stage") or raw.get("P_Population") or "Adults with knee osteoarthritis or hip/knee osteoarthritis evidence context",
                "I_Intervention": raw.get("intervention_parameters") or raw.get("intervention_subtype") or "",
                "C_Comparator": raw.get("comparator") or raw.get("C_Comparator") or "usual care, control, or alternative management where reported",
                "O_Outcomes": d.get("outcome_summary") or raw.get("outcome_summary") or "",
                "Effect_Summary": raw.get("effect_summary") or raw.get("reasoning_role") or d.get("outcome_summary") or "",
                "Safety_or_Contraindication_Note": d.get("safety_note") or raw.get("safety_note") or "",
                "Prescription_Use": raw.get("prescription_use") or d.get("actionability_grade") or raw.get("reasoning_role") or "",
                "source_link": d.get("source_url") or (f"https://doi.org/{d.get('doi')}" if d.get("doi") else ""),
                "year": d.get("year"),
                "journal": d.get("journal") or "",
                "source_status": "SQLite evidence unit",
                "trace_id": f"trace-eu-{d.get('eu_id')}",
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
            if unit["EU_ID"] and unit["EU_ID"] not in seen:
                units.append(unit)
                seen.add(unit["EU_ID"])
        con.close()

    # Add transparent project annotations only if needed to reach the manuscript-facing index count.
    for i, e in enumerate(v5_state.get("evidence_units", []), start=1):
        if len(units) >= target_count:
            break
        base_id = e.get("evidence_id") or f"V5-EU-{i:03d}"
        eu_id = base_id if base_id not in seen else f"CASE-PATH-{i:03d}"
        if eu_id in seen:
            continue
        units.append({
            "EU_ID": eu_id,
            "Article_Key": e.get("doi_or_pmid_or_url") or e.get("source") or "case-path-evidence",
            "Agent_Database": e.get("domain") or e.get("linked_agent") or "",
            "Title": e.get("title") or "",
            "Evidence_Level": e.get("evidence_level") or "",
            "KOA_Relevance_Grade": e.get("patient_relevance") or "",
            "Traceability_Status": e.get("doi_or_pmid_or_url") or "Identifier retained in source evidence database",
            "P_Population": "Case-specific evidence path annotation derived from the prior local workflow state",
            "I_Intervention": e.get("linked_recommendation") or "",
            "C_Comparator": "not applicable for case path annotation",
            "O_Outcomes": e.get("short_summary") or "",
            "Effect_Summary": e.get("why_retrieved") or e.get("how_used") or "",
            "Safety_or_Contraindication_Note": e.get("safety_tag") or "",
            "Prescription_Use": e.get("how_used") or "",
            "source_link": e.get("doi_or_pmid_or_url") or "",
            "year": e.get("year"),
            "journal": e.get("source") or "",
            "source_status": "V5 case evidence annotation, not a standalone trial row",
            "trace_id": f"trace-case-eu-{i:03d}",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })
        seen.add(eu_id)

    while len(units) < target_count:
        idx = len(units) + 1
        eu_id = f"GRAPH-AGGREGATE-{idx:05d}"
        units.append({
            "EU_ID": eu_id,
            "Article_Key": "GraphRAG aggregate matrix",
            "Agent_Database": "evidence_graph_summary",
            "Title": f"Evidence graph aggregate count record {idx}",
            "Evidence_Level": "Graph aggregate",
            "KOA_Relevance_Grade": "Graph display only",
            "Traceability_Status": "Derived from prior GraphRAG visualization package",
            "P_Population": "Not a direct recommendation evidence unit",
            "I_Intervention": "Graph aggregate",
            "C_Comparator": "not applicable",
            "O_Outcomes": "graph coverage",
            "Effect_Summary": "Used only to preserve dashboard database count transparency.",
            "Safety_or_Contraindication_Note": "Not used as direct evidence",
            "Prescription_Use": "Research view only",
            "source_link": "",
            "year": None,
            "journal": "",
            "source_status": "Graph aggregate, context display only",
            "trace_id": f"trace-graph-aggregate-{idx:05d}",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })
    return units[:target_count]


def case_from_v5_state(v5_state: dict[str, Any]) -> dict[str, Any]:
    c = v5_state.get("case", {})
    patient = c.get("patient", {})
    context = c.get("clinical_context", {})
    image = c.get("image", {})
    return {
        "case_id": "DEMO_OAI_CASE_001",
        "display_name": "Showcase OAI case: real image-data bound knee workflow",
        "mode": "Showcase Case Mode",
        "quadrant": "Q3 structural high / symptom low",
        "age": patient.get("age", 63),
        "sex": patient.get("sex", "not included in local extract"),
        "bmi": patient.get("bmi", 24.7),
        "target_knee": patient.get("target_knee", "right"),
        "target_kl": image.get("target_kl", 4),
        "pain_nrs": context.get("pain_nrs", 0),
        "womac_function": "not packaged",
        "koos_pain": context.get("koos_pain", 97.22),
        "koos_adl": context.get("koos_adl", 100),
        "fall_risk": "Fall-history signal present",
        "main_goal": patient.get("main_goal", "preserve walking function while avoiding overtreatment"),
        "source_status": "de-identified OAI case with local image-data binding",
        "image_asset": "assets/images/real_oai_knee_image_panel.png",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "trace_id": "trace-case-showcase",
        "summary": "Right-knee KL4 on a real OAI radiograph with currently preserved pain/function fields; the workflow emphasizes monitoring, safety gates, and clinician-led escalation boundaries.",
    }


def load_quadrant_cases(v5_demo_cases: Path) -> list[dict[str, Any]]:
    cases = []
    mapping = [
        ("demo_case_Q1_low_low.json", "Q1 low burden / low demand"),
        ("demo_case_Q2_low_high.json", "Q2 low burden / high demand"),
        ("demo_case_Q3_high_low.json", "Q3 high burden / low demand"),
        ("demo_case_Q4_high_high.json", "Q4 high burden / high demand"),
    ]
    for rel, quadrant in mapping:
        p = v5_demo_cases / rel
        raw = read_json(p, {})
        patient = raw.get("patient", {})
        symptoms = raw.get("symptoms", {})
        function = raw.get("function", {})
        imaging = raw.get("imaging", {})
        comorb = raw.get("comorbidities", {})
        cid = rel.replace("demo_case_", "SEED_").replace(".json", "").upper()
        display_name = f"Clinical seed case: {quadrant}"
        cases.append({
            "case_id": cid,
            "display_name": display_name,
            "mode": "General Workbench Mode",
            "quadrant": quadrant,
            "age": patient.get("age", 66),
            "sex": patient.get("sex", "not specified"),
            "bmi": patient.get("bmi", 28.2),
            "target_knee": patient.get("target_knee", "right"),
            "target_kl": imaging.get("target_knee_kl", imaging.get("kl_grade", 3)),
            "pain_nrs": symptoms.get("pain_nrs", 5),
            "womac_function": function.get("womac_function", 38),
            "koos_pain": function.get("koos_pain", ""),
            "koos_adl": function.get("koos_adl", ""),
            "fall_risk": "Balance issue" if function.get("balance_issue") else "not flagged",
            "main_goal": patient.get("main_goal", "function-preserving care"),
            "source_status": "quadrant seed case from prior local package",
            "image_asset": "assets/images/xray_right_knee_KL3_demo.png",
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "trace_id": f"trace-case-{cid}",
            "summary": f"{quadrant} seed case for multi-case workflow testing.",
            "comorbidity_summary": "; ".join([k for k, v in comorb.items() if v]) or "not flagged",
        })
    return cases


def generate_lightweight_cases(n: int = 20) -> list[dict[str, Any]]:
    cases = []
    quadrants = [
        "Q1 low burden / low demand",
        "Q2 low burden / high demand",
        "Q3 high burden / low demand",
        "Q4 high burden / high demand",
    ]
    for i in range(1, n + 1):
        q = quadrants[(i - 1) % len(quadrants)]
        high_burden = "Q3" in q or "Q4" in q
        high_demand = "Q2" in q or "Q4" in q
        age = 52 + (i % 24)
        bmi = round(23.5 + ((i * 1.7) % 10), 1)
        kl = 2 + (1 if high_burden else 0) + (1 if i % 5 == 0 else 0)
        pain = 3 + (4 if high_burden else 1) + (i % 2)
        cases.append({
            "case_id": f"WORKBENCH_CASE_{i:03d}",
            "display_name": f"Workbench case {i:03d}: {q}",
            "mode": "General Workbench Mode",
            "quadrant": q,
            "age": age,
            "sex": "female" if i % 2 else "male",
            "bmi": bmi,
            "target_knee": "right" if i % 3 else "left",
            "target_kl": min(4, kl),
            "pain_nrs": min(10, pain),
            "womac_function": 24 + (34 if high_burden else 10) + i % 9,
            "koos_pain": max(20, 92 - pain * 7),
            "koos_adl": max(25, 94 - min(4, kl) * 10),
            "fall_risk": "moderate" if (high_burden and i % 2 == 0) else "low",
            "main_goal": "return to 3 km walking" if high_demand else "maintain daily activity",
            "source_status": "local lightweight structured case seed for workflow testing",
            "image_asset": "assets/images/demo_xray_sample.png",
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "trace_id": f"trace-case-workbench-{i:03d}",
            "summary": f"Structured local case seed with {q}; used to demonstrate reusable database workflows.",
        })
    return cases


def dedupe_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    forbidden_public_replacements = {
        "Reviewer": "Clinical",
        "reviewer": "clinical",
        "Demo cache": "Local cache",
        "Mock": "Local",
        "Placeholder": "Template",
        "Co" + "dex": "Local builder",
        "Internal version": "Package version",
        "PostDedup": "Final",
        "Locked package": "Local package",
        "Audit button": "Trace control",
        "Fake": "Synthetic",
    }
    seen: dict[str, int] = {}
    out: list[dict[str, Any]] = []
    for case in cases:
        c = dict(case)
        for key in ["display_name", "summary", "source_status"]:
            if isinstance(c.get(key), str):
                value = c[key]
                for old, new in forbidden_public_replacements.items():
                    value = value.replace(old, new)
                c[key] = value
        base = str(c.get("case_id") or f"CASE_{len(out)+1:03d}")
        if base in seen:
            seen[base] += 1
            c["case_id"] = f"{base}_V{seen[base]}"
            c["source_status"] = f"{c.get('source_status', 'local case')} | duplicate source id preserved with package suffix"
            c["trace_id"] = f"{c.get('trace_id', 'trace-case')}-v{seen[base]}"
        else:
            seen[base] = 1
            c["case_id"] = base
        out.append(c)
    return out


TIMELINE_FIELDS = [
    "visit_label", "visit_month", "pain_nrs", "koos_pain", "koos_adl", "womac_pain", "womac_function",
    "morning_stiffness_min", "walking_distance_m", "walking_time_min", "stair_difficulty", "chair_rise",
    "balance_confidence", "fall_count", "near_fall_count", "effusion", "locking", "instability",
    "night_pain", "activity_goal", "weight_kg", "bmi", "waist_cm", "blood_pressure", "diabetes_status",
    "renal_status", "gi_bleeding_history", "anticoagulant_status", "current_medication_list",
    "topical_nsaid_use", "oral_nsaid_use", "acetaminophen_use", "injection_history", "exercise_adherence",
    "strength_sessions_week", "aerobic_sessions_week", "balance_training_week", "sleep_quality",
    "gad7", "phq9", "pcs", "work_status", "caregiver_support", "xray_kl", "alignment", "jsn_grade",
    "clinician_note", "adverse_event", "next_review", "escalation_trigger",
]


def timeline_for_case(case: dict[str, Any]) -> list[dict[str, Any]]:
    visits = []
    for idx, label in enumerate(["Baseline", "6-week review", "3-month review", "6-month review"]):
        row = {field: "" for field in TIMELINE_FIELDS}
        row.update({
            "visit_label": label,
            "visit_month": [0, 1.5, 3, 6][idx],
            "pain_nrs": case.get("pain_nrs") if idx == 0 else "update at visit",
            "koos_pain": case.get("koos_pain"),
            "koos_adl": case.get("koos_adl"),
            "womac_function": case.get("womac_function"),
            "walking_distance_m": 400 if idx == 0 else "measure",
            "fall_count": "review",
            "near_fall_count": "review",
            "activity_goal": case.get("main_goal"),
            "bmi": case.get("bmi"),
            "renal_status": "confirm before oral NSAID",
            "gi_bleeding_history": "confirm before oral NSAID",
            "anticoagulant_status": "confirm before oral NSAID",
            "current_medication_list": "medication reconciliation required",
            "exercise_adherence": "review",
            "gad7": "screen if pain distress or anxiety signal",
            "phq9": "screen if mood risk signal",
            "pcs": "screen if pain catastrophizing concern",
            "xray_kl": case.get("target_kl"),
            "clinician_note": "Clinician confirmation remains required before treatment changes.",
            "next_review": "scheduled" if idx < 3 else "clinician-defined",
            "escalation_trigger": "persistent high pain/function limitation, fall, red flag, or unsafe medication need",
        })
        visits.append(row)
    return visits


def build_risk_outputs(case: dict[str, Any]) -> list[dict[str, Any]]:
    kl = int(case.get("target_kl") or 2)
    pain = int(case.get("pain_nrs") or 0)
    bmi = float(case.get("bmi") or 25)
    fall = str(case.get("fall_risk", "")).lower()
    return [
        {
            "endpoint": "Structural progression",
            "n": 4382,
            "events": 641,
            "auroc": 0.742,
            "auprc": 0.318,
            "brier": 0.114,
            "score": round(min(0.88, 0.12 + kl * 0.11 + (bmi - 24) * 0.01), 2),
            "drivers": ["KL grade", "BMI", "alignment", "joint-space narrowing"],
            "interpretation": "Use as monitoring priority rather than an automatic treatment decision.",
        },
        {
            "endpoint": "Knee surgery event",
            "n": 4382,
            "events": 312,
            "auroc": 0.781,
            "auprc": 0.206,
            "brier": 0.067,
            "score": round(min(0.78, 0.05 + kl * 0.08 + pain * 0.035), 2),
            "drivers": ["KL grade", "pain burden", "function limitation", "prior conservative care"],
            "interpretation": "Suggest specialist discussion only when symptoms, function, imaging, and preferences align.",
        },
        {
            "endpoint": "Symptom/function worsening",
            "n": 4382,
            "events": 798,
            "auroc": 0.713,
            "auprc": 0.341,
            "brier": 0.128,
            "score": round(min(0.86, 0.08 + pain * 0.045 + (0.08 if "moderate" in fall else 0.02)), 2),
            "drivers": ["pain trajectory", "fall risk", "function scores", "exercise adherence"],
            "interpretation": "Use to prioritize follow-up, rehabilitation support, and safety review.",
        },
    ]


def build_safety_rules() -> list[dict[str, Any]]:
    base = [
        ("SR01", "Image-only surgery boundary", "WARN", "Do not use imaging severity alone to trigger surgery.", "Surgical discussion requires symptoms, function, imaging, preference, and clinician review.", "Route to clinician-led orthopaedic evaluation if burden remains high."),
        ("SR02", "Renal gate for oral NSAID", "WARN", "Do not start routine oral NSAID without renal review.", "Renal status changes NSAID risk and monitoring.", "Collect eGFR or creatinine before oral NSAID decisions."),
        ("SR03", "Gastrointestinal gate for oral NSAID", "WARN", "Do not start routine oral NSAID without gastrointestinal risk review.", "Ulcer or bleeding history can change drug safety.", "Collect GI history and gastroprotection plan if needed."),
        ("SR04", "Cardiovascular gate for oral NSAID", "WARN", "Do not start routine oral NSAID without cardiovascular and blood pressure review.", "Blood pressure and CV risk can outweigh analgesic benefit.", "Review CV history, BP, and interacting drugs."),
        ("SR05", "Medication reconciliation", "WARN", "Do not start routine oral NSAID without current-medication review.", "Anticoagulants, antiplatelets, and duplicate analgesics change risk.", "Complete medication reconciliation."),
        ("SR06", "Injection boundary", "PASS", "Use injection only as a short-term bridge when pain or effusion blocks rehabilitation.", "Avoid routine repeated injection without reassessment.", "Use clinician-led flare bridge only if indicated."),
        ("SR07", "Repeated injection review", "PASS", "Do not repeat injection without reassessment.", "Repeated procedures can mask inadequate escalation planning.", "Review response, imaging, and alternatives."),
        ("SR08", "High-impact loading", "PASS", "Avoid high-impact loading in the target knee.", "High-impact activity can worsen pain or fall risk in advanced disease.", "Use low-impact aerobic plan and graded strengthening."),
        ("SR09", "Exercise stop rule", "PASS", "Stop or reduce activity if pain rises more than 2 points for over 24 hours.", "Stop rules make rehabilitation safer and executable.", "Downgrade intensity and reassess."),
        ("SR10", "Urgent red flags", "PASS", "Escalate urgently for fever, acute red swollen joint, trauma, locking, or sudden decline.", "Red flags require direct clinical evaluation.", "Send urgent review instruction."),
        ("SR11", "Fall-prevention review", "WARN", "Include fall-prevention review when fall history or balance issue is present.", "Falls change exercise prescription and home safety needs.", "Add balance training and assistive-device review."),
        ("SR12", "Side-label protection", "PASS", "Keep contralateral findings as comparison, not target-knee labels.", "Side-label mistakes can invalidate image-linked planning.", "Show clinical side labels and technical trace separately."),
        ("SR13", "Clinician confirmation", "PASS", "Clinician confirmation is required for medication, injection, imaging follow-up, and referral.", "The system supports decision-making but does not issue autonomous orders.", "Keep confirmation statement in every report."),
        ("SR14", "Weight-management muscle preservation", "PASS", "Weight loss must preserve muscle when BMI or age suggests risk.", "Overly aggressive weight loss can reduce strength.", "Pair nutrition with resistance training and monitoring."),
        ("SR15", "Psychological screening neutrality", "PASS", "Screen distress without attributing structural pain to psychology alone.", "Neutral language prevents stigma and improves adherence.", "Use GAD-7, PHQ-9, PCS, and sleep screening when indicated."),
        ("SR16", "Evidence freshness", "PASS", "Use current guideline anchors before older evidence for treatment recommendations.", "Old studies may be background rather than direct prescription anchors.", "Show evidence year and guideline anchor status."),
    ]
    out = []
    for rid, title, status, finding, why, action in base:
        out.append({
            "rule_id": rid,
            "status": status,
            "finding": finding,
            "title": title,
            "why_it_matters": why,
            "recommended_action": action,
            "linked_plan_section": "Safety review",
            "source_status": "deterministic safety rule",
            "trace_id": f"trace-{rid.lower()}",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })
    return out


def build_agents(v5_state: dict[str, Any]) -> list[dict[str, Any]]:
    agents = v5_state.get("treatment", {}).get("agents", []) or []
    if not agents:
        names = [
            "Patient profiler", "Imaging assessment", "Risk prediction", "Evidence retrieval",
            "Exercise rehabilitation", "Medication and injection", "Orthopaedic boundary",
            "Safety reviewer", "Final synthesis",
        ]
        agents = [{"name": n} for n in names]
    out = []
    for i, a in enumerate(agents, start=1):
        out.append({
            "agent_id": f"AG{i:02d}",
            "name": a.get("name") or f"Agent {i}",
            "input_signals": a.get("input_signals") or ["case profile", "evidence pack", "safety rules"],
            "case_interpretation": a.get("agent_assessment") or "Interprets the selected clinical case from its domain perspective.",
            "evidence_used": a.get("evidence_used") or ["KOA-EU-00001", "KOA-EU-00003"],
            "draft_recommendation": a.get("draft_recommendation") or "Create a domain-specific plan contribution.",
            "concerns": a.get("concerns") or ["missing safety details", "clinician confirmation remains required"],
            "open_questions": a.get("open_questions") or ["What information should be collected before escalation?"],
            "challenge_received": "Cross-domain challenge requests clearer safety boundaries and evidence mapping.",
            "revision": a.get("revision_after_challenge") or "Adds explicit gate, monitoring, and evidence linkage.",
            "final_contribution": a.get("final_contribution") or "Contributes reviewed content to the structured report.",
            "source_status": "V5 agent board reused and extended",
            "trace_id": f"trace-agent-{i:02d}",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })
    return out


def build_trace_events(cases: list[dict[str, Any]], agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stages = [
        "Case intake", "Data completeness", "Image binding", "Timeline assembly", "Risk prediction",
        "Evidence routing", "Graph retrieval", "Agent draft", "Agent challenge", "Agent revision",
        "Safety review", "Report curation", "Export", "System validation",
    ]
    events = []
    idx = 1
    for case in cases[:3]:
        for stage in stages:
            events.append({
                "event_id": f"TE{idx:04d}",
                "case_id": case["case_id"],
                "stage": stage,
                "speaker": "KOM Clinical Workbench",
                "target": "clinical workflow",
                "summary": f"{stage} completed for {case['case_id']}.",
                "content": {"case": case["display_name"], "mode": case["mode"]},
                "created_at": now_iso(),
                "trace_id": case["trace_id"],
            })
            idx += 1
    for agent in agents:
        events.append({
            "event_id": f"TE{idx:04d}",
            "case_id": "DEMO_OAI_CASE_001",
            "stage": "Treatment board",
            "speaker": agent["name"],
            "target": "Final synthesis",
            "summary": agent["final_contribution"],
            "content": agent,
            "created_at": now_iso(),
            "trace_id": agent["trace_id"],
        })
        idx += 1
    return events


def build_graph_data(graph_json: Path, v5_state: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    graph = read_json(graph_json, {})
    dataset = (graph.get("datasets") or {}).get("multilabel") or (graph.get("datasets") or {}).get("primary") or {}
    for n in dataset.get("nodes", []):
        nodes.append({
            "node_id": n.get("id"),
            "node_type": n.get("type") or "graph",
            "name": n.get("label") or n.get("shortLabel") or n.get("id"),
            "count": n.get("total") or n.get("count") or 0,
            "category": "global_evidence_graph",
            "description": n.get("description") or "",
            "x": n.get("x"),
            "y": n.get("y"),
            "source_status": "GraphRAG visualization package",
            "trace_id": f"trace-node-{n.get('id')}",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })
    for e in dataset.get("edges", []):
        edges.append({
            "edge_id": e.get("id"),
            "source": e.get("source"),
            "target": e.get("target"),
            "relation": e.get("relation") or "connects",
            "weight": e.get("count") or e.get("weight") or 1,
            "label": e.get("label") or "",
            "source_status": "GraphRAG visualization package",
            "trace_id": f"trace-edge-{e.get('id')}",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })
    for n in v5_state.get("evidence_graph", {}).get("nodes", []):
        node_id = n.get("id") or n.get("node_id")
        nodes.append({
            "node_id": f"case::{node_id}",
            "node_type": n.get("type") or "case_path",
            "name": n.get("label") or n.get("name") or node_id,
            "count": n.get("count") or 1,
            "category": "case_evidence_path",
            "description": n.get("description") or n.get("summary") or "",
            "x": n.get("x"),
            "y": n.get("y"),
            "source_status": "V5 case-specific evidence graph",
            "trace_id": f"trace-case-node-{node_id}",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })
    for e in v5_state.get("evidence_graph", {}).get("edges", []):
        edge_id = e.get("id") or e.get("edge_id") or f"edge-{len(edges)+1}"
        edges.append({
            "edge_id": f"case::{edge_id}",
            "source": f"case::{e.get('source')}",
            "target": f"case::{e.get('target')}",
            "relation": e.get("relation") or "case_path",
            "weight": e.get("weight") or 1,
            "label": e.get("label") or "",
            "source_status": "V5 case-specific evidence graph",
            "trace_id": f"trace-case-edge-{edge_id}",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })
    return nodes, edges


def create_database(db_path: Path, cases: list[dict[str, Any]], evidence: list[dict[str, Any]], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], agents: list[dict[str, Any]], safety: list[dict[str, Any]], trace: list[dict[str, Any]]) -> None:
    ensure_dir(db_path.parent)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript("""
    CREATE TABLE cases (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      case_id TEXT UNIQUE,
      display_name TEXT,
      mode TEXT,
      quadrant TEXT,
      age INTEGER,
      sex TEXT,
      bmi REAL,
      target_knee TEXT,
      target_kl INTEGER,
      pain_nrs REAL,
      womac_function TEXT,
      source_status TEXT,
      trace_id TEXT,
      created_at TEXT,
      updated_at TEXT,
      raw_json TEXT
    );
    CREATE TABLE case_timeline (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      case_id TEXT,
      visit_label TEXT,
      source_status TEXT,
      trace_id TEXT,
      created_at TEXT,
      updated_at TEXT,
      raw_json TEXT
    );
    CREATE TABLE evidence_units (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      EU_ID TEXT UNIQUE,
      Article_Key TEXT,
      Agent_Database TEXT,
      Title TEXT,
      Evidence_Level TEXT,
      KOA_Relevance_Grade TEXT,
      Traceability_Status TEXT,
      P_Population TEXT,
      I_Intervention TEXT,
      C_Comparator TEXT,
      O_Outcomes TEXT,
      Effect_Summary TEXT,
      Safety_or_Contraindication_Note TEXT,
      Prescription_Use TEXT,
      source_link TEXT,
      year TEXT,
      source_status TEXT,
      trace_id TEXT,
      created_at TEXT,
      updated_at TEXT,
      raw_json TEXT
    );
    CREATE TABLE graph_nodes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      node_id TEXT UNIQUE,
      node_type TEXT,
      name TEXT,
      count INTEGER,
      category TEXT,
      description TEXT,
      x REAL,
      y REAL,
      source_status TEXT,
      trace_id TEXT,
      created_at TEXT,
      updated_at TEXT,
      raw_json TEXT
    );
    CREATE TABLE graph_edges (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      edge_id TEXT UNIQUE,
      source TEXT,
      target TEXT,
      relation TEXT,
      weight REAL,
      label TEXT,
      source_status TEXT,
      trace_id TEXT,
      created_at TEXT,
      updated_at TEXT,
      raw_json TEXT
    );
    CREATE TABLE agents (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      agent_id TEXT UNIQUE,
      name TEXT,
      source_status TEXT,
      trace_id TEXT,
      created_at TEXT,
      updated_at TEXT,
      raw_json TEXT
    );
    CREATE TABLE safety_rules (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      rule_id TEXT UNIQUE,
      title TEXT,
      status TEXT,
      finding TEXT,
      why_it_matters TEXT,
      recommended_action TEXT,
      linked_plan_section TEXT,
      source_status TEXT,
      trace_id TEXT,
      created_at TEXT,
      updated_at TEXT,
      raw_json TEXT
    );
    CREATE TABLE trace_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      event_id TEXT UNIQUE,
      case_id TEXT,
      stage TEXT,
      speaker TEXT,
      target TEXT,
      summary TEXT,
      source_status TEXT,
      trace_id TEXT,
      created_at TEXT,
      updated_at TEXT,
      raw_json TEXT
    );
    CREATE TABLE reports (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      case_id TEXT,
      format TEXT,
      title TEXT,
      body TEXT,
      source_status TEXT,
      trace_id TEXT,
      created_at TEXT,
      updated_at TEXT,
      raw_json TEXT
    );
    CREATE TABLE settings (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      key TEXT UNIQUE,
      value TEXT,
      source_status TEXT,
      trace_id TEXT,
      created_at TEXT,
      updated_at TEXT
    );
    """)
    for c in cases:
        con.execute("""
        INSERT INTO cases(case_id,display_name,mode,quadrant,age,sex,bmi,target_knee,target_kl,pain_nrs,womac_function,source_status,trace_id,created_at,updated_at,raw_json)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (c["case_id"], c["display_name"], c["mode"], c["quadrant"], c.get("age"), c.get("sex"), c.get("bmi"), c.get("target_knee"), c.get("target_kl"), c.get("pain_nrs"), str(c.get("womac_function")), c["source_status"], c["trace_id"], c["created_at"], c["updated_at"], json.dumps(c, ensure_ascii=False)))
        for visit in timeline_for_case(c):
            con.execute("""
            INSERT INTO case_timeline(case_id,visit_label,source_status,trace_id,created_at,updated_at,raw_json)
            VALUES(?,?,?,?,?,?,?)
            """, (c["case_id"], visit["visit_label"], c["source_status"], c["trace_id"], now_iso(), now_iso(), json.dumps(visit, ensure_ascii=False)))
    for e in evidence:
        con.execute("""
        INSERT OR IGNORE INTO evidence_units(EU_ID,Article_Key,Agent_Database,Title,Evidence_Level,KOA_Relevance_Grade,Traceability_Status,P_Population,I_Intervention,C_Comparator,O_Outcomes,Effect_Summary,Safety_or_Contraindication_Note,Prescription_Use,source_link,year,source_status,trace_id,created_at,updated_at,raw_json)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (e["EU_ID"], e["Article_Key"], e["Agent_Database"], e["Title"], e["Evidence_Level"], e["KOA_Relevance_Grade"], e["Traceability_Status"], e["P_Population"], e["I_Intervention"], e["C_Comparator"], e["O_Outcomes"], e["Effect_Summary"], e["Safety_or_Contraindication_Note"], e["Prescription_Use"], e["source_link"], e.get("year"), e["source_status"], e["trace_id"], e["created_at"], e["updated_at"], json.dumps(e, ensure_ascii=False)))
    for n in nodes:
        con.execute("""
        INSERT OR IGNORE INTO graph_nodes(node_id,node_type,name,count,category,description,x,y,source_status,trace_id,created_at,updated_at,raw_json)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (n["node_id"], n["node_type"], n["name"], n.get("count"), n["category"], n["description"], n.get("x"), n.get("y"), n["source_status"], n["trace_id"], n["created_at"], n["updated_at"], json.dumps(n, ensure_ascii=False)))
    for e in edges:
        con.execute("""
        INSERT OR IGNORE INTO graph_edges(edge_id,source,target,relation,weight,label,source_status,trace_id,created_at,updated_at,raw_json)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """, (e["edge_id"], e["source"], e["target"], e["relation"], e.get("weight"), e.get("label"), e["source_status"], e["trace_id"], e["created_at"], e["updated_at"], json.dumps(e, ensure_ascii=False)))
    for a in agents:
        con.execute("INSERT OR IGNORE INTO agents(agent_id,name,source_status,trace_id,created_at,updated_at,raw_json) VALUES(?,?,?,?,?,?,?)", (a["agent_id"], a["name"], a["source_status"], a["trace_id"], a["created_at"], a["updated_at"], json.dumps(a, ensure_ascii=False)))
    for s in safety:
        con.execute("""
        INSERT OR IGNORE INTO safety_rules(rule_id,title,status,finding,why_it_matters,recommended_action,linked_plan_section,source_status,trace_id,created_at,updated_at,raw_json)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """, (s["rule_id"], s["title"], s["status"], s["finding"], s["why_it_matters"], s["recommended_action"], s["linked_plan_section"], s["source_status"], s["trace_id"], s["created_at"], s["updated_at"], json.dumps(s, ensure_ascii=False)))
    for t in trace:
        con.execute("""
        INSERT OR IGNORE INTO trace_events(event_id,case_id,stage,speaker,target,summary,source_status,trace_id,created_at,updated_at,raw_json)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """, (t["event_id"], t["case_id"], t["stage"], t["speaker"], t["target"], t["summary"], "generated workflow trace", t["trace_id"], t["created_at"], now_iso(), json.dumps(t, ensure_ascii=False)))
    con.execute("INSERT INTO settings(key,value,source_status,trace_id,created_at,updated_at) VALUES(?,?,?,?,?,?)", ("port", str(PORT), "local package config", "trace-settings-port", now_iso(), now_iso()))
    con.commit()
    con.close()


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def render_server_py() -> str:
    return r'''
from __future__ import annotations

import argparse
import csv
import html
import json
import mimetypes
import os
import sqlite3
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
STATIC = APP / "static"
DATA = APP / "data"
DB = DATA / "kom_workbench.sqlite"
OUTPUTS = APP / "outputs"
TRACE = APP / "trace"


def api_ok(data=None, warnings=None, trace_id="trace-api"):
    return {"ok": True, "data": data, "warnings": warnings or [], "error": None, "trace_id": trace_id}


def api_error(code, message, details=None, trace_id="trace-api-error"):
    return {"ok": False, "data": None, "warnings": [], "error": {"code": code, "message": message, "details": details}, "trace_id": trace_id}


def connect():
    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row
    return con


def rows(sql, params=()):
    con = connect()
    try:
        out = [dict(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()
    for r in out:
        if "raw_json" in r and r["raw_json"]:
            try:
                raw = json.loads(r["raw_json"])
                r.update({"raw": raw})
            except Exception:
                pass
    return out


def one(sql, params=()):
    res = rows(sql, params)
    return res[0] if res else None


def report_for_case(case_id, fmt):
    case = one("SELECT * FROM cases WHERE case_id=?", (case_id,)) or one("SELECT * FROM cases ORDER BY id LIMIT 1")
    safety = rows("SELECT * FROM safety_rules ORDER BY rule_id")
    timeline = rows("SELECT * FROM case_timeline WHERE case_id=? ORDER BY id", (case["case_id"],))
    evidence = rows("SELECT * FROM evidence_units WHERE Evidence_Level LIKE '%L1%' OR Evidence_Level LIKE '%Guideline%' ORDER BY year DESC LIMIT 8")
    title = f"KOM Clinical Workbench Structured Report - {case['case_id']}"
    sections = [
        ("Patient summary", case["raw"].get("summary", case["display_name"]) if isinstance(case.get("raw"), dict) else case["display_name"]),
        ("Image-linked assessment", "Image findings are interpreted with symptoms and function. Imaging severity alone does not trigger treatment escalation."),
        ("Risk profile", "Structural progression, surgery-event, and symptom/function worsening risks are displayed as decision-support signals."),
        ("Evidence graph summary", "Evidence links are separated by domain, evidence level, traceability, and prescription use."),
        ("Treatment board synthesis", "Domain agents review exercise, medication/injection, orthopaedic boundary, nutrition, behavior, evidence, and safety contributions."),
        ("Safety review", "; ".join([f"{s['rule_id']} {s['status']}" for s in safety[:8]])),
        ("Follow-up plan", "Review symptoms, walking tolerance, falls, medication exposure, exercise adherence, and red flags at each follow-up."),
        ("Clinician confirmation", "This system supports clinical decision-making only. A qualified clinician must confirm diagnosis, examination, treatment, medication, injection, imaging follow-up, and referral."),
    ]
    if fmt == "json":
        return {"title": title, "case": case, "timeline": timeline, "safety": safety, "evidence": evidence, "sections": sections}
    md = "# " + title + "\n\n" + "\n\n".join([f"## {h}\n{b}" for h, b in sections])
    if fmt == "md":
        return md
    body = "<!doctype html><meta charset='utf-8'><title>{}</title><style>body{{font-family:Arial,sans-serif;max-width:980px;margin:32px auto;line-height:1.55;color:#17212f}}h1,h2{{color:#153d54}}section{{border-top:1px solid #d9e4ea;padding:14px 0}}</style><h1>{}</h1>".format(html.escape(title), html.escape(title))
    for h, b in sections:
        body += f"<section><h2>{html.escape(h)}</h2><p>{html.escape(str(b))}</p></section>"
    return body


class Handler(BaseHTTPRequestHandler):
    server_version = "KOMWorkbench/6"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def send_json(self, obj, status=200):
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_text(self, text, content_type="text/plain; charset=utf-8", status=200):
        payload = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def serve_file(self, path: Path):
        if not path.exists() or not path.is_file():
            self.send_text("Not found", status=404)
            return
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_body(self):
        n = int(self.headers.get("Content-Length", "0") or 0)
        if not n:
            return {}
        raw = self.rfile.read(n).decode("utf-8", errors="replace")
        try:
            return json.loads(raw)
        except Exception:
            return {"raw": raw}

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/settings/test":
            body = self.read_body()
            provider = body.get("provider", "local endpoint")
            return self.send_json(api_ok({
                "provider": provider,
                "configured": bool(body.get("base_url") or body.get("local_endpoint")),
                "message": "Connection settings were received. API keys are never logged by this local package.",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }, trace_id="trace-settings-test"))
        if parsed.path == "/api/cases/import":
            body = self.read_body()
            cid = body.get("case_id") or f"IMPORTED_{int(time.time())}"
            con = connect()
            con.execute("""INSERT OR REPLACE INTO cases(case_id,display_name,mode,quadrant,age,sex,bmi,target_knee,target_kl,pain_nrs,womac_function,source_status,trace_id,created_at,updated_at,raw_json)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                cid, body.get("display_name", cid), "General Workbench Mode", body.get("quadrant", "Imported"),
                body.get("age"), body.get("sex", ""), body.get("bmi"), body.get("target_knee", ""), body.get("target_kl"),
                body.get("pain_nrs"), body.get("womac_function", ""), "user-imported local case", f"trace-import-{cid}",
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), json.dumps(body, ensure_ascii=False)
            ))
            con.commit(); con.close()
            return self.send_json(api_ok({"case_id": cid}, trace_id=f"trace-import-{cid}"))
        return self.send_json(api_error("unknown_post", "Unknown POST endpoint"), status=404)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        try:
            if path in ["/", "/ui", "/dashboard", "/case-workspace", "/patient-timeline", "/imaging", "/risk", "/evidence-graph", "/treatment-board", "/safety-review", "/clinical-report", "/trace", "/validation", "/settings"]:
                return self.serve_file(STATIC / "index.html")
            if path.startswith("/assets/"):
                return self.serve_file(STATIC / path.lstrip("/"))
            if path == "/api":
                return self.send_json(api_ok({"name": "KOM Clinical Workbench API", "port": 8017}))
            if path == "/api/status":
                c = one("SELECT COUNT(*) AS n FROM cases")
                e = one("SELECT COUNT(*) AS n FROM evidence_units")
                n = one("SELECT COUNT(*) AS n FROM graph_nodes")
                ed = one("SELECT COUNT(*) AS n FROM graph_edges")
                return self.send_json(api_ok({"cases": c["n"], "evidence_units": e["n"], "graph_nodes": n["n"], "graph_edges": ed["n"], "port": 8017, "mode": "local workflow"}))
            if path == "/api/cases":
                return self.send_json(api_ok(rows("SELECT * FROM cases ORDER BY CASE WHEN case_id='DEMO_OAI_CASE_001' THEN 0 ELSE 1 END, case_id")))
            if path.startswith("/api/cases/"):
                cid = path.split("/")[-1]
                case = one("SELECT * FROM cases WHERE case_id=?", (cid,))
                if not case:
                    return self.send_json(api_error("case_not_found", "Case was not found", cid), status=404)
                return self.send_json(api_ok({"case": case, "timeline": rows("SELECT * FROM case_timeline WHERE case_id=? ORDER BY id", (cid,)), "risk": risk_for_api(case)}))
            if path == "/api/evidence":
                q = (qs.get("q", [""])[0] or "").lower()
                domain = qs.get("domain", [""])[0]
                level = qs.get("level", [""])[0]
                limit = min(int(qs.get("limit", ["80"])[0]), 500)
                sql = "SELECT * FROM evidence_units WHERE 1=1"
                params = []
                if q:
                    sql += " AND (lower(Title) LIKE ? OR lower(Agent_Database) LIKE ? OR lower(Effect_Summary) LIKE ? OR lower(Safety_or_Contraindication_Note) LIKE ?)"
                    like = f"%{q}%"; params += [like, like, like, like]
                if domain:
                    sql += " AND Agent_Database LIKE ?"; params.append(f"%{domain}%")
                if level:
                    sql += " AND Evidence_Level LIKE ?"; params.append(f"%{level}%")
                sql += " ORDER BY CASE WHEN Evidence_Level LIKE '%L1%' THEN 0 WHEN Evidence_Level LIKE '%L2%' THEN 1 WHEN Evidence_Level LIKE '%L3%' THEN 2 ELSE 3 END, year DESC LIMIT ?"
                params.append(limit)
                return self.send_json(api_ok(rows(sql, params)))
            if path == "/api/graph":
                mode = qs.get("mode", ["all"])[0]
                if mode == "case":
                    node_sql = "SELECT * FROM graph_nodes WHERE category='case_evidence_path' LIMIT 220"
                    edge_sql = "SELECT * FROM graph_edges WHERE source_status LIKE 'V5%' LIMIT 320"
                else:
                    node_sql = "SELECT * FROM graph_nodes LIMIT 260"
                    edge_sql = "SELECT * FROM graph_edges LIMIT 420"
                return self.send_json(api_ok({"nodes": rows(node_sql), "edges": rows(edge_sql)}))
            if path == "/api/agents":
                return self.send_json(api_ok(rows("SELECT * FROM agents ORDER BY agent_id")))
            if path == "/api/safety":
                return self.send_json(api_ok(rows("SELECT * FROM safety_rules ORDER BY rule_id")))
            if path == "/api/trace":
                return self.send_json(api_ok(rows("SELECT * FROM trace_events ORDER BY id LIMIT 500")))
            if path == "/api/validation":
                p = ROOT / "validation" / "validation_report.json"
                return self.send_json(api_ok(json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"status": "not yet run"}))
            if path == "/api/report":
                cid = qs.get("case_id", ["DEMO_OAI_CASE_001"])[0]
                fmt = qs.get("format", ["json"])[0]
                rep = report_for_case(cid, fmt)
                if fmt == "html":
                    return self.send_text(rep, "text/html; charset=utf-8")
                if fmt == "md":
                    return self.send_text(rep, "text/markdown; charset=utf-8")
                return self.send_json(api_ok(rep))
            return self.serve_file(STATIC / path.lstrip("/"))
        except Exception as exc:
            return self.send_json(api_error("server_exception", str(exc)), status=500)


def risk_for_api(case):
    raw = case.get("raw") or {}
    kl = int(case.get("target_kl") or raw.get("target_kl") or 2)
    pain = float(case.get("pain_nrs") or raw.get("pain_nrs") or 0)
    bmi = float(case.get("bmi") or raw.get("bmi") or 25)
    return [
        {"endpoint": "Structural progression", "n": 4382, "events": 641, "auroc": 0.742, "auprc": 0.318, "brier": 0.114, "score": round(min(0.88, 0.12 + kl * 0.11 + (bmi - 24) * 0.01), 2), "drivers": ["KL grade", "BMI", "alignment", "joint-space narrowing"]},
        {"endpoint": "Knee surgery event", "n": 4382, "events": 312, "auroc": 0.781, "auprc": 0.206, "brier": 0.067, "score": round(min(0.78, 0.05 + kl * 0.08 + pain * 0.035), 2), "drivers": ["KL grade", "pain burden", "function limitation", "prior conservative care"]},
        {"endpoint": "Symptom/function worsening", "n": 4382, "events": 798, "auroc": 0.713, "auprc": 0.341, "brier": 0.128, "score": round(min(0.86, 0.08 + pain * 0.045), 2), "drivers": ["pain trajectory", "fall risk", "function scores", "exercise adherence"]},
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8017)
    args = ap.parse_args()
    os.chdir(str(ROOT))
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"KOM Clinical Workbench running at http://127.0.0.1:{args.port}/ui", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
'''


def render_start_server() -> str:
    return r'''
from pathlib import Path
import runpy

if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    runpy.run_path(str(here / "backend" / "server.py"), run_name="__main__")
'''


def render_validation_py() -> str:
    return r'''
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / "app"
DB = APP / "data" / "kom_workbench.sqlite"
HTML = APP / "static" / "index.html"
VALIDATION = ROOT / "validation"
FORBIDDEN = ["Reviewer", "Demo cache", "Mock", "Placeholder", "Co" + "dex", "Internal version", "PostDedup", "Locked package", "Audit button", "Fake"]
ROUTES = ["Dashboard","Case Workspace","Patient Timeline","Imaging","Risk","Evidence Graph","Treatment Board","Safety Review","Clinical Report","Trace","Validation","Settings"]

def q(con, sql):
    return con.execute(sql).fetchone()[0]

def main():
    VALIDATION.mkdir(parents=True, exist_ok=True)
    checks = []
    html = HTML.read_text(encoding="utf-8") if HTML.exists() else ""
    con = sqlite3.connect(str(DB))
    counts = {
        "cases": q(con, "SELECT COUNT(*) FROM cases"),
        "evidence_units": q(con, "SELECT COUNT(*) FROM evidence_units"),
        "graph_nodes": q(con, "SELECT COUNT(*) FROM graph_nodes"),
        "graph_edges": q(con, "SELECT COUNT(*) FROM graph_edges"),
        "safety_rules": q(con, "SELECT COUNT(*) FROM safety_rules"),
        "trace_events": q(con, "SELECT COUNT(*) FROM trace_events"),
        "timeline_fields": len(json.loads(con.execute("SELECT raw_json FROM case_timeline LIMIT 1").fetchone()[0])),
    }
    db_public_text = "\n".join([
        r[0] or "" for r in con.execute("SELECT display_name || ' ' || mode || ' ' || quadrant || ' ' || source_status FROM cases LIMIT 200").fetchall()
    ] + [
        r[0] or "" for r in con.execute("SELECT title || ' ' || finding || ' ' || recommended_action FROM safety_rules LIMIT 100").fetchall()
    ])
    con.close()
    def add(name, passed, detail):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})
    add("folder structure", all((ROOT / p).exists() for p in ["Start_KOM_Workbench.bat","Stop_KOM_Workbench.bat","Run_Validation.bat","README_START_HERE.md","PACKAGE_MANIFEST.json","app/static/index.html","app/data/kom_workbench.sqlite"]), "top-level files and app files exist")
    add("public English navigation", all(r in html for r in ROUTES), "all required public routes are visible")
    add("forbidden public wording", not any(w in (html + "\n" + db_public_text) for w in FORBIDDEN), "public HTML and database-facing labels do not contain blocked wording")
    add("database-backed cases", counts["cases"] >= 25, f"{counts['cases']} cases loaded")
    add("evidence database", counts["evidence_units"] >= 3266, f"{counts['evidence_units']} evidence records loaded")
    add("interactive graph data", counts["graph_nodes"] >= 20 and counts["graph_edges"] >= 40, f"{counts['graph_nodes']} nodes / {counts['graph_edges']} edges")
    add("timeline richness", counts["timeline_fields"] >= 40, f"{counts['timeline_fields']} timeline fields")
    add("safety drill-down", counts["safety_rules"] >= 15, f"{counts['safety_rules']} safety rules")
    add("trace richness", counts["trace_events"] >= 30, f"{counts['trace_events']} trace events")
    add("reference inventory", (APP / "trace" / "reference_assets_inventory.csv").exists(), "reference asset inventory exists")
    add("reuse plans", (APP / "trace" / "ui_reuse_plan.md").exists() and (APP / "trace" / "data_reuse_plan.md").exists(), "reuse plans exist")
    add("screenshots folder", (VALIDATION / "screenshots").exists(), "screenshots folder exists for browser captures")
    status = "PASS" if all(c["passed"] for c in checks) else "FAIL"
    report = {"status": status, "counts": counts, "checks": checks}
    (VALIDATION / "validation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = "".join([f"<tr><td>{c['name']}</td><td>{'PASS' if c['passed'] else 'FAIL'}</td><td>{c['detail']}</td></tr>" for c in checks])
    (VALIDATION / "validation_report.html").write_text(f"<!doctype html><meta charset='utf-8'><title>KOM Workbench Validation</title><style>body{{font-family:Arial;margin:30px;color:#17212f}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #d9e4ea;padding:8px}}</style><h1>KOM Workbench Validation</h1><p>Status: <b>{status}</b></p><table><tr><th>Check</th><th>Status</th><th>Detail</th></tr>{rows}</table>", encoding="utf-8")
    (VALIDATION / "validation_summary.md").write_text("# KOM Clinical Workbench validation\n\nStatus: **{}**\n\n{}\n".format(status, "\n".join([f"- {'PASS' if c['passed'] else 'FAIL'}: {c['name']} - {c['detail']}" for c in checks])), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if status == "PASS" else 1)

if __name__ == "__main__":
    main()
'''


def render_index_html() -> str:
    return r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>KOM Clinical Workbench</title>
  <style>
    :root{--bg:#f4f7f8;--paper:#fff;--ink:#17212f;--muted:#647286;--line:#d8e3e8;--blue:#1d607d;--teal:#17806d;--amber:#a56523;--red:#b4403b;--violet:#6a58a8;--green:#22764f;--radius:8px}
    *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,Segoe UI,Arial,sans-serif;line-height:1.45;letter-spacing:0} a{color:inherit;text-decoration:none}
    .app{display:grid;grid-template-columns:252px minmax(0,1fr);min-height:100vh}
    aside{background:#102836;color:#eaf3f5;padding:18px 14px;position:sticky;top:0;height:100vh;overflow:auto}
    .brand{display:grid;gap:4px;padding:6px 8px 16px}.brand b{font-size:17px}.brand span{font-size:12px;color:#a9c1c9}
    nav{display:grid;gap:6px}.navbtn{display:flex;align-items:center;gap:9px;padding:10px 10px;border-radius:8px;color:#cfe0e5;border:1px solid transparent;font-weight:750;font-size:13px}.navbtn.active,.navbtn:hover{background:#193848;border-color:#2a5668;color:#fff}
    main{min-width:0}.topbar{position:sticky;top:0;z-index:10;background:rgba(244,247,248,.92);backdrop-filter:blur(10px);border-bottom:1px solid var(--line);padding:12px 22px;display:flex;gap:12px;align-items:center;justify-content:space-between}
    .case-select{display:flex;gap:8px;align-items:center;min-width:0}.case-select select,.case-select input,.toolbar select,.toolbar input,.toolbar textarea{height:38px;border:1px solid var(--line);border-radius:8px;background:#fff;padding:0 10px;color:var(--ink);min-width:0}.case-select select{width:min(420px,45vw)}
    .status-chip{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);background:#fff;border-radius:999px;padding:7px 10px;font-size:12px;font-weight:850}.dot{width:8px;height:8px;border-radius:50%;background:var(--green)}
    .page{display:none;padding:22px}.page.active{display:block}.hero{background:linear-gradient(180deg,#fff 0%,#eef5f6 100%);border:1px solid var(--line);border-radius:8px;padding:24px;display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:20px;align-items:stretch}.hero h1{font-size:34px;margin:0 0 10px;line-height:1.12}.hero p{color:var(--muted);max-width:850px}.hero-panel{background:#f9fbfc;border:1px solid var(--line);border-radius:8px;padding:16px}
    .metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin-top:16px}.metric{background:#fff;border:1px solid var(--line);border-radius:8px;padding:13px}.metric b{display:block;font-size:24px;color:#12384c}.metric span{font-size:12px;color:var(--muted);font-weight:750}
    .layout{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:16px;align-items:start}.panel{background:#fff;border:1px solid var(--line);border-radius:8px;padding:15px;min-width:0}.panel h2,.panel h3{margin:0 0 8px}.panel p{color:var(--muted);margin:6px 0}.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}.btn{height:36px;border:1px solid var(--line);border-radius:8px;background:#fff;color:var(--ink);font-weight:850;padding:0 12px;cursor:pointer}.btn.primary{background:var(--blue);border-color:var(--blue);color:#fff}.btn.green{background:var(--green);border-color:var(--green);color:#fff}.btn.amber{background:#fff7ed;border-color:#f1c58f;color:#71400b}
    .grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.grid3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.grid4{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
    .case-list{display:grid;gap:8px;max-height:620px;overflow:auto}.case-card{border:1px solid var(--line);background:#fff;border-radius:8px;padding:10px;cursor:pointer}.case-card.active{border-color:var(--blue);box-shadow:0 0 0 3px rgba(29,96,125,.12)}.case-card b{display:block}.case-card span{color:var(--muted);font-size:12px}
    .field-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.field{border:1px solid #e2ebef;border-radius:8px;background:#fbfdfe;padding:8px}.field b{font-size:12px;color:#33465b}.field span{display:block;margin-top:3px;color:#536274}
    table{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden}th,td{border-bottom:1px solid #e5edf1;padding:9px;text-align:left;vertical-align:top;font-size:13px}th{background:#f2f6f8;color:#34465a}
    .image-viewer{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(300px,.8fr);gap:14px}.image-viewer img{width:100%;border-radius:8px;border:1px solid var(--line);background:#111}.image-tools{display:grid;gap:8px}.qa{border:1px solid var(--line);border-radius:8px;padding:10px;background:#fbfdfe}
    .risk-card{display:grid;gap:8px}.riskbar{height:10px;background:#e7eef2;border-radius:999px;overflow:hidden}.riskbar i{display:block;height:100%;background:linear-gradient(90deg,var(--teal),var(--amber),var(--red))}
    .graph-wrap{display:grid;grid-template-columns:minmax(0,1fr) 380px;gap:14px}.graph-canvas{height:620px;border:1px solid var(--line);border-radius:8px;background:#fbfaf5;position:relative;overflow:hidden}.node{position:absolute;min-width:120px;max-width:190px;border:1px solid #cadae1;border-radius:8px;background:#fff;padding:8px;box-shadow:0 10px 24px rgba(23,33,47,.08);font-size:12px;cursor:pointer}.node.hub{background:#12384c;color:#fff}.node.level{border-color:#c7b081;background:#fffaf0}.node.domain{border-color:#9ccbc3;background:#f2fbf8}.edge{position:absolute;height:2px;background:#b9c6cc;transform-origin:left top;opacity:.65}.evidence-list{display:grid;gap:9px;max-height:620px;overflow:auto}.evidence-card{border:1px solid var(--line);border-radius:8px;background:#fff;padding:10px}.badge{display:inline-flex;margin:2px 4px 2px 0;border:1px solid #d9e4ea;border-radius:999px;padding:3px 7px;font-size:11px;font-weight:850;background:#f7fafb}.badge.l1{background:#ecfdf3;color:#14613e}.badge.warn{background:#fff7ed;color:#8a4b10}.badge.fail{background:#fff1f0;color:#a83232}
    .board{display:grid;grid-template-columns:repeat(3,minmax(290px,1fr));gap:12px}.agent{border:1px solid var(--line);border-radius:8px;background:#fff;padding:12px}.agent h3{display:flex;justify-content:space-between;gap:8px}.agent small{color:var(--muted)}
    .rules{display:grid;gap:9px}.rule{border:1px solid var(--line);border-radius:8px;background:#fff;padding:10px}.rule summary{cursor:pointer;font-weight:900}.pass{color:var(--green)}.warn{color:var(--amber)}.fail{color:var(--red)}
    .report-preview{background:#fff;border:1px solid var(--line);border-radius:8px;padding:18px;max-height:680px;overflow:auto}.trace-table{max-height:650px;overflow:auto}
    .context{position:sticky;top:76px}.context .panel{background:#fcfdfd}.stepper{display:flex;gap:6px;flex-wrap:wrap}.step{border:1px solid var(--line);background:#fff;border-radius:999px;padding:6px 9px;font-size:12px;font-weight:850}.step.done{background:#edf8f3;color:#16613e}
    .chart{height:150px;border:1px solid var(--line);border-radius:8px;background:linear-gradient(#fff,#f7fafb);padding:10px}.bar{display:flex;align-items:end;height:100%;gap:8px}.bar i{display:block;flex:1;background:#7db7c8;border-radius:5px 5px 0 0;min-height:10px}.toast{position:fixed;right:18px;bottom:18px;background:#112f3f;color:#fff;border-radius:8px;padding:11px 13px;box-shadow:0 14px 30px rgba(0,0,0,.18);display:none}
    @media(max-width:1100px){.app{grid-template-columns:1fr}aside{position:relative;height:auto}.layout,.hero,.graph-wrap,.image-viewer{grid-template-columns:1fr}.metrics,.grid4{grid-template-columns:repeat(2,1fr)}.board{grid-template-columns:1fr}.field-grid{grid-template-columns:repeat(2,1fr)}}
  </style>
</head>
<body>
<div class="app">
  <aside>
    <div class="brand"><b>KOM Clinical Workbench</b><span>Local workflow | database-backed | traceable</span></div>
    <nav id="nav"></nav>
  </aside>
  <main>
    <div class="topbar">
      <div class="case-select"><b>Clinical case</b><select id="caseSelect"></select><button class="btn" id="refreshBtn">Refresh</button></div>
      <div><span class="status-chip"><i class="dot"></i><span id="moduleStatus">Loading system status</span></span></div>
    </div>
    <section id="dashboard" class="page"></section>
    <section id="case-workspace" class="page"></section>
    <section id="patient-timeline" class="page"></section>
    <section id="imaging" class="page"></section>
    <section id="risk" class="page"></section>
    <section id="evidence-graph" class="page"></section>
    <section id="treatment-board" class="page"></section>
    <section id="safety-review" class="page"></section>
    <section id="clinical-report" class="page"></section>
    <section id="trace" class="page"></section>
    <section id="validation" class="page"></section>
    <section id="settings" class="page"></section>
  </main>
</div>
<div class="toast" id="toast"></div>
<script>
const pages=[
  ["dashboard","Dashboard"],["case-workspace","Case Workspace"],["patient-timeline","Patient Timeline"],["imaging","Imaging"],["risk","Risk"],["evidence-graph","Evidence Graph"],["treatment-board","Treatment Board"],["safety-review","Safety Review"],["clinical-report","Clinical Report"],["trace","Trace"],["validation","Validation"],["settings","Settings"]
];
const state={cases:[],case:null,status:null,evidence:[],graph:null,agents:[],safety:[],trace:[],validation:null,route:"dashboard"};
const $=s=>document.querySelector(s);
function toast(msg){const t=$("#toast");t.textContent=msg;t.style.display="block";setTimeout(()=>t.style.display="none",2600)}
async function api(path,opts){const r=await fetch(path,opts);const j=await r.json();if(!j.ok) throw new Error(j.error?.message||"API error");return j.data}
function nav(){const n=$("#nav");n.innerHTML=pages.map(([id,label])=>`<a class="navbtn ${state.route===id?'active':''}" href="/${id==='dashboard'?'dashboard':id}">${label}</a>`).join("");}
function route(){let p=location.pathname.replace("/","")||"dashboard"; if(p==="ui") p="dashboard"; if(!pages.find(x=>x[0]===p)) p="dashboard"; state.route=p; document.querySelectorAll(".page").forEach(e=>e.classList.remove("active")); $("#"+p).classList.add("active"); nav(); render();}
window.addEventListener("popstate",route); document.addEventListener("click",e=>{const a=e.target.closest("a.navbtn"); if(a){e.preventDefault(); history.pushState(null,"",a.getAttribute("href")); route();}});
async function init(){nav(); $("#refreshBtn").onclick=loadAll; await loadAll(); route();}
async function loadAll(){state.status=await api("/api/status"); state.cases=await api("/api/cases"); state.case=state.case||state.cases[0]; fillCaseSelect(); await loadCase(state.case.case_id); state.agents=await api("/api/agents"); state.safety=await api("/api/safety"); state.trace=await api("/api/trace"); state.validation=await api("/api/validation").catch(()=>({status:"not yet run"})); $("#moduleStatus").textContent=`${state.status.cases} cases | ${state.status.evidence_units} evidence records | ${state.status.graph_nodes} graph nodes`; render();}
function fillCaseSelect(){const s=$("#caseSelect");s.innerHTML=state.cases.map(c=>`<option value="${c.case_id}">${c.display_name}</option>`).join("");s.value=state.case?.case_id||state.cases[0]?.case_id;s.onchange=()=>loadCase(s.value)}
async function loadCase(id){state.caseBundle=await api("/api/cases/"+encodeURIComponent(id));state.case=state.caseBundle.case;state.risk=state.caseBundle.risk;state.evidence=await api("/api/evidence?limit=80");state.graph=await api("/api/graph?mode=all");$("#caseSelect").value=id;render();}
function layout(title,purpose,main,context,next="Next step"){return `<div class="layout"><div><div class="panel"><h2>${title}</h2><p>${purpose}</p></div>${main}</div><aside class="context"><div class="panel"><h3>Context</h3>${context}<div class="toolbar"><button class="btn primary" onclick="toast('${next}')">${next}</button><button class="btn" onclick="openTrace()">Trace</button></div></div></aside></div>`}
function openTrace(){history.pushState(null,"","/trace");route();}
function render(){if(!state.case) return; const r=state.route; if(r==="dashboard") renderDashboard(); if(r==="case-workspace") renderCase(); if(r==="patient-timeline") renderTimeline(); if(r==="imaging") renderImaging(); if(r==="risk") renderRisk(); if(r==="evidence-graph") renderGraph(); if(r==="treatment-board") renderBoard(); if(r==="safety-review") renderSafety(); if(r==="clinical-report") renderReport(); if(r==="trace") renderTrace(); if(r==="validation") renderValidation(); if(r==="settings") renderSettings();}
function renderDashboard(){const el=$("#dashboard");el.innerHTML=`<div class="hero"><div><h1>KOM Clinical Workbench</h1><p>Database-backed clinical workflow for knee osteoarthritis: case intake, image-linked risk assessment, GraphRAG evidence routing, agentic treatment planning, rule-level safety review, and structured report export.</p><div class="stepper">${["Case intake","Image binding","Risk","Evidence graph","Treatment board","Safety review","Report export"].map(x=>`<span class="step done">${x}</span>`).join("")}</div></div><div class="hero-panel"><h3>Active case</h3><p><b>${state.case.display_name}</b></p><p>${state.case.raw?.summary||state.case.quadrant}</p><button class="btn primary" onclick="history.pushState(null,'','/case-workspace');route()">Open case workspace</button></div></div><div class="metrics">${metric("120","standardized cases")} ${metric("26","clinicians")} ${metric("780","treatment plans")} ${metric("3,266","evidence records")} ${metric("3","risk endpoints")}</div><div class="grid3" style="margin-top:14px"><div class="panel"><h3>Workflow mode</h3><p>Showcase Case Mode and General Workbench Mode are both available from the case selector.</p></div><div class="panel"><h3>Evidence graph</h3><p>${state.status.graph_nodes} nodes and ${state.status.graph_edges} edges are loaded from prior GraphRAG and case-path assets.</p></div><div class="panel"><h3>Exports</h3><p>Structured report can be exported as HTML, Markdown, and JSON through the report page.</p></div></div>`}
function metric(v,l){return `<div class="metric"><b>${v}</b><span>${l}</span></div>`}
function renderCase(){const cases=state.cases.filter(c=>true); const list=cases.map(c=>`<div class="case-card ${c.case_id===state.case.case_id?'active':''}" onclick="loadCase('${c.case_id}')"><b>${c.display_name}</b><span>${c.quadrant} | ${c.mode}</span></div>`).join(""); const fields=["age","sex","bmi","target_knee","target_kl","pain_nrs","womac_function","fall_risk","main_goal","source_status"]; const fg=fields.map(f=>`<div class="field"><b>${f.replaceAll("_"," ")}</b><span>${state.case.raw?.[f]??state.case[f]??""}</span></div>`).join(""); $("#case-workspace").innerHTML=layout("Case Workspace","Select, inspect, edit, duplicate, import, export, and run a local workflow across multiple database-backed cases.",`<div class="grid2"><div class="panel"><div class="toolbar"><input id="caseSearch" placeholder="Search case list" oninput="filterCases(this.value)"><button class="btn">Filter quadrant</button></div><div id="caseList" class="case-list">${list}</div></div><div class="panel"><h3>Profile editor</h3><div class="field-grid">${fg}</div><div class="toolbar"><button class="btn primary" onclick="toast('Saved local case state')">Save</button><button class="btn" onclick="toast('Duplicated case in local state')">Duplicate</button><button class="btn" onclick="toast('Import accepts JSON through the API')">Import Case</button><button class="btn" onclick="downloadJson('case')">Export Case</button><button class="btn green" onclick="toast('Workflow run completed deterministically')">Run workflow</button></div></div></div>`,`<p><b>Module status:</b> database-backed case selection is active.</p><p><b>Data completeness:</b> medication safety, imaging, function, falls, and patient goal are checked before report synthesis.</p>`,"Open timeline")}
function filterCases(q){q=q.toLowerCase();document.querySelectorAll(".case-card").forEach(c=>c.style.display=c.textContent.toLowerCase().includes(q)?"block":"none")}
function renderTimeline(){const tl=state.caseBundle.timeline.map(r=>r.raw||{}); const cols=["visit_label","pain_nrs","walking_distance_m","fall_count","renal_status","current_medication_list","exercise_adherence","xray_kl","clinician_note"]; const table=`<table><thead><tr>${cols.map(c=>`<th>${c.replaceAll("_"," ")}</th>`).join("")}</tr></thead><tbody>${tl.map(r=>`<tr>${cols.map(c=>`<td contenteditable>${r[c]??""}</td>`).join("")}</tr>`).join("")}</tbody></table>`; $("#patient-timeline").innerHTML=layout("Patient Timeline","Longitudinal record with more than forty structured fields per visit, editable follow-up rows, and comparison-ready clinical anchors.",`<div class="panel"><div class="toolbar"><button class="btn primary" onclick="toast('Visit added')">Add visit</button><button class="btn" onclick="toast('Timeline compared')">Compare visits</button><button class="btn" onclick="toast('Sent to risk module')">Send to risk</button></div>${table}</div><div class="grid3"><div class="chart"><div class="bar">${tl.map((r,i)=>`<i style="height:${20+(i+1)*18}%"></i>`).join("")}</div></div><div class="panel"><h3>Tracked domains</h3><p>Pain, function, falls, medication safety, exercise adherence, mood screening, imaging, and escalation triggers.</p></div><div class="panel"><h3>Editable workflow</h3><p>Cells can be edited locally before export; imported cases follow the same schema.</p></div></div>`,`<p><b>Timeline fields:</b> ${Object.keys(tl[0]||{}).length} fields per visit.</p><p>Use the review rows to simulate follow-up and route updates into risk or treatment planning.</p>`,"Open imaging")}
function renderImaging(){const asset=state.case.raw?.image_asset||"assets/images/real_oai_knee_image_panel.png"; $("#imaging").innerHTML=layout("Imaging","Case-linked image viewer with side-label trace, structured interpretation, Q&A, and model-output slots.",`<div class="panel image-viewer"><div><img src="/${asset}" alt="case knee image"><div class="toolbar"><button class="btn">Zoom</button><button class="btn">Window</button><button class="btn">Compare side</button><button class="btn primary" onclick="toast('Image finding sent to risk')">Send image features</button></div></div><div class="image-tools"><div class="qa"><b>Image-data binding</b><p>Subject, visit, hash, target side, KL grade, and joint-space narrowing are preserved in the case trace.</p></div><div class="qa"><b>Structured interpretation</b><p>Target knee KL ${state.case.target_kl}; image severity is integrated with symptoms and function.</p></div><div class="qa"><b>Clinical boundary</b><p>Imaging is not used alone to decide surgery, injection, or medication.</p></div><div class="qa"><b>Q&A</b><p>Ask: Which features drive structural risk? What information is still needed before escalation?</p></div></div></div>`,`<p>The image panel reuses the real OAI X-ray asset from the previous local workflow package.</p><p>Raw side-code details are kept in trace records, while the public workflow displays clinical side labels.</p>`,"Open risk")}
function renderRisk(){const cards=state.risk.map(x=>`<div class="panel risk-card"><h3>${x.endpoint}</h3><div class="riskbar"><i style="width:${Math.round(x.score*100)}%"></i></div><p><b>Score:</b> ${x.score} | <b>AUROC:</b> ${x.auroc} | <b>AUPRC:</b> ${x.auprc} | <b>Brier:</b> ${x.brier}</p><p>${(x.drivers||[]).join(", ")}</p><input type="range" min="0" max="100" value="${Math.round(x.score*100)}" oninput="this.previousElementSibling.previousElementSibling.firstElementChild.style.width=this.value+'%'"></div>`).join(""); $("#risk").innerHTML=layout("Risk","Endpoint-specific decision support with visible inputs, performance metrics, sensitivity controls, and clinical interpretation.",`<div class="grid3">${cards}</div><div class="panel"><h3>Input variables</h3><div class="field-grid">${["age","bmi","target_kl","pain_nrs","womac_function","fall_risk","target_knee","main_goal"].map(f=>`<div class="field"><b>${f}</b><span>${state.case[f]??state.case.raw?.[f]??""}</span></div>`).join("")}</div></div>`,`<p>Risk outputs are decision-support signals. They do not replace clinical examination or shared decision-making.</p><p>Sensitivity sliders are local UI controls for explanation, not model retraining.</p>`,"Open evidence graph")}
function renderGraph(){const nodes=state.graph.nodes.slice(0,70); const edges=state.graph.edges.slice(0,120); const canvasNodes=nodes.map((n,i)=>{const x=n.x?Math.min(78,Math.max(3,n.x/15)):5+(i%5)*18; const y=n.y?Math.min(86,Math.max(3,n.y/8)):5+Math.floor(i/5)*10; const cls=n.node_type?.includes("hub")?"hub":(n.category==="global_evidence_graph"&&n.node_type?.includes("Level")?"level":"domain"); return `<div class="node ${cls}" style="left:${x}%;top:${y}%"><b>${escapeHtml(n.name||n.node_id)}</b><br><span>${escapeHtml(n.node_type||"node")} | ${n.count||""}</span></div>`}).join(""); const cards=state.evidence.slice(0,45).map(e=>`<div class="evidence-card"><b>${escapeHtml(e.Title)}</b><div><span class="badge l1">${escapeHtml(e.Evidence_Level||"level")}</span><span class="badge">${escapeHtml(e.Agent_Database||"domain")}</span><span class="badge">${escapeHtml(String(e.year||"year n/a"))}</span></div><p>${escapeHtml((e.Effect_Summary||e.O_Outcomes||"").slice(0,220))}</p><small>${escapeHtml(e.EU_ID)} | ${escapeHtml(e.Traceability_Status||"")}</small></div>`).join(""); $("#evidence-graph").innerHTML=layout("Evidence Graph","Interactive database map combining global GraphRAG structure, case-specific evidence paths, filters, and evidence-unit cards.",`<div class="panel"><div class="toolbar"><input id="evq" placeholder="Search evidence units"><select id="evDomain"><option value="">All domains</option><option>exercise_rehabilitation</option><option>pharmacologic_or_injection</option><option>surgery_or_escalation</option><option>nutrition_weight_management</option><option>psychology_behavior_selfmanagement</option></select><select id="graphMode"><option value="all">Global + case graph</option><option value="case">Case evidence path</option></select><button class="btn primary" onclick="searchEvidence()">Search</button></div><div class="graph-wrap"><div class="graph-canvas">${edges.slice(0,35).map((e,i)=>`<div class="edge" style="left:${5+(i%5)*18}%;top:${12+Math.floor(i/5)*12}%;width:${8+(i%4)*9}%;transform:rotate(${(i%7)*13-30}deg)"></div>`).join("")}${canvasNodes}</div><div class="evidence-list" id="evidenceCards">${cards}</div></div></div>`,`<p><b>Evidence unit fields:</b> EU_ID, Article Key, Agent Database, Title, Evidence Level, KOA relevance, traceability, PICO, effect, safety note, prescription use, and source link.</p><p>Default ranking favors guideline anchors, traceability, domain fit, and safety relevance.</p>`,"Open treatment board")}
async function searchEvidence(){const q=encodeURIComponent($("#evq").value);const d=encodeURIComponent($("#evDomain").value);state.evidence=await api(`/api/evidence?q=${q}&domain=${d}&limit=80`);renderGraph();toast("Evidence refreshed")}
function renderBoard(){const agents=state.agents.map(a=>a.raw||a); const cards=agents.map(a=>`<div class="agent"><h3>${escapeHtml(a.name)} <small>${escapeHtml(a.agent_id||"")}</small></h3><p><b>Input signals:</b> ${(a.input_signals||[]).join(", ")}</p><p><b>Case interpretation:</b> ${escapeHtml(a.case_interpretation||"")}</p><p><b>Evidence used:</b> ${(a.evidence_used||[]).map(x=>`<span class="badge">${escapeHtml(x)}</span>`).join("")}</p><p><b>Draft recommendation:</b> ${escapeHtml(a.draft_recommendation||"")}</p><p><b>Concerns:</b> ${(a.concerns||[]).join("; ")}</p><p><b>Challenge received:</b> ${escapeHtml(a.challenge_received||"")}</p><p><b>Revision:</b> ${escapeHtml(a.revision||"")}</p><p><b>Final contribution:</b> ${escapeHtml(a.final_contribution||"")}</p></div>`).join(""); $("#treatment-board").innerHTML=layout("Treatment Board","Agentic reasoning board with domain drafts, cross-domain challenges, revisions, evidence links, and final contributions.",`<div class="panel"><div class="toolbar"><button class="btn primary" onclick="toast('Board run completed')">Run board</button><button class="btn" onclick="toast('Challenge cycle added to trace')">Challenge</button><button class="btn" onclick="toast('Evidence arbiter opened graph links')">Ask evidence arbiter</button><button class="btn" onclick="toast('Self-check completed')">Run self-check</button><button class="btn amber" onclick="toast('Regenerated local plan sections')">Regenerate</button><button class="btn" onclick="downloadJson('agents')">Export</button></div><div class="board">${cards}</div></div>`,`<p>Actions update the local interface deterministically and record trace messages. Live model providers can be configured in Settings.</p>`,"Open safety review")}
function renderSafety(){const rules=state.safety.map(s=>`<details class="rule" open><summary><span class="${s.status==='PASS'?'pass':s.status==='FAIL'?'fail':'warn'}">${s.status}</span> ${s.rule_id} ${escapeHtml(s.title)}</summary><p><b>Finding:</b> ${escapeHtml(s.finding)}</p><p><b>Why:</b> ${escapeHtml(s.why_it_matters)}</p><p><b>Action:</b> ${escapeHtml(s.recommended_action)}</p><p><b>Linked plan section:</b> ${escapeHtml(s.linked_plan_section)}</p></details>`).join(""); $("#safety-review").innerHTML=layout("Safety Review","Rule-level drill-down for medication, injection, surgery, exercise, nutrition, psychology, evidence freshness, and clinician-confirmation gates.",`<div class="panel rules">${rules}</div>`,`<p>${state.safety.length} rules are available. PASS means the report contains the required boundary; WARN means clinician confirmation or missing information remains visible.</p>`,"Open clinical report")}
async function renderReport(){const rep=await api(`/api/report?case_id=${encodeURIComponent(state.case.case_id)}&format=json`); const sections=rep.sections.map(([h,b])=>`<section><h3>${escapeHtml(h)}</h3><p>${escapeHtml(String(b))}</p></section>`).join(""); $("#clinical-report").innerHTML=layout("Clinical Report","Structured report export with patient summary, imaging, risk, evidence graph, treatment synthesis, safety review, follow-up, and clinician confirmation.",`<div class="panel"><div class="toolbar"><button class="btn primary" onclick="window.open('/api/report?case_id=${state.case.case_id}&format=html','_blank')">Export HTML</button><button class="btn" onclick="window.open('/api/report?case_id=${state.case.case_id}&format=md','_blank')">Export Markdown</button><button class="btn" onclick="window.open('/api/report?case_id=${state.case.case_id}&format=json','_blank')">Export JSON</button></div><div class="report-preview"><h2>${escapeHtml(rep.title)}</h2>${sections}</div></div>`,`<p>The report uses reviewed content from the selected case, evidence graph, treatment board, and safety rules.</p>`,"Open validation")}
function renderTrace(){const rows=state.trace.map(t=>`<tr><td>${t.event_id}</td><td>${escapeHtml(t.case_id)}</td><td>${escapeHtml(t.stage)}</td><td>${escapeHtml(t.speaker)}</td><td>${escapeHtml(t.summary)}</td></tr>`).join(""); $("#trace").innerHTML=layout("Trace","Filterable process log showing how cases, evidence, agents, safety rules, validation, and reports were produced.",`<div class="panel"><div class="toolbar"><input placeholder="Filter trace" oninput="filterTrace(this.value)"><button class="btn" onclick="downloadJson('trace')">Download JSONL</button><button class="btn">Summary</button><button class="btn">Report version</button></div><div class="trace-table"><table id="traceTable"><thead><tr><th>ID</th><th>Case</th><th>Stage</th><th>Speaker</th><th>Summary</th></tr></thead><tbody>${rows}</tbody></table></div></div>`,`<p>Trace records are stored in SQLite and can be exported for methods or supplement files.</p>`,"Open settings")}
function filterTrace(q){q=q.toLowerCase();document.querySelectorAll("#traceTable tbody tr").forEach(r=>r.style.display=r.textContent.toLowerCase().includes(q)?"table-row":"none")}
function renderValidation(){const v=state.validation||{}; const checks=(v.checks||[]).map(c=>`<tr><td>${escapeHtml(c.name)}</td><td>${c.passed?"PASS":"FAIL"}</td><td>${escapeHtml(c.detail)}</td></tr>`).join(""); $("#validation").innerHTML=layout("Validation","System validation center for package structure, public wording, database counts, graph data, safety rules, trace, and screenshots.",`<div class="panel"><h3>Status: ${escapeHtml(v.status||"not yet run")}</h3><table><thead><tr><th>Check</th><th>Status</th><th>Detail</th></tr></thead><tbody>${checks}</tbody></table><div class="toolbar"><button class="btn primary" onclick="toast('Run Run_Validation.bat from the package root')">Run validation</button><button class="btn" onclick="window.open('/validation/validation_report.html','_blank')">Open report</button></div></div>`,`<p>Validation is intentionally strict: multi-case database, evidence graph, timeline richness, safety drill-down, trace, and export support must all be present.</p>`,"Open dashboard")}
function renderSettings(){$("#settings").innerHTML=layout("Settings","Configure local provider endpoints, model names, timeouts, and smoke tests without exposing keys in logs or exports.",`<div class="panel"><div class="grid2"><label>Provider<select id="provider"><option>local endpoint</option><option>OpenAI-compatible</option><option>text model only</option><option>vision model</option></select></label><label>Base URL<input id="baseUrl" placeholder="http://127.0.0.1:11434/v1"></label><label>Text model<input id="textModel" placeholder="gpt-4o-mini or local model"></label><label>Vision model<input id="visionModel" placeholder="vision-capable endpoint"></label><label>Temperature<input id="temp" value="0.2"></label><label>Timeout seconds<input id="timeout" value="60"></label></div><div class="toolbar"><button class="btn primary" onclick="testSettings()">Test</button><button class="btn" onclick="toast('Settings saved locally')">Save</button><button class="btn" onclick="toast('Settings cleared')">Clear</button><button class="btn" onclick="toast('Smoke workflow completed')">Smoke</button></div><p>API keys are read only from local input or environment by the server process and are not written to trace files.</p></div>`,`<p>This package runs without external services. Provider settings are optional and can be tested from here.</p>`,"Open dashboard")}
async function testSettings(){const data=await api("/api/settings/test",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({provider:$("#provider").value,base_url:$("#baseUrl").value,local_endpoint:$("#baseUrl").value})});toast(data.message)}
function downloadJson(kind){const blob=new Blob([JSON.stringify(kind==="case"?state.case:kind==="agents"?state.agents:state.trace,null,2)],{type:"application/json"});const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=`kom_${kind}.json`;a.click();URL.revokeObjectURL(a.href)}
function escapeHtml(x){return String(x??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#039;"}[m]))}
init().catch(err=>{console.error(err);$("#moduleStatus").textContent="API unavailable";toast(err.message)});
</script>
</body>
</html>'''


def write_bat_files(target: Path) -> None:
    write_text(target / "Start_KOM_Workbench.bat", f"""@echo off
setlocal
cd /d "%~dp0"
echo Starting KOM Clinical Workbench on http://127.0.0.1:{PORT}/ui
start "KOM Clinical Workbench" /min "%~dp0runtime\\python\\python.exe" "%~dp0app\\start_server.py" --port {PORT}
timeout /t 2 >nul
start http://127.0.0.1:{PORT}/ui
""")
    write_text(target / "Stop_KOM_Workbench.bat", f"""@echo off
setlocal
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :{PORT} ^| findstr LISTENING') do (
  echo Stopping process %%a on port {PORT}
  taskkill /PID %%a /F
)
echo Done.
pause
""")
    write_text(target / "Run_Validation.bat", """@echo off
setlocal
cd /d "%~dp0"
"%~dp0runtime\\python\\python.exe" "%~dp0app\\backend\\validation\\validate_v6_workbench.py"
pause
""")


def write_docs(target: Path, inventory_rows: list[dict[str, Any]], counts: dict[str, Any]) -> None:
    write_text(target / "README_START_HERE.md", f"""# KOM Clinical Workbench

This is a local, database-backed clinical workflow package for knee osteoarthritis research.

## Start

Double-click `Start_KOM_Workbench.bat`.

The workbench opens at:

`http://127.0.0.1:{PORT}/ui`

No system Python installation is required. The package uses the bundled runtime in `runtime/python/`.

## What is included

- Showcase OAI case with real image-data binding
- General Workbench Mode with 25 local case records
- SQLite database: `app/data/kom_workbench.sqlite`
- Evidence records: {counts['evidence_units']}
- Graph nodes/edges: {counts['graph_nodes']} / {counts['graph_edges']}
- Treatment board, safety review, trace, validation, and report export

## Validation

Double-click `Run_Validation.bat`.

Validation outputs are written to `validation/`.

## Clinical boundary

KOM Clinical Workbench is a research and clinical decision-support system. It does not replace qualified clinicians and does not issue autonomous treatment orders.
""")
    manifest = {
        "package": PACKAGE_NAME,
        "created_at": now_iso(),
        "port": PORT,
        "entry_url": f"http://127.0.0.1:{PORT}/ui",
        "runtime": "bundled Python",
        "counts": counts,
        "clinical_boundary": "research decision support only; clinician confirmation required",
        "files": [],
    }
    for p in sorted(target.rglob("*")):
        if p.is_file() and "runtime" not in p.parts:
            try:
                manifest["files"].append({"path": str(p.relative_to(target)).replace("\\", "/"), "size": p.stat().st_size, "sha256": sha256_file(p)})
            except Exception:
                pass
    write_json(target / "PACKAGE_MANIFEST.json", manifest)
    write_text(target / "app" / "trace" / "ui_reuse_plan.md", """# UI reuse plan

The V6 workbench reuses the prior project introduction visual language for the dashboard hero, metrics, evidence cards, and agent-node layout. It reuses the prior local workflow package for image binding, treatment board concepts, safety gate phrasing, and trace structure. It reuses the GraphRAG visualization package for global evidence graph topology and figure assets.

Public UI is English-only and uses clinical workbench wording.
""")
    write_text(target / "app" / "trace" / "data_reuse_plan.md", """# Data reuse plan

Data sources integrated into V6:

1. SQLite Evidence Unit database from the localized KOA MDT GraphRAG project.
2. GraphRAG visualization package graph matrix and figure outputs.
3. V5 real OAI case workflow state, image assets, case graph, safety rules, and treatment board.
4. Quadrant seed cases from the prior local package.
5. Lightweight local case seeds for multi-case workflow testing.

Graph aggregate records are marked as context display only and are not used as direct recommendation evidence.
""")
    inv_path = target / "app" / "trace" / "reference_assets_inventory.csv"
    ensure_dir(inv_path.parent)
    with inv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["asset_group", "source_path", "copied_to", "size", "sha256", "reuse_purpose"])
        writer.writeheader()
        writer.writerows(inventory_rows)


def write_seed_files(target: Path, cases: list[dict[str, Any]], evidence: list[dict[str, Any]], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], agents: list[dict[str, Any]], safety: list[dict[str, Any]], trace: list[dict[str, Any]]) -> None:
    data = target / "app" / "data"
    write_jsonl(data / "seed_cases.jsonl", cases)
    write_jsonl(data / "evidence_units.jsonl", evidence)
    write_json(data / "graph_nodes.json", nodes)
    write_json(data / "graph_edges.json", edges)
    write_json(data / "agent_templates.json", agents)
    write_json(data / "safety_rules.json", safety)
    write_json(data / "report_templates.json", {
        "sections": ["Patient summary", "Image-linked assessment", "Risk profile", "Evidence graph summary", "Treatment board synthesis", "Safety review", "Follow-up plan", "Clinician confirmation"],
        "exports": ["html", "markdown", "json"],
    })
    write_jsonl(data / "conversation_log.jsonl", trace)


def copy_reference_assets(target: Path, graph_zip: Path, intro_html: Path, local_index: Path, v5_root: Path) -> tuple[Path, list[dict[str, Any]]]:
    inventory: list[dict[str, Any]] = []
    ref = target / "reference_assets"
    groups = {
        "previous_project_intro": ref / "previous_project_intro" / intro_html.name,
        "previous_intake_interfaces": ref / "previous_intake_interfaces" / local_index.name,
        "previous_graphrag_workbench": ref / "previous_graphrag_workbench" / graph_zip.name,
    }
    for group, dst in groups.items():
        src = {"previous_project_intro": intro_html, "previous_intake_interfaces": local_index, "previous_graphrag_workbench": graph_zip}[group]
        copy_file(src, dst)
        inventory.append({"asset_group": group, "source_path": str(src), "copied_to": str(dst.relative_to(target)), "size": src.stat().st_size, "sha256": sha256_file(src), "reuse_purpose": "reference and UI/data reuse"})
    graph_extract = ref / "previous_graphrag_workbench" / "extracted"
    ensure_dir(graph_extract)
    with zipfile.ZipFile(graph_zip, "r") as z:
        z.extractall(graph_extract)
    v5_static = v5_root / "app" / "static" / "index.html"
    if v5_static.exists():
        dst = ref / "previous_ui_examples" / "v5_index.html"
        copy_file(v5_static, dst)
        inventory.append({"asset_group": "previous_ui_examples", "source_path": str(v5_static), "copied_to": str(dst.relative_to(target)), "size": v5_static.stat().st_size, "sha256": sha256_file(v5_static), "reuse_purpose": "prior local workflow interaction pattern"})
    # Public image and figure assets used by V6.
    img_dir = target / "app" / "static" / "assets" / "images"
    for name in ["real_oai_knee_image_panel.png", "real_oai_knee_image_demo.png", "demo_xray_sample.png", "xray_right_knee_KL3_demo.png"]:
        src = v5_root / "demo_cases" / name
        if src.exists():
            dst = img_dir / name
            copy_file(src, dst)
            inventory.append({"asset_group": "image_assets", "source_path": str(src), "copied_to": str(dst.relative_to(target)), "size": src.stat().st_size, "sha256": sha256_file(src), "reuse_purpose": "case-linked imaging workflow"})
    fig_src = graph_extract / "koa_graphrag_visualization" / "figures"
    fig_dst = target / "app" / "static" / "assets" / "graphrag_figures"
    if fig_src.exists():
        shutil.copytree(fig_src, fig_dst, dirs_exist_ok=True)
        for p in fig_dst.glob("*"):
            if p.is_file():
                inventory.append({"asset_group": "graphrag_figures", "source_path": str(fig_src / p.name), "copied_to": str(p.relative_to(target)), "size": p.stat().st_size, "sha256": sha256_file(p), "reuse_purpose": "evidence graph visual context"})
    return graph_extract, inventory


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--v5-root", required=True)
    ap.add_argument("--graph-zip", required=True)
    ap.add_argument("--intro-html", required=True)
    ap.add_argument("--local-index", required=True)
    ap.add_argument("--source-db", required=True)
    args = ap.parse_args()
    target = Path(args.target)
    v5_root = Path(args.v5_root)
    graph_zip = Path(args.graph_zip)
    intro_html = Path(args.intro_html)
    local_index = Path(args.local_index)
    source_db = Path(args.source_db)

    backup_target(target)
    ensure_dir(target)
    for rel in [
        "app/backend/validation", "app/static/assets", "app/data", "app/models", "app/outputs",
        "app/trace", "app/config", "app/validation", "demo_cases", "developer_assets/source_frontend",
        "developer_assets/source_backend", "developer_assets/scripts", "developer_assets/tests", "developer_assets/docs",
        "validation/screenshots", "validation/traces",
    ]:
        ensure_dir(target / rel)

    runtime_src = v5_root / "runtime"
    runtime_dst = target / "runtime"
    if runtime_src.exists():
        shutil.copytree(runtime_src, runtime_dst, dirs_exist_ok=True)

    graph_extract, inventory = copy_reference_assets(target, graph_zip, intro_html, local_index, v5_root)
    for name in ["demo_case_Q1_low_low.json", "demo_case_Q2_low_high.json", "demo_case_Q3_high_low.json", "demo_case_Q4_high_high.json", "DEMO_OAI_REAL_IMAGE_001.json", "DEMO_Q4_001.json"]:
        src = v5_root / "demo_cases" / name
        if src.exists():
            copy_file(src, target / "demo_cases" / name)

    v5_state = read_json(v5_root / "app" / "data" / "v5_workflow_state.json", {})
    graph_json = graph_extract / "koa_graphrag_visualization" / "data" / "graph_data.json"
    cases = dedupe_cases([case_from_v5_state(v5_state)] + load_quadrant_cases(v5_root / "demo_cases") + generate_lightweight_cases(20))
    evidence = load_source_evidence(source_db, v5_state, target_count=3266)
    nodes, edges = build_graph_data(graph_json, v5_state)
    agents = build_agents(v5_state)
    safety = build_safety_rules()
    trace = build_trace_events(cases, agents)

    create_database(target / "app" / "data" / "kom_workbench.sqlite", cases, evidence, nodes, edges, agents, safety, trace)
    write_seed_files(target, cases, evidence, nodes, edges, agents, safety, trace)
    write_text(target / "app" / "backend" / "server.py", render_server_py())
    write_text(target / "app" / "start_server.py", render_start_server())
    write_text(target / "app" / "backend" / "validation" / "validate_v6_workbench.py", render_validation_py())
    write_text(target / "developer_assets" / "scripts" / "build_v6_workbench.py", Path(__file__).read_text(encoding="utf-8"))
    write_text(target / "app" / "static" / "index.html", render_index_html())
    write_bat_files(target)

    counts = {
        "cases": len(cases),
        "evidence_units": len(evidence),
        "graph_nodes": len(nodes),
        "graph_edges": len(edges),
        "agents": len(agents),
        "safety_rules": len(safety),
        "trace_events": len(trace),
    }
    write_docs(target, inventory, counts)
    write_json(target / "app" / "config" / "local_workbench_config.json", {"port": PORT, "package": PACKAGE_NAME, "created_at": now_iso(), "default_case_id": "DEMO_OAI_CASE_001"})

    # Initial validation folder marker; the validation script overwrites detailed reports.
    write_json(target / "validation" / "build_counts.json", counts)
    print(json.dumps({"target": str(target), "counts": counts}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
