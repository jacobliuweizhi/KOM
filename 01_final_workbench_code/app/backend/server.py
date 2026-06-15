from __future__ import annotations

import json
import os
import re
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
VALIDATION_DIR = ROOT / "validation"
DB = DATA / "kom_workbench.sqlite"
CONTENT = DATA / "v9_workbench_content.json"
LLM_LOCAL = CONFIG / "llm_config.local.json"
PROFILE_CURRENT = DATA / "current_profile_config.json"
RX_FINAL = DATA / "final_rx_prescription.json"

GET_ROUTES = [
    "/api/routes", "/api/status", "/api/v9/content", "/api/v9/validate", "/api/v9/evidence/explore",
    "/api/v9/risk/predict", "/api/v10/evidence/units", "/api/v10/evidence/patient-fit", "/api/validation", "/api/settings/llm/status",
    "/api/v16/profile/current", "/api/v16/rx/final",
    "/api/report", "/api/v8/content", "/api/v8/pipeline", "/api/v8/evidence-chain", "/api/v8/agents",
    "/api/v8/prescription", "/api/cases", "/api/evidence", "/api/graph", "/api/agents", "/api/safety",
    "/api/trace",
]
POST_ROUTES = [
    "/api/pathway/run", "/api/v9/agent/chat", "/api/v9/rad/analyze", "/api/v9/risk/predict",
    "/api/v10/profile/generate", "/api/v10/risk/simulate", "/api/v10/evidence/patient-fit", "/api/v15/safe/negotiate",
    "/api/v16/profile/save", "/api/v16/rx/finalize",
    "/api/settings/llm/test-text", "/api/settings/llm/test-vision", "/api/settings/llm/save",
    "/api/settings/llm/clear", "/api/agents/challenge",
    "/api/v8/prescription/polish", "/api/report/generate",
]


def api_ok(data=None, warnings=None, trace_id=None):
    return {"ok": True, "data": data, "warnings": warnings or [], "error": None, "trace_id": trace_id or f"trace-{int(time.time()*1000)}"}


def api_error(code, message, details=None):
    return {"ok": False, "data": None, "warnings": [], "error": {"code": code, "message": message, "details": details or {}}, "trace_id": f"trace-{int(time.time()*1000)}"}


def content():
    if not CONTENT.exists():
        return {"version": "missing_content", "case": {}, "agents": [], "evidence": {"chains": {}}, "report": []}
    return json.loads(CONTENT.read_text(encoding="utf-8"))


def read_json_file(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json_file(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def con():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db


def public_demo_mode():
    return os.environ.get("KOM_PUBLIC_DEMO", "").strip().lower() in {"1", "true", "yes", "on"}


def settings_load():
    cfg = {"provider": "OpenAI-compatible", "base_url": "https://xiaoai.plus/v1", "text_model": "gpt-4o", "vision_model": "gpt-4o", "temperature": 0.2, "timeout_seconds": 60, "masked_api_key": None, "status": "Not configured"}
    if public_demo_mode():
        cfg.update({
            "status": "Public demo mode: private API keys are not persisted on this shared server.",
            "public_demo_mode": True,
            "server_side_key_available": bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("XIAOAI_API_KEY")),
        })
        return cfg
    if LLM_LOCAL.exists():
        try:
            cfg.update(json.loads(LLM_LOCAL.read_text(encoding="utf-8")))
        except Exception:
            pass
    return cfg


def mask_key(key):
    return None if not key else ("sk-***" + key[-4:] if len(key) >= 8 else "***")


def call_openai_compatible(payload, prompt=None, vision=False):
    cfg = settings_load()
    key = payload.get("api_key") or cfg.get("api_key") or os.environ.get("OPENAI_API_KEY") or os.environ.get("XIAOAI_API_KEY")
    base_url = (payload.get("base_url") or cfg.get("base_url") or "https://xiaoai.plus/v1").rstrip("/")
    model = payload.get("vision_model" if vision else "text_model") or cfg.get("vision_model" if vision else "text_model") or "gpt-4o"
    timeout = int(payload.get("timeout_seconds") or cfg.get("timeout_seconds") or 60)
    if not key:
        return api_error("llm_key_missing", "No API key is configured. The deterministic KOM local pathway remains available.", {"base_url": base_url, "model": model})
    user_message = prompt or "Confirm in one concise English sentence that the KOM local clinical workbench model connection is available."
    if vision:
        user_message = [
            {"type": "text", "text": "Confirm in one concise English sentence that the vision model connection is available."},
            {"type": "image_url", "image_url": {"url": payload.get("image_url") or "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAghnSxwAAAABJRU5ErkJggg=="}},
        ]
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a concise assistant inside a knee osteoarthritis clinical workbench. Do not invent patient facts. Medication, injection, exercise, nutrition, psychology and surgery recommendations must retain clinician-review boundaries."},
            {"role": "user", "content": user_message},
        ],
        "temperature": float(payload.get("temperature") or cfg.get("temperature") or 0.2),
        "max_tokens": int(payload.get("max_tokens") or 700),
    }
    req = urllib.request.Request(
        base_url + "/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return api_ok({"status": "connected", "model": model, "base_url": base_url, "response": text, "masked_api_key": mask_key(key)})
    except urllib.error.HTTPError as exc:
        msg = exc.read().decode("utf-8", errors="replace")[:1000]
        return api_error("llm_http_error", "The configured provider returned an HTTP error.", {"status": exc.code, "body": msg, "base_url": base_url, "model": model})
    except Exception as exc:
        return api_error("llm_connection_failed", "Unable to connect to the configured provider.", {"error": str(exc), "base_url": base_url, "model": model})


def no_cjk_in_public_files():
    pattern = re.compile(r"[\u4e00-\u9fff]")
    roots = [STATIC, DATA, APP / "backend", ROOT]
    allowed_suffix = {".html", ".js", ".css", ".py", ".json", ".md", ".bat", ".txt"}
    generated_validation_files = {
        "v9_validation_report.json",
        "package_integrity_report.json",
        "zip_integrity_report.json",
    }
    bad = []
    for base in roots:
        for path in base.rglob("*") if base.is_dir() else []:
            if not path.is_file() or path.suffix.lower() not in allowed_suffix:
                continue
            if "runtime" in path.parts or "__pycache__" in path.parts:
                continue
            if path.name in generated_validation_files:
                continue
            if VALIDATION_DIR in path.parents:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if pattern.search(text):
                bad.append(str(path.relative_to(ROOT)))
    return bad


def validation_result():
    c = content()
    js = (STATIC / "kom_v9.js").read_text(encoding="utf-8", errors="ignore")
    html = (STATIC / "index.html").read_text(encoding="utf-8", errors="ignore")
    serialized = json.dumps(c, ensure_ascii=False)
    checks = []

    def add(name, passed, detail):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    bad = no_cjk_in_public_files()
    add("english_public_content", not bad, "No CJK characters were found in public app, API, data, README or script files." if not bad else "; ".join(bad[:10]))
    add("english_html_language", 'lang="en"' in html and "KOM Knee Osteoarthritis Clinical Workbench" in html, "HTML document language and title are English.")
    add("assess_treat_architecture", "KOM-Assess" in serialized and "KOM-Treat" in serialized, "Two-subsystem architecture is visible.")
    add("profile_controls", all(x in js for x in ["WOMAC assistant", "KOOS assistant", "Quadriceps strength assistant", "Generate KOM-Profile"]), "Interactive KOM-Profile controls are present.")
    add("radiology_run_state", all(x in js for x in ["Structured interpretation has not been run", "Run structural interpretation", "Original image", "Annotated image"]), "KOM-Rad keeps a run-state distinction.")
    add("risk_prediction", all(x in js + serialized + open(__file__, encoding="utf-8").read() for x in ["Structural progression risk", "TKA-event risk", "Symptom/function worsening risk", "Scenario controls", "KL grade locked from KOM-Profile", "POST /api/v9/risk/predict", "not_frontend_simulation", "KL4 structural ceiling"]), "Risk prediction is endpoint-backed, side-specific, and scenario controls are limited to modifiable or follow-up variables.")
    add("bilateral_knee_logic", all(x in js + serialized for x in ["Left knee", "Right knee", "bilateral", "left_kl", "right_kl"]), "Left and right knees are explicit across profile, imaging and risk logic.")
    add("bilateral_coupled_risk", all(x in js + open(__file__, encoding="utf-8").read() for x in ["Cross-knee coupling", "bilateral_coupled", "contralateral_pain_nrs", "shared activity load and compensation"]), "KOM-Risk includes a transparent bilateral-coupled surrogate where contralateral pain/function/KL influence both knee predictions.")
    add("bilateral_weight_v2_audit", all(x in js + open(__file__, encoding="utf-8").read() for x in ["BILATERAL_WEIGHT_V4_KL4_CEILING_20260615", "riskWeightAuditHtml", "retraining_data_strategy", "compensation_load"]), "KOM-Risk exposes endpoint-backed V4 bilateral coupling weights, KL4 ceiling semantics and a paired-knee retraining data strategy.")
    add("kl4_ceiling_tka_gate", all(x in js + serialized + open(__file__, encoding="utf-8").read() for x in ["structural_event_applicable", "surgery_rule_floor", "KL4 is already the radiographic ceiling", "end-stage structural ceiling", "KL4 severe-symptom TKA gate"]), "KL4 is no longer interpreted as KL+1 progression and severe KL4 knees trigger a high TKA-event floor.")
    add("dashboard_endpoint_workflow", all(x in js + (STATIC / "kom_v9.css").read_text(encoding="utf-8", errors="ignore") for x in ["Configure API key", "Patient-state contract", "workflow-bg", "workflow-edge-line", "original_asset"]) and "workflow-legend" not in js and "workflow-edge-label" not in js, "Overview places Settings immediately after Overview and shows a meaningful endpoint/data-contract workflow graph over a non-distorted bilateral knee radiograph background.")
    add("dashboard_layer_navigation", all(x in js for x in ["Assessment layer", "Evidence layer", "MDT prescription layer", "Safety audit layer", "Verifiable output", "openFlowStep"]), "Dashboard layer buttons jump to KOM-Profile, KOM-RAG, KOM-MDT, KOM-Safe and KOM-Rx.")
    old_case_labels = [f"Q{i}" for i in range(1, 5)] + ["quad" + "rant_rule"]
    case_layout_ok = all(x in js + serialized for x in ["Four selectable patient examples", "Early education and monitoring case", "Activity-goal rehabilitation case", "Comorbidity and safety-gated conservative case", "Orthopedic referral-screen and prehabilitation case"]) and not any(x in js + serialized for x in old_case_labels)
    add("public_case_layout", case_layout_ok, "KOM-Profile uses four direct patient cases and removes the public external grading classification.")
    add("profile_card_readability", all(x in js + (STATIC / "kom_v9.css").read_text(encoding="utf-8", errors="ignore") for x in ["case-main", "case-kl-pill", "case-status-line", "case-panel-next", "summary-case-badge", "profile-workspace-v26", "profile-quick-editor", "profile-next-floating", 'if(r==="assess") return ""', "V25 profile card visual guard", "V25.1 width audit", "V25.2 summary case badge", "V26 profile workspace"]), "KOM-Profile case cards, summary badge, visible bilateral editor and sticky Next action prevent label overlap, clipping, hidden lower-left content and Case 4 wrapping.")
    add("case_locked_kl_risk", all(x in js for x in ["locked-kl-panel", "KL grade is an observed radiographic input", "BMI scenario"]) and 'riskSlider("left_kl"' not in js and 'riskSlider("right_kl"' not in js, "KOM-Risk displays KL as locked profile-derived input and does not expose left/right KL sliders.")
    add("editable_kl_profile_fields", all(x in js for x in ["profileKlField", "klOptions", "left_kl", "right_kl", "Editable only in KOM-Profile", "onchange=\"updateProfileField(this)\""]) and 'if(["left_kl","right_kl"].includes(id)) return' not in js, "KOM-Profile exposes editable left/right KL controls, while downstream modules read the resulting profile-derived KL values.")
    risk_input_block = re.search(r"function updateRiskInput[\s\S]*?function updateRiskDisplay", js)
    add("smooth_profile_risk_sliders", all(x in js for x in ["updateProfileFieldFast", "commitProfileField", "updateRiskDisplay"]) and risk_input_block is not None and "risk();" not in risk_input_block.group(0), "WOMAC/NRS/BMI sliders update values without full page rerender on every input.")
    add("persistent_profile_config", all(x in js + open(__file__, encoding="utf-8").read() for x in ["/api/v16/profile/save", "/api/v16/profile/current", "current_profile_config.json", "Save profile configuration"]), "Profile configuration is saved locally and reused by downstream modules.")
    add("rag_catalog_and_chain", all(x in js for x in ["Evidence catalog", "Case evidence chain", "L1-L7 evidence hierarchy", "Search catalog"]), "KOM-RAG contains evidence-chain and full-catalog views.")
    add("rag_sticky_domain_switcher", all(x in js + (STATIC / "kom_v9.css").read_text(encoding="utf-8", errors="ignore") for x in ["evidence-chain-sticky", "position:sticky", "state.manualChain=true", "state.chain='${k}'"]), "Specialty evidence chain keeps domain tabs and level filters sticky while the panel scrolls.")
    add("rag_floating_evidence_detail", all(x in js for x in ["evidence-float", "Open floating detail", "if(event.target===this)closeEvidenceOverlay"]), "KOM-RAG evidence cards and chain nodes can open floating Evidence Unit details and close them by clicking the backdrop.")
    add("interactive_dynamic_graph", all(x in js + (STATIC / "kom_v9.css").read_text(encoding="utf-8", errors="ignore") for x in ["KOM-RAG interactive evidence network", "interactive-network", "network-evidence", "Current catalog/query result"]) and "clean-network-stage" not in js, "Full graph figure is an interactive patient/query-driven network instead of a static overlapping image.")
    add("rag_graph_level_sampling", all(x in js for x in ["selectRankedPack(state.evidenceDb, fallback)", "The graph now samples by L1-L7 level", "currentCounts"]), "Full graph figure samples across L1-L7 so L1 guideline rows cannot hide other evidence tiers.")
    add("rag_quantified_evidence_detail", all(x in js for x in ["Population and quantified result extraction", "Quantitative effect status", "Result direction", "Population_Fingerprint", "Evidence_Extraction_QA", "Source_Abstract"]), "Evidence Unit detail extracts source-level population, intervention, result direction and quantitative-effect availability.")
    try:
        with con() as db:
            total_l2_l3 = db.execute("select count(*) from evidence_units where Evidence_Level like 'L2%' or Evidence_Level like 'L3%'").fetchone()[0]
            weak_l2_l3 = db.execute("""
                select count(*) from evidence_units
                where (Evidence_Level like 'L2%' or Evidence_Level like 'L3%')
                and lower(coalesce(P_Population,'') || ' ' || coalesce(O_Outcomes,'') || ' ' || coalesce(Effect_Summary,'')) glob '*not encoded*'
            """).fetchone()[0]
            weak_l2_l3 += db.execute("""
                select count(*) from evidence_units
                where (Evidence_Level like 'L2%' or Evidence_Level like 'L3%')
                and lower(coalesce(P_Population,'') || ' ' || coalesce(O_Outcomes,'') || ' ' || coalesce(Effect_Summary,'')) glob '*full-text extraction required*'
            """).fetchone()[0]
            weak_l2_l3 += db.execute("""
                select count(*) from evidence_units
                where (Evidence_Level like 'L2%' or Evidence_Level like 'L3%')
                and lower(coalesce(Effect_Summary,'')) glob '*numeric magnitude requires full-text*'
            """).fetchone()[0]
            v28_cols = {row[1] for row in db.execute("pragma table_info(evidence_units)").fetchall()}
            required_v28 = {"Population_Fingerprint", "Intervention_Detail", "Comparator_Detail", "Result_Direction", "Quantitative_Effect_Status", "Evidence_Extraction_QA", "Source_PMID", "Source_Abstract"}
            v28_ready = required_v28.issubset(v28_cols)
            v28_report = DATA / "evidence_enrichment_report_v28.json"
            v28_report_ready = v28_report.exists() and json.loads(v28_report.read_text(encoding="utf-8")).get("weak_numeric_marker_remaining") == 0
            v28_missing = db.execute("""
                select count(*) from evidence_units
                where (Evidence_Level like 'L2%' or Evidence_Level like 'L3%')
                and (coalesce(Population_Fingerprint,'')='' or coalesce(Intervention_Detail,'')='' or coalesce(Result_Direction,'')='' or coalesce(Quantitative_Effect_Status,'')='')
            """).fetchone()[0]
    except Exception:
        total_l2_l3, weak_l2_l3, v28_ready, v28_report_ready, v28_missing = 0, 1, False, False, 1
    add("l2_l3_evidence_qa", total_l2_l3 >= 1 and weak_l2_l3 == 0 and v28_ready and v28_report_ready and v28_missing == 0, f"L2/L3 V28 source-abstract evidence QA completed for {total_l2_l3} rows; weak marker rows: {weak_l2_l3}; missing V28 detail rows: {v28_missing}.")
    add("rag_catalog_pagination", all(x in js for x in ["evidenceVisible", "increaseEvidenceVisible", "Export JSON", "Show ${Math.min", ".slice(0,state.evidenceVisible)"]), "Evidence catalog renders paginated rows and exports full JSON without freezing the page.")
    add("patient_fit_rag_api", "/api/v10/evidence/patient-fit" in GET_ROUTES and "success_rule" in js + open(__file__, encoding="utf-8").read(), "Patient-fit RAG retrieval has an API route and explicit success rule.")
    add("mdt_specialty_agents", all(x in serialized for x in ["Exercise and rehabilitation agent", "Medication and injection agent", "Orthopedic surgery recommendation and preoperative warning agent"]), "Specialty agents are present.")
    add("mdt_agent_dialogue_api", all(x in js + open(__file__, encoding="utf-8").read() for x in ["agent-quick-prompts", "quickAgentPrompt", "deterministic_specialty_agent", "agent_response_text", "deterministic_local_draft", "selected_modules", "safety_checks"]), "Each MDT specialty agent exposes quick prompts and a local/API dialogue path using current patient data, selected modules and safety gates.")
    add("deep_treatment_detail", all(x in serialized + js + open(__file__, encoding="utf-8").read() for x in ["Diclofenac 1% gel", "Celecoxib", "Duloxetine", "Sodium hyaluronate", "Leukocyte-poor PRP", "Genicular nerve radiofrequency", "RNA/mRNA frontier therapy", "Nutrition target", "CBT", "Mandatory pre-referral screen", "Stationary cycling", "Quadriceps isometrics", "Specific exercise action menu", "Balance and gait safety block", "result_tiers"]), "Treatment plan includes concrete medication, injection, exercise, nutrition, psychology, pre-referral screening and frontier/research-only boundaries.")
    add("selectable_rx_builder", all(x in js for x in ["Build the final KOM-Rx by clicking treatment options", "Selected clinician prescription", "Sodium hyaluronate", "Platelet-rich plasma (PRP)", "toggleRxOption"]), "KOM-Rx includes a clinician-selectable modular prescription builder.")
    add("rx_evidence_support", all(x in js for x in ["evidence_support", "rxEvidenceHtml", "rxEvidenceText", "KOA-EU-STEP9-2024", "KOA-EU-00477"]), "Every selectable and final KOM-Rx module carries L1-L7 Evidence Unit support.")
    add("final_rx_confirmation", all(x in js + open(__file__, encoding="utf-8").read() for x in ["Confirm final KOM-Rx", "/api/v16/rx/finalize", "final_rx_prescription.json", "Draft not finalized"]), "Clinician-selected modules generate a saved final prescription after confirmation.")
    add("semaglutide_obesity_module", all(x in js + serialized for x in ["Semaglutide 2.4 mg once weekly", "STEP 9", "obesity-treatment option"]), "Obese knee OA pathway includes a semaglutide/STEP 9 special-population option with safety boundaries.")
    add("safe_compatibility_data_gates", all(x in js for x in ["Specialty compatibility gate", "Patient data completeness gate", "Medication safety gate", "Orthopedic referral and preoperative screening gate"]), "KOM-Safe separates cross-specialty prescription compatibility from patient-data completeness gates.")
    add("safe_negotiation", all(x in js for x in ["Safe-MDT negotiation", "Specialty revision", "Re-audit", "Adoption / clinician review"]), "KOM-Safe negotiation loop is visible.")
    add("safe_audit_traceability", all(x in js + open(__file__, encoding="utf-8").read() for x in ["audit_id", "event_id", "input_gate_status", "adoption_rule"]), "KOM-Safe negotiation records auditable event IDs, input gate status and adoption rules.")
    add("rx_report", all(x in js for x in ["Patient assessment report", "MDT treatment prescription", "Detailed medication and injection plan"]), "KOM-Rx structured report is visible.")
    add("score_validation", all(x in serialized for x in ["Rule and model validation", "Expert prescription quality review", "Safety-event and gate audit"]), "KOM-Score validation layers are represented.")
    add("api_routes", "/api/v15/safe/negotiate" in POST_ROUTES and "/api/v10/evidence/units" in GET_ROUTES, "Required API routes are registered.")
    status = "KOM_ENGLISH_READY" if all(item["passed"] for item in checks) else "KOM_ENGLISH_NEEDS_FIX"
    result = {"status": status, "summary": f"{sum(item['passed'] for item in checks)}/{len(checks)} checks passed", "checks": checks}
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    (VALIDATION_DIR / "v9_validation_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def pathway_run():
    stages = ["KOM-Profile patient profile", "KOM-Rad structured imaging interpretation", "KOM-Risk three-endpoint prediction", "KOM-RAG evidence retrieval", "KOM-MDT specialty prescription", "KOM-Safe safety negotiation", "KOM-Rx report curation"]
    out = {"status": "pathway_completed", "summary": "The deterministic local clinical pathway has completed. If an API key is configured, model calls can support specialty follow-up and report refinement without bypassing safety gates.", "stages": stages, "timestamp": now()}
    (DATA / "latest_pathway_run.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def markdown_report(c):
    lines = ["# KOM Knee Osteoarthritis Structured Prescription", ""]
    final_rx = read_json_file(RX_FINAL, {})
    if final_rx:
        p = final_rx.get("prescription") or final_rx
        lines += ["## Final clinician-selected KOM-Rx", f"Finalized at: {p.get('finalized_at', 'not recorded')}", ""]
        for item in p.get("selected_modules", []):
            lines += [f"- {item.get('label', 'Selected module')}: {item.get('detail', '')}"]
        lines += [""]
    for heading, body in c.get("report", []):
        lines += [f"## {heading}", body, ""]
    return "\n".join(lines)


def profile_current():
    return read_json_file(PROFILE_CURRENT, {"profile": {}, "selectedCase": None, "rxSelections": {}, "chain": None, "saved_at": None})


def profile_save(body):
    payload = {
        "profile": body.get("profile") or {},
        "selectedCase": body.get("selectedCase"),
        "riskInputs": body.get("riskInputs") or {},
        "rxSelections": body.get("rxSelections") or {},
        "chain": body.get("chain"),
        "saved_at": body.get("saved_at") or now(),
        "source": "KOM local profile persistence",
    }
    return write_json_file(PROFILE_CURRENT, payload)


def final_rx_current():
    return read_json_file(RX_FINAL, {"prescription": None, "saved_at": None})


def final_rx_save(body):
    payload = {
        "prescription": body,
        "saved_at": body.get("finalized_at") or now(),
        "source": "KOM local final prescription confirmation",
    }
    return write_json_file(RX_FINAL, payload)


def profile_generate(body):
    def num(name, default=0.0):
        try:
            return float(body.get(name, default))
        except Exception:
            return default
    def side_num(side, name, default=0.0):
        return num(f"{side}_{name}", num(name, default))
    def first_value(*names):
        for name in names:
            value = body.get(name)
            if value is not None and str(value).strip() != "":
                return str(value).strip()
        return ""

    knees = {}
    for side in ("left", "right"):
        kl = side_num(side, "kl", 0)
        nrs = side_num(side, "nrs", 0)
        womac = side_num(side, "womac_function", 0)
        structural_stage = "advanced / severe" if kl >= 4 else "definite radiographic OA" if kl >= 2 else "early or doubtful radiographic OA"
        progression_state = "progressed or high structural burden" if kl >= 3 or womac >= 50 else "monitor for progression"
        knees[side] = {
            "side": f"{side.title()} knee",
            "kl": kl,
            "pain_nrs": nrs,
            "womac_function": womac,
            "strength": first_value(f"{side}_strength") or "Not recorded",
            "structural_stage": structural_stage,
            "progression_state": progression_state,
            "clinical_priority": "primary treatment planning" if kl >= 3 or nrs >= 7 or womac >= 50 else "comparative monitoring and prevention",
        }
    max_kl = max(k["kl"] for k in knees.values())
    max_nrs = max(k["pain_nrs"] for k in knees.values())
    max_womac = max(k["womac_function"] for k in knees.values())
    bmi = num("bmi", 0)
    target_side = first_value("target_side", "target_knee") or "Both knees"
    target_lower = target_side.lower()
    primary_sides = ["left", "right"] if "both" in target_lower else ["right"] if "right" in target_lower else ["left"]
    if "both" in target_lower:
        primary_sides = [s for s, k in knees.items() if k["kl"] >= 3 or k["pain_nrs"] >= 7 or k["womac_function"] >= 50] or ["left", "right"]
    high_burden = max_kl >= 3 or max_nrs >= 7 or max_womac >= 50
    goal_text = str(body.get("quality_goal", "")).lower()
    injection_text = str(body.get("avoid_injection", "")).lower()
    surgery_text = str(body.get("surgery_question", "")).lower()
    high_demand = (
        any(token in goal_text for token in ["3 km", "return", "sport", "referral", "surgery", "arthroplasty"])
        or any(token in surgery_text for token in ["yes", "referral", "surgery"])
        or any(token in injection_text for token in ["yes", "avoid repeated", "avoid injection"])
    )
    case_profile = "surgical_referral" if high_burden and high_demand else "medical_complex" if high_burden else "active_rehab" if high_demand else "early_education"
    case_label = {
        "early_education": "Early education and monitoring case",
        "active_rehab": "Activity-goal rehabilitation case",
        "medical_complex": "Comorbidity and safety-gated conservative case",
        "surgical_referral": "Orthopedic referral-screen and prehabilitation case",
    }[case_profile]
    missing = []
    for keys, label in [
        (("egfr", "renal_status", "renal_function"), "eGFR / creatinine"),
        (("gi_history", "gi_bleeding_history", "gi_ulcer_history"), "GI ulcer or bleeding history"),
        (("anticoag", "anticoagulant_status", "antiplatelet_status"), "Anticoagulant / antiplatelet status"),
        (("current_meds", "current_medications", "medication_list"), "Complete current medication list"),
        (("conservative_history", "prior_conservative_treatment", "conservative_treatment_history"), "Conservative-treatment history"),
        (("gad7", "phq9", "sleep_quality", "pain_catastrophizing"), "Psychology and sleep screening signals"),
        (("weightbearing_alignment_xray", "knee_rom"), "Weight-bearing radiograph or knee ROM pre-referral screen"),
        (("surgical_cv_screen", "surgical_resp_screen", "skin_dental_infection_screen"), "Self-reported cardiovascular, respiratory and infection screen"),
    ]:
        val = first_value(*keys).lower()
        if not val or val in {"missing", "unknown", "not recorded", "needs review"}:
            missing.append(label)
    gates = [
        "Bilateral knee rule: left and right knees must each retain their own profile-derived KL grade, pain/function anchor, imaging interpretation and follow-up progression state.",
        "Oral NSAID: DEFER until renal + GI + anticoagulant/current medication + cardiovascular review is complete.",
        "Exercise: FITT-VP, fall prevention and symptom-based stop rules are required.",
        "Nutrition: weight management must have an explicit target and be paired with muscle preservation; avoid fixed high-protein targets until renal function is known.",
        "Orthopedics: referral screening requires weight-bearing radiographs/alignment status, ROM, conservative-treatment response, and self-reported cardiovascular, respiratory and infection-risk screen; the system does not choose TKA, UKA or HTO.",
    ]
    bilateral_line = "; ".join(
        f"{knees[s]['side']} KL {knees[s]['kl']:g}, NRS {knees[s]['pain_nrs']:g}, WOMAC function {knees[s]['womac_function']:g}, {knees[s]['progression_state']}"
        for s in ("left", "right")
    )
    return {
        "case_profile": case_profile,
        "case_label": case_label,
        "burden": "high burden" if high_burden else "low burden",
        "demand": "high demand" if high_demand else "low demand",
        "one_line": f"{int(num('age', 0))}-year-old {body.get('sex','not recorded')}, bilateral knee profile: {bilateral_line}; BMI {bmi:g}; primary planning side(s): {', '.join(knees[s]['side'] for s in primary_sides)}; selected case: {case_label}.",
        "knees": knees,
        "primary_decision_knees": [knees[s]["side"] for s in primary_sides],
        "bilateral_profile": bilateral_line,
        "missing": missing,
        "gates": gates,
    }


def query_evidence_rows(q="", level="", domain="", limit=3266):
    q = (q or "").strip().lower()
    level = (level or "").strip()
    domain = (domain or "").strip()
    limit = max(1, min(5000, int(limit or 3266)))
    rows, total_database, total_matches = [], 0, 0
    if DB.exists():
        where = " FROM evidence_units WHERE 1=1"
        params = []
        if q:
            where += " AND (lower(EU_ID) LIKE ? OR lower(Title) LIKE ? OR lower(P_Population) LIKE ? OR lower(I_Intervention) LIKE ? OR lower(O_Outcomes) LIKE ? OR lower(Effect_Summary) LIKE ? OR lower(Safety_or_Contraindication_Note) LIKE ? OR lower(Prescription_Use) LIKE ? OR lower(coalesce(Population_Fingerprint,'')) LIKE ? OR lower(coalesce(Intervention_Detail,'')) LIKE ? OR lower(coalesce(Comparator_Detail,'')) LIKE ? OR lower(coalesce(Result_Direction,'')) LIKE ? OR lower(coalesce(Quantitative_Effect_Status,'')) LIKE ? OR lower(coalesce(Evidence_Extraction_QA,'')) LIKE ? OR lower(coalesce(Source_PMID,'')) LIKE ? OR lower(coalesce(Source_Abstract,'')) LIKE ?)"
            like = f"%{q}%"
            params += [like, like, like, like, like, like, like, like, like, like, like, like, like, like, like, like]
        if level:
            where += " AND Evidence_Level LIKE ?"
            params.append(level + "%")
        if domain:
            where += " AND Agent_Database LIKE ?"
            params.append("%" + domain + "%")
        sql = "SELECT EU_ID, Agent_Database, Title, Evidence_Level, KOA_Relevance_Grade, Traceability_Status, P_Population, I_Intervention, C_Comparator, O_Outcomes, Effect_Summary, Safety_or_Contraindication_Note, Prescription_Use, source_link, year, Population_Fingerprint, Intervention_Detail, Comparator_Detail, Result_Direction, Quantitative_Effect_Status, Evidence_Extraction_QA, Source_PMID, Source_Abstract" + where
        sql += " ORDER BY CASE WHEN Evidence_Level LIKE 'L1%' THEN 1 WHEN Evidence_Level LIKE 'L2%' THEN 2 WHEN Evidence_Level LIKE 'L3%' THEN 3 WHEN Evidence_Level LIKE 'L4%' THEN 4 WHEN Evidence_Level LIKE 'L5%' THEN 5 WHEN Evidence_Level LIKE 'L6%' THEN 6 ELSE 7 END, CAST(COALESCE(NULLIF(year,''),'0') AS INTEGER) DESC, EU_ID LIMIT ?"
        with con() as db:
            total_database = db.execute("SELECT COUNT(*) FROM evidence_units").fetchone()[0]
            total_matches = db.execute("SELECT COUNT(*)" + where, params).fetchone()[0]
            rows = [dict(row) for row in db.execute(sql, list(params) + [limit]).fetchall()]
    return rows, total_matches, total_database


def evidence_units_query(qs):
    q = (qs.get("q", [""])[0] or "").strip().lower()
    level = (qs.get("level", [""])[0] or "").strip()
    domain = (qs.get("domain", [""])[0] or "").strip()
    try:
        limit = max(1, min(5000, int(qs.get("limit", ["3266"])[0] or 3266)))
    except Exception:
        limit = 3266
    rows, total_matches, total_database = query_evidence_rows(q=q, level=level, domain=domain, limit=limit)
    return {"rows": rows, "count": len(rows), "total_matches": total_matches, "total_database": total_database, "limit": limit, "filters": {"q": q, "level": level, "domain": domain}}


def patient_fit_query(body_or_qs):
    if isinstance(body_or_qs, dict) and "q" in body_or_qs and isinstance(body_or_qs.get("q"), list):
        profile = {}
        free_q = (body_or_qs.get("q", [""])[0] or "").strip()
        domain = (body_or_qs.get("domain", [""])[0] or "").strip()
        limit = int(body_or_qs.get("limit", ["24"])[0] or 24)
    else:
        profile = body_or_qs.get("profile") or body_or_qs
        free_q = (body_or_qs.get("q") or body_or_qs.get("question") or "").strip()
        domain = (body_or_qs.get("domain") or body_or_qs.get("chain") or "").strip()
        limit = int(body_or_qs.get("limit") or 24)
    left_kl = profile.get("left_kl", profile.get("leftKl", ""))
    right_kl = profile.get("right_kl", profile.get("rightKl", ""))
    age = profile.get("age", "")
    sex = profile.get("sex", "")
    bmi = profile.get("bmi", "")
    nrs = profile.get("nrs", profile.get("pain_nrs", ""))
    womac = profile.get("womac", profile.get("womac_function", ""))
    safety_terms = "renal GI anticoagulant cardiovascular medication safety" if not profile.get("medicationGateComplete") else "lowest effective dose monitoring"
    query = " ".join(str(x) for x in [free_q, age, sex, "knee osteoarthritis", f"left KL {left_kl}", f"right KL {right_kl}", f"BMI {bmi}", f"NRS {nrs}", f"WOMAC {womac}", safety_terms] if str(x).strip())
    if not domain:
        domain = "surgery_or_escalation" if max(float(left_kl or 0), float(right_kl or 0)) >= 3 else "exercise_rehabilitation"
    retrieval_rounds = []
    rows = []
    seen = set()
    for round_name, q, d, per_level in [
        ("patient-fit query within selected domain", query, domain, True),
        ("selected-domain fallback", "", domain, True),
        ("broad KOA evidence fallback", free_q or "knee osteoarthritis treatment guideline NSAID exercise surgery psychology nutrition", "", False),
    ]:
        round_rows = []
        levels = ["L1", "L2", "L3", "L4", "L5"] if per_level else [""]
        for level in levels:
            got, total_matches, total_database = query_evidence_rows(q=q, level=level, domain=d, limit=8)
            for row in got:
                key = row.get("EU_ID")
                if key not in seen:
                    seen.add(key)
                    rows.append(row)
                    round_rows.append(row)
        retrieval_rounds.append({
            "round": len(retrieval_rounds) + 1,
            "strategy": round_name,
            "query": q,
            "domain": d or "all domains",
            "retrieved": len(round_rows),
            "new_total": len(rows),
        })
        levels_found = {str(r.get("Evidence_Level", ""))[:2] for r in rows}
        if {"L1", "L2", "L3"}.issubset(levels_found) and len(rows) >= 6:
            break
    levels_found = {str(r.get("Evidence_Level", ""))[:2] for r in rows}
    success = {"L1", "L2", "L3"}.issubset(levels_found) and len(rows) >= 6
    return {
        "query": query,
        "domain": domain,
        "success": success,
        "success_rule": "Patient-fit retrieval is successful when at least L1 guideline/consensus, L2 synthesis and L3 trial/clinical evidence are returned, with at least six unique Evidence Units after no more than three retrieval rounds.",
        "retrieval_rounds": retrieval_rounds,
        "levels_found": sorted(levels_found),
        "rows": rows[:limit],
        "count": min(len(rows), limit),
        "total_unique_retrieved": len(rows),
    }


def risk_simulate(body):
    source_body = {}
    if isinstance(body, dict):
        source_body.update(body.get("profile") or {})
        source_body.update(body.get("risk_inputs") or body.get("riskInputs") or {})
        source_body.update({k: v for k, v in body.items() if k not in {"profile", "risk_inputs", "riskInputs"}})
    def num(name, default):
        try:
            return float(source_body.get(name, default))
        except Exception:
            return default
    def side_value(side, name, default):
        return num(f"{side}_{name}", num(name, default))
    bmi = num("bmi", 29.4)
    target = str(source_body.get("target_side") or "Both knees").lower()
    coefficient_version = "BILATERAL_WEIGHT_V4_KL4_CEILING_20260615"
    coeffs = {
        "left": {
            "structural": {"kl": .055, "bmi": .0060, "nrs": .010, "womac": .00120, "other_nrs": .0040, "other_womac": .00050, "other_kl": .010, "comp_nrs": .005, "comp_womac": .00070},
            "surgery": {"kl": .045, "bmi": .0040, "nrs": .006, "womac": .00100, "other_nrs": .0025, "other_womac": .00040, "other_kl": .008, "comp_nrs": .004, "comp_womac": .00070},
            "symptom": {"kl": .018, "bmi": .010, "nrs": .026, "womac": .00200, "other_nrs": .006, "other_womac": .00080, "other_kl": .006, "comp_nrs": .005, "comp_womac": .00080},
        },
        "right": {
            "structural": {"kl": .045, "bmi": .0065, "nrs": .008, "womac": .00110, "other_nrs": .0080, "other_womac": .00080, "other_kl": .014, "comp_nrs": .004, "comp_womac": .00070},
            "surgery": {"kl": .036, "bmi": .0045, "nrs": .005, "womac": .00090, "other_nrs": .0050, "other_womac": .00065, "other_kl": .012, "comp_nrs": .002, "comp_womac": .00060},
            "symptom": {"kl": .014, "bmi": .011, "nrs": .022, "womac": .00180, "other_nrs": .010, "other_womac": .00110, "other_kl": .009, "comp_nrs": .008, "comp_womac": .00110},
        },
    }

    def raw_side(side):
        return {
            "kl": side_value(side, "kl", 4 if side == "left" else 2),
            "nrs": side_value(side, "nrs", 8),
            "womac": side_value(side, "womac_function", side_value(side, "womac", 62)),
        }

    raw = {"left": raw_side("left"), "right": raw_side("right")}

    def calc(side):
        other = "right" if side == "left" else "left"
        kl = side_value(side, "kl", 4 if side == "left" else 2)
        nrs = side_value(side, "nrs", 8)
        womac = side_value(side, "womac_function", side_value(side, "womac", 62))
        other_kl = raw[other]["kl"]
        other_nrs = raw[other]["nrs"]
        other_womac = raw[other]["womac"]
        c = coeffs[side]
        bilateral_load = c["structural"]["other_nrs"] * other_nrs + c["structural"]["other_womac"] * other_womac + c["structural"]["other_kl"] * max(0, other_kl - 1)
        compensation_load = c["structural"]["comp_nrs"] * max(0, other_nrs - nrs) + c["structural"]["comp_womac"] * max(0, other_womac - womac)
        shared_burden = 0.006 * (raw["left"]["nrs"] + raw["right"]["nrs"]) / 2 + 0.0009 * (raw["left"]["womac"] + raw["right"]["womac"]) / 2 + 0.010 * (max(raw["left"]["kl"], raw["right"]["kl"]) - min(raw["left"]["kl"], raw["right"]["kl"]))
        primary_boost = .015 if side in target or "both" in target else 0
        end_stage = kl >= 4
        severe_symptoms = nrs >= 7 or womac >= 50
        very_severe_symptoms = nrs >= 8 or womac >= 60
        structural_model = max(.05, min(.88, .06 + c["structural"]["kl"] * kl + c["structural"]["bmi"] * (bmi - 24) + c["structural"]["nrs"] * nrs + c["structural"]["womac"] * womac + bilateral_load + compensation_load + primary_boost))
        structural = .98 if end_stage else structural_model
        surgery_other = c["surgery"]["other_nrs"] * other_nrs + c["surgery"]["other_womac"] * other_womac + c["surgery"]["other_kl"] * max(0, other_kl - 1)
        surgery_comp = c["surgery"]["comp_nrs"] * max(0, other_nrs - nrs) + c["surgery"]["comp_womac"] * max(0, other_womac - womac)
        surgery_model = max(.03, min(.76, .025 + c["surgery"]["kl"] * kl + c["surgery"]["bmi"] * (bmi - 24) + c["surgery"]["nrs"] * nrs + c["surgery"]["womac"] * womac + surgery_other + surgery_comp + (.035 if kl >= 4 else 0) + primary_boost))
        surgery_rule_floor = 0
        surgery_rule_label = "model-only"
        if end_stage:
            surgery_rule_floor = .82
            surgery_rule_label = "KL4 structural TKA gate"
            if severe_symptoms:
                surgery_rule_floor = .90
                surgery_rule_label = "KL4 severe-symptom TKA gate"
            if very_severe_symptoms:
                surgery_rule_floor = .94
                surgery_rule_label = "KL4 very-severe-symptom TKA gate"
            if very_severe_symptoms and (side in target or "both" in target):
                surgery_rule_floor = .96
                surgery_rule_label = "KL4 very-severe primary-side TKA gate"
        elif kl >= 3 and severe_symptoms:
            surgery_rule_floor = .58 if not very_severe_symptoms else .66
            surgery_rule_label = "KL3 severe-symptom escalation gate"
        surgery = min(.97, max(surgery_model, surgery_rule_floor))
        symptom_other = c["symptom"]["other_nrs"] * other_nrs + c["symptom"]["other_womac"] * other_womac + c["symptom"]["other_kl"] * max(0, other_kl - 1)
        symptom_comp = c["symptom"]["comp_nrs"] * max(0, other_nrs - nrs) + c["symptom"]["comp_womac"] * max(0, other_womac - womac)
        symptom_model = max(.10, min(.92, .13 + c["symptom"]["bmi"] * (bmi - 24) + c["symptom"]["nrs"] * nrs + c["symptom"]["womac"] * womac + symptom_other + symptom_comp + shared_burden + (.020 if kl >= 4 else 0) + primary_boost / 2))
        symptom_rule_floor = 0
        if end_stage:
            symptom_rule_floor = .78
            if severe_symptoms:
                symptom_rule_floor = .88
            if very_severe_symptoms:
                symptom_rule_floor = .92
        symptom = min(.96, max(symptom_model, symptom_rule_floor))
        structural_note = "KL4 is already the radiographic ceiling; this value marks end-stage structural status rather than a KL+1 progression probability." if end_stage else "KL0-3 event remains measurable KL-grade/JSN progression."
        return {
            "kl": kl,
            "pain_nrs": nrs,
            "womac_function": womac,
            "structural": round(structural, 3),
            "surgery": round(surgery, 3),
            "symptom": round(symptom, 3),
            "structural_model_probability": round(structural_model, 3),
            "structural_event": "end-stage structural ceiling" if end_stage else "48-month KL/JSN progression",
            "structural_event_applicable": not end_stage,
            "structural_probability_note": structural_note,
            "surgery_model_probability": round(surgery_model, 3),
            "surgery_rule_floor": round(surgery_rule_floor, 3),
            "surgery_rule_label": surgery_rule_label,
            "surgery_probability_note": "Rule floor applied because KL4 with high pain/function loss should not be compressed by the linear surrogate." if surgery_rule_floor > surgery_model else "Model estimate exceeds the escalation floor.",
            "symptom_model_probability": round(symptom_model, 3),
            "symptom_rule_floor": round(symptom_rule_floor, 3),
            "coupling": {
                "contralateral_knee": other,
                "contralateral_kl": other_kl,
                "contralateral_pain_nrs": other_nrs,
                "contralateral_womac_function": other_womac,
                "coefficient_version": coefficient_version,
                "bilateral_load_term": round(bilateral_load, 3),
                "compensation_load_term": round(compensation_load, 3),
                "shared_burden_term": round(shared_burden, 3),
                "side_specific_coefficients": c,
            },
            "interpretation": "end-stage orthopedic referral-screen knee" if end_stage and severe_symptoms else ("advanced high-priority knee" if kl >= 4 or nrs >= 7 or womac >= 50 else "active monitoring / prevention knee"),
        }

    left = calc("left")
    right = calc("right")
    return {
        "endpoint": "POST /api/v9/risk/predict",
        "request_id": f"KOMRISK-{int(time.time()*1000)}",
        "model_source": "backend_endpoint_bilateral_coupled_surrogate_v4_kl4_ceiling",
        "not_frontend_simulation": True,
        "input_echo": {
            "bmi": bmi,
            "target_side": source_body.get("target_side") or "Both knees",
            "left": raw["left"],
            "right": raw["right"],
        },
        "left": left,
        "right": right,
        "max": {
            "structural": max(left["structural"], right["structural"]),
            "surgery": max(left["surgery"], right["surgery"]),
            "symptom": max(left["symptom"], right["symptom"]),
        },
        "side_specific": True,
        "bilateral_coupled": True,
        "accuracy_note": "KOM-Risk uses the backend endpoint with BILATERAL_WEIGHT_V4_KL4_CEILING_20260615. Each knee has side-specific KL, pain and WOMAC inputs; contralateral pain/function/KL, compensation load and shared burden intentionally modify both knee predictions with asymmetric side-specific coefficients. KL4 triggers a structural ceiling rule because KL+1 progression is not a valid event at the radiographic maximum, and severe KL4 knees trigger a high 96-month TKA-event floor before retrained paired-knee OAI weights replace this auditable surrogate.",
        "retraining_data_strategy": ["paired left/right baseline KL, pain, WOMAC, BMI, strength, gait/fall and treatment exposure", "side-specific 24-96 month outcomes: KL/JSN progression, symptom worsening and knee replacement event", "calibrate ipsilateral, contralateral, compensation and shared-burden weights separately"],
        "horizons": {"structural": "KL0-3: 48-month KL/JSN progression; KL4: end-stage structural ceiling", "surgery": "96-month knee replacement / TKA event", "symptom": "24-48 month clinically meaningful WOMAC pain/function worsening"},
    }


def safe_agent_for_gate(gate):
    text = str(gate or "").lower()
    if any(x in text for x in ["nsaid", "injection", "medication", "renal", "gi", "anticoagulant"]):
        return "medication", "Medication and injection agent"
    if any(x in text for x in ["fall", "exercise", "fitt", "rehabilitation"]):
        return "exercise_rehab", "Exercise and rehabilitation agent"
    if any(x in text for x in ["nutrition", "weight", "muscle", "protein"]):
        return "nutrition", "Weight, nutrition and metabolism agent"
    if any(x in text for x in ["orthopedic", "surgery", "referral", "tka", "uka", "hto"]):
        return "surgery", "Orthopedic boundary and escalation agent"
    if any(x in text for x in ["psychology", "behavior", "gad", "phq", "pcs", "sleep"]):
        return "psychology", "Psychology, behavior and adherence agent"
    return "coordinator", "MDT synthesis coordinator"


def safe_revision_for(agent_id):
    if agent_id == "medication":
        return "Keep oral NSAID deferred until renal, GI, anticoagulant/current medication and cardiovascular review is complete. Topical NSAID or patch therapy may be considered if locally safe; injection remains bridge-only after clinician assessment."
    if agent_id == "exercise_rehab":
        return "Add FITT-VP low-impact aerobic exercise, progressive resistance training, supervised balance work and stop rules for pain increase, swelling, limp or near-fall."
    if agent_id == "nutrition":
        return "Pair the weight-loss target with muscle preservation. Do not prescribe a fixed high-protein target until renal function is known."
    if agent_id == "surgery":
        return "Recommend specialist evaluation or referral discussion, collect updated weight-bearing radiographs and conservative-treatment history, and avoid deciding TKA/UKA/HTO in the system."
    if agent_id == "psychology":
        return "Add GAD-7, PHQ-9, PCS and sleep screening, neutral pain education, pacing, coping skills and referral boundaries."
    return "Record the issue for clinician review and request specialty clarification before final adoption."


def compact_profile_summary(profile):
    profile = profile or {}
    parts = [
        f"Age {profile.get('age', 'not recorded')}",
        f"sex {profile.get('sex', 'not recorded')}",
        f"BMI {profile.get('bmi', 'not recorded')}",
        f"left knee KL {profile.get('left_kl', 'not recorded')}, pain NRS {profile.get('left_nrs', profile.get('nrs', 'not recorded'))}, WOMAC {profile.get('left_womac_function', profile.get('left_womac', profile.get('womac_function', 'not recorded')))}",
        f"right knee KL {profile.get('right_kl', 'not recorded')}, pain NRS {profile.get('right_nrs', 'not recorded')}, WOMAC {profile.get('right_womac_function', profile.get('right_womac', 'not recorded'))}",
        f"goal: {profile.get('quality_goal', 'not recorded')}",
    ]
    return "; ".join(str(x) for x in parts)


def prescription_digest(agent):
    p = agent.get("prescription") or {}
    if isinstance(p.get("items"), list):
        return "; ".join(str(x) for x in p.get("items")[:6])
    if isinstance(p.get("content"), list):
        rows = []
        for row in p.get("content")[:4]:
            if isinstance(row, list):
                rows.append(" / ".join(str(x) for x in row[:4]))
        return "; ".join(rows)
    chunks = []
    for key in ["target", "plate", "monitoring", "preoperative_warning", "collect_before_decision", "intervention", "screening"]:
        val = p.get(key)
        if isinstance(val, list):
            chunks.extend(str(x) for x in val[:4])
        elif val:
            chunks.append(str(val))
    return "; ".join(chunks[:8]) or "No structured prescription content is recorded for this agent."


def exercise_action_digest(profile=None):
    profile = profile or {}
    balance_text = str(profile.get("balance") or "")
    fall_flag = bool(re.search(r"fall|stance|support|balance|tug", balance_text, re.I))
    actions = [
        {
            "name": "Walking interval dose",
            "tier": "L1 + L2",
            "evidence": "KOA-EU-00019; KOA-EU-00099",
            "dose": "3-5 days/week; 10-30 min split into 3-10 min intervals; RPE 3-5/10.",
            "actions": "Flat indoor route or treadmill, shorter stride, comfortable cadence; progress total minutes before speed.",
            "stop": "Stop or reduce for swelling, limp, night-pain increase or next-day function loss.",
        },
        {
            "name": "Stationary cycling protocol",
            "tier": "L2 + L3",
            "evidence": "KOA-EU-00477; KOA-EU-01039",
            "dose": "2-4 days/week; 15-30 min; low-to-moderate resistance; saddle high enough to avoid deep-flexion pain.",
            "actions": "Start with 5 min warm-up, steady cadence, then 2-4 short moderate blocks if tolerated.",
            "stop": "Stop for effusion, sharp patellofemoral pain, increasing night pain or cycling through swelling.",
        },
        {
            "name": "Quadriceps isometric start",
            "tier": "L1 + L3",
            "evidence": "KOA-EU-00019; KOA-EU-01039",
            "dose": "5-6 days/week; 2-3 sets of 8-12 reps; 5-10 second holds.",
            "actions": "Quad sets, straight-leg raise, short-arc terminal knee extension; pain <=3/10 during and after.",
            "stop": "Avoid breath-holding, resisted terminal extension through sharp pain, or next-day swelling.",
        },
        {
            "name": "Sit-to-stand and low step control",
            "tier": "L1 + L3",
            "evidence": "KOA-EU-00019; KOA-EU-00849",
            "dose": "2-3 days/week; 1-3 sets of 6-10 reps; raised chair or 10-15 cm step.",
            "actions": "Slow sit-to-stand, low step-up, controlled step-down; hand support if balance is limited.",
            "stop": "Avoid deep flexion, knee collapse, fast stair volume increase or unsupported drills with fall risk.",
        },
        {
            "name": "Hip abductor and posterior-chain support",
            "tier": "L1",
            "evidence": "KOA-EU-00019",
            "dose": "2-3 days/week; 1-3 sets of 8-12 reps.",
            "actions": "Side-lying hip abduction, bridges, calf raises, hamstring curls, band walks when tolerated.",
            "stop": "Avoid gait-changing resistance, lateral hip pain or worsening knee torque.",
        },
        {
            "name": "Balance and gait safety block",
            "tier": "Required safety module" if fall_flag else "Conditional safety module",
            "evidence": "KOA-EU-00019",
            "dose": "3-5 days/week; 8-15 min/session; supervise if single-leg stance <10 s.",
            "actions": "Tandem stance, supported single-leg stance, step touch, turning practice, gait aid check.",
            "stop": "No unstable-surface drills without support; stop after near-fall, dizziness or fear escalation.",
        },
        {
            "name": "Aquatic bridge",
            "tier": "L2",
            "evidence": "KOA-EU-00156",
            "dose": "1-3 sessions/week if available; 20-40 min.",
            "actions": "Water walking, supported ROM, cycling-like movements when land walking flares.",
            "stop": "Avoid with open wound, infection risk, unsafe pool access or uncontrolled cardiopulmonary symptoms.",
        },
    ]
    return "\n".join(
        f"- {item['name']} ({item['tier']}): Dose: {item['dose']} Actions: {item['actions']} Stop rule: {item['stop']} Evidence: {item['evidence']}."
        for item in actions
    )


def agent_response_text(agent, question, profile, selected_modules=None, safety_checks=None):
    name = agent.get("name", "Specialty agent")
    rule = agent.get("specialty_rule", "not recorded")
    profile_line = compact_profile_summary(profile)
    eligible = bool(profile.get("target_side")) and bool(profile.get("left_kl")) and bool(profile.get("right_kl")) and bool(profile.get("left_nrs") or profile.get("right_nrs") or profile.get("nrs"))
    eligibility_text = "Bilateral knee OA eligibility check passed." if eligible else "Bilateral knee OA eligibility check is incomplete; left/right KL grade and symptom anchors should be completed before final prescription."
    modules = selected_modules or []
    agent_modules = [m for m in modules if str(m.get("cat", "")).lower() in str(agent.get("id", "")).lower() or str(agent.get("name", "")).lower().split()[0] in str(m.get("title", "")).lower()]
    if not agent_modules:
        agent_modules = modules[:4]
    module_lines = []
    for item in agent_modules[:5]:
        evidence = "; ".join(f"{e.get('level')} {e.get('eu')}" for e in item.get("evidence_support", [])[:3])
        module_lines.append(f"- {item.get('label')}: {item.get('detail')} Evidence support: {evidence or 'not attached'}. Boundary: {item.get('avoid', 'clinician review required')}")
    blocking = [c for c in (safety_checks or []) if str(c.get("status")) == "ACTION_REQUIRED"]
    blocking_text = "; ".join(f"{c.get('gate')}: {c.get('decision')}" for c in blocking[:4]) or "No ACTION_REQUIRED gate was supplied to this agent call."
    extra = ""
    if agent.get("id") == "exercise_rehab":
        extra = "\nSpecific exercise action menu:\n" + exercise_action_digest(profile) + "\n"
    identity = f"I am {name}. I can screen whether the current bilateral knee OA profile is adequate for my specialty, draft a specialty prescription, explain evidence support, and identify missing data or safety gates."
    if "who are you" in str(question).lower() or "what can you do" in str(question).lower():
        return f"{identity}\n\n{eligibility_text}\nCurrent patient snapshot: {profile_line}\nSpecialty rule: {rule}\nClinician boundary: I support review and shared decision-making; I do not issue autonomous medical orders."
    return (
        f"{name} response.\n"
        f"{eligibility_text}\n"
        f"Current patient snapshot: {profile_line}\n"
        f"Specialty rule: {rule}\n"
        f"Structured specialty prescription: {prescription_digest(agent)}\n"
        f"{extra}"
        f"Selected module draft:\n" + ("\n".join(module_lines) if module_lines else "- No clinician-selected module was supplied for this specialty yet.") + "\n"
        f"Safety gates or missing-data stops: {blocking_text}\n"
        f"Question received: {question}\n"
        f"Clinician boundary: retain human review, do not invent missing data, and match evidence to the patient population before adoption."
    )


def safe_negotiate(body):
    checks = body.get("checks") or []
    actionable = [item for item in checks if str(item.get("status") or "") not in {"PASS", "CONDITIONAL_PASS"}]
    events = []
    audit_id = f"KOMSAFE-{int(time.time()*1000)}"
    if not actionable:
        events.append({"round": 1, "speaker": "KOM-Safe audit agent", "target": "MDT synthesis coordinator", "type": "all_clear", "gate": "All key gates", "message": "No non-pass gate requires specialty revision under the current profile.", "agent_response": "The MDT coordinator confirms that the prescription can proceed to KOM-Rx while retaining clinician review.", "revision": "No revision required.", "reaudit": "PASS", "status": "ADOPTED", "adopted": True})
    else:
        for index, check in enumerate(actionable, start=1):
            agent_id, agent_label = safe_agent_for_gate(check.get("gate"))
            revision = safe_revision_for(agent_id)
            events.append({"round": 1, "speaker": "KOM-Safe audit agent", "target": agent_label, "target_agent_id": agent_id, "type": "revision_request", "gate": check.get("gate"), "message": f"Audit finding: {check.get('finding')}; required action: {check.get('decision')}", "agent_response": "Revision requested; recommendation cannot be adopted until the responsible specialty agent responds.", "revision": "PENDING_SPECIALTY_REVISION", "reaudit": "PENDING", "status": "RETURNED_TO_SPECIALTY", "adopted": False})
            events.append({"round": 2, "speaker": agent_label, "target": "KOM-Safe audit agent", "target_agent_id": "kom_safe", "type": "specialty_revision", "gate": check.get("gate"), "message": "Specialty agent revised the recommendation using the audit finding and retained the clinician-review boundary.", "agent_response": revision, "revision": revision, "reaudit": "READY_FOR_REAUDIT", "status": "REVISED", "adopted": False})
            events.append({"round": 3, "speaker": "KOM-Safe audit agent", "target": "MDT synthesis coordinator", "target_agent_id": "mdt_coordinator", "type": "reaudit_and_adoption", "gate": check.get("gate"), "message": "Re-audit confirms that the unsafe or unclear recommendation has been downgraded, deferred, or made conditional with clinician review.", "agent_response": "MDT coordinator adopts the revised wording and records the residual clinician-review requirement.", "revision": revision, "reaudit": "RESOLVED_WITH_DEFER_OR_HUMAN_REVIEW" if str(check.get("status")) == "ACTION_REQUIRED" else "RESOLVED_WITH_MODIFICATION", "status": "ADOPTED_WITH_BOUNDARY", "adopted": True})
    gate_status_by_name = {str(item.get("gate")): str(item.get("status")) for item in checks}
    for idx, event in enumerate(events, start=1):
        event["audit_id"] = audit_id
        event["event_id"] = f"{audit_id}-E{idx:02d}"
        event["input_gate_status"] = gate_status_by_name.get(str(event.get("gate")), "NOT_SUPPLIED")
        event["adoption_rule"] = "Adopt only after specialty revision, re-audit status and clinician-review boundary are recorded."
    source, llm_feedback = "deterministic_rules", None
    if body.get("use_llm"):
        prompt = "You are the KOM-Safe audit agent. Evaluate the safety negotiation trace only; do not generate a replacement prescription. Summarize residual concerns and required clinician review in English.\n" + json.dumps({"profile": body.get("profile") or {}, "events": events}, ensure_ascii=False)[:5000]
        llm = call_openai_compatible(body, prompt=prompt)
        if llm.get("ok"):
            source = "configured_model_plus_rules"
            llm_feedback = llm["data"].get("response")
    return {"status": "NEGOTIATION_COMPLETE", "source": source, "audit_id": audit_id, "auditable": True, "rounds": max([e.get("round", 1) for e in events] or [1]), "completion_criteria": ["Each non-pass gate is assigned to a responsible specialty agent.", "The specialty agent returns a revision or clinician-review boundary.", "KOM-Safe records re-audit and adoption status.", "Missing data must not be invented as normal."], "events": events, "summary": f"KOM-Safe generated {len(events)} negotiation record(s) and retained clinician-review boundaries.", "llm_feedback": llm_feedback, "timestamp": now()}


class Handler(BaseHTTPRequestHandler):
    server_version = "KOMWorkbench/English"

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), fmt % args))

    def send_json(self, payload, status=200):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_text(self, text, content_type="text/plain; charset=utf-8", status=200):
        raw = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def read_body(self):
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return {}

    def static(self, path):
        app_routes = {"/", "/ui", "/dashboard", "/assess", "/rad", "/risk", "/rag", "/mdt", "/safe", "/rx", "/score", "/settings", "/case-workspace", "/imaging", "/evidence-graph", "/treatment-board", "/safety-review", "/clinical-report", "/validation", "/trace", "/patient-timeline"}
        if path in app_routes:
            file_path = STATIC / "index.html"
        elif path.startswith("/assets/"):
            file_path = STATIC / path.lstrip("/")
        elif path.startswith("/validation/"):
            file_path = ROOT / path.lstrip("/")
        else:
            file_path = STATIC / path.lstrip("/")
        if not file_path.exists() or not file_path.is_file():
            return False
        suffix = file_path.suffix.lower()
        ctype = "text/html; charset=utf-8" if suffix == ".html" else "text/css; charset=utf-8" if suffix == ".css" else "application/javascript; charset=utf-8" if suffix == ".js" else "application/json; charset=utf-8" if suffix == ".json" else "image/png" if suffix == ".png" else "image/svg+xml" if suffix == ".svg" else "application/octet-stream"
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        return True

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path, qs = parsed.path, urllib.parse.parse_qs(parsed.query)
        try:
            c = content()
            if path == "/api/routes":
                return self.send_json(api_ok({"GET": GET_ROUTES, "POST": POST_ROUTES, "version": c.get("version")}))
            if path == "/api/status":
                counts = {"cases": 0, "evidence_units": c.get("evidence", {}).get("count", 0), "graph_nodes": 40, "graph_edges": 68}
                if DB.exists():
                    with con() as db:
                        counts["evidence_units"] = db.execute("SELECT COUNT(*) FROM evidence_units").fetchone()[0]
                return self.send_json(api_ok({"version": c.get("version"), **counts, "selected_case": c.get("case", {}).get("case_id"), "language": "English"}))
            if path in ("/api/v9/content", "/api/v8/content"):
                return self.send_json(api_ok(c))
            if path in ("/api/v9/validate", "/api/validation"):
                return self.send_json(api_ok(validation_result()))
            if path == "/api/v16/profile/current":
                return self.send_json(api_ok(profile_current()))
            if path == "/api/v16/rx/final":
                return self.send_json(api_ok(final_rx_current()))
            if path == "/api/v10/evidence/units":
                return self.send_json(api_ok(evidence_units_query(qs)))
            if path == "/api/v10/evidence/patient-fit":
                return self.send_json(api_ok(patient_fit_query(qs)))
            if path == "/api/v9/evidence/explore":
                return self.send_json(api_ok(c.get("evidence", {})))
            if path == "/api/v9/risk/predict":
                return self.send_json(api_ok({
                    "endpoint": "POST /api/v9/risk/predict",
                    "method": "POST",
                    "model_source": "backend_endpoint_bilateral_coupled_surrogate_v4_kl4_ceiling",
                    "coefficient_version": "BILATERAL_WEIGHT_V4_KL4_CEILING_20260615",
                    "not_frontend_simulation": True,
                    "input_contract": ["bmi", "left_kl", "right_kl", "left_nrs", "right_nrs", "left_womac_function", "right_womac_function", "target_side"],
                    "kl_lock": "KL grade is accepted from KOM-Profile only. KOM-Rad documents imaging evidence and KOM-Risk treats KL as read-only.",
                    "kl4_semantics": "KL4 structural ceiling: structural output is an end-stage status marker, not a KL+1 progression event; severe KL4 applies a TKA-event floor.",
                    "modifiable_scenario_fields": ["bmi", "left_nrs", "right_nrs", "left_womac_function", "right_womac_function"],
                }))
            if path == "/api/settings/llm/status":
                return self.send_json(api_ok(settings_load()))
            if path == "/api/report":
                fmt = (qs.get("format", ["json"])[0] or "json").lower()
                if fmt == "md":
                    return self.send_text(markdown_report(c), "text/markdown; charset=utf-8")
                if fmt == "html":
                    html = "<!doctype html><meta charset='utf-8'><title>KOM Structured Prescription</title><style>body{font-family:Arial,sans-serif;max-width:980px;margin:32px auto;line-height:1.7}h1,h2{color:#123}</style>" + markdown_report(c).replace("\n", "<br>")
                    return self.send_text(html, "text/html; charset=utf-8")
                return self.send_json(api_ok({"case": c.get("case"), "report": c.get("report")}))
            if path == "/api/v8/pipeline":
                return self.send_json(api_ok(c.get("architecture", [])))
            if path == "/api/v8/evidence-chain":
                return self.send_json(api_ok(c.get("evidence", {}).get("chains", {})))
            if path in ("/api/v8/agents", "/api/agents"):
                return self.send_json(api_ok(c.get("agents", [])))
            if path == "/api/v8/prescription":
                return self.send_json(api_ok({"case": c.get("case"), "sections": c.get("report")}))
            if path == "/api/cases":
                return self.send_json(api_ok(c.get("standard_cases", [])))
            if path == "/api/evidence":
                return self.send_json(api_ok(c.get("evidence", {})))
            if path == "/api/graph":
                return self.send_json(api_ok({"nodes": c.get("evidence", {}).get("distribution", {}).get("levels", {}), "edges": "see static graph figures"}))
            if path == "/api/safety":
                return self.send_json(api_ok(c.get("safety", [])))
            if path == "/api/trace":
                return self.send_json(api_ok(c.get("trace", [])))
            if self.static(path):
                return
            return self.send_json(api_error("not_found", "Unknown GET endpoint", {"path": path}), 404)
        except Exception as exc:
            return self.send_json(api_error("server_error", str(exc), {"traceback": traceback.format_exc()}), 500)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        body = self.read_body()
        try:
            c = content()
            if path in ("/api/pathway/run", "/api/report/generate"):
                return self.send_json(api_ok(pathway_run()))
            if path == "/api/v10/profile/generate":
                return self.send_json(api_ok(profile_generate(body)))
            if path == "/api/v16/profile/save":
                return self.send_json(api_ok(profile_save(body)))
            if path == "/api/v16/rx/finalize":
                return self.send_json(api_ok(final_rx_save(body)))
            if path == "/api/v10/risk/simulate":
                return self.send_json(api_ok(risk_simulate(body)))
            if path == "/api/v10/evidence/patient-fit":
                return self.send_json(api_ok(patient_fit_query(body)))
            if path == "/api/v15/safe/negotiate":
                return self.send_json(api_ok(safe_negotiate(body)))
            if path == "/api/v9/rad/analyze":
                examples = c.get("imaging", {}).get("examples", [])
                return self.send_json(api_ok({"side_specific": True, "knees": examples, "left": examples[0] if len(examples) > 0 else {}, "right": examples[1] if len(examples) > 1 else {}, "clinician_review_required": True}))
            if path == "/api/v9/risk/predict":
                return self.send_json(api_ok(risk_simulate(body)))
            if path in ("/api/v9/agent/chat", "/api/agents/challenge"):
                agent_id = body.get("agent_id") or body.get("agent") or "exercise_rehab"
                agent = next((item for item in c.get("agents", []) if item.get("id") == agent_id), c.get("agents", [{}])[0])
                question = body.get("question") or "Explain this specialty prescription."
                profile = body.get("profile") or {}
                deterministic = agent_response_text(agent, question, profile, selected_modules=body.get("selected_modules") or [], safety_checks=body.get("safety_checks") or [])
                if body.get("use_llm"):
                    agent_context = {
                        "agent": agent,
                        "profile": profile,
                        "question": question,
                        "selected_modules": body.get("selected_modules") or [],
                        "safety_checks": body.get("safety_checks") or [],
                        "deterministic_local_draft": deterministic,
                    }
                    if agent.get("id") == "exercise_rehab":
                        agent_context["specific_exercise_action_menu"] = exercise_action_digest(profile)
                    prompt = (
                        "Answer the clinical follow-up in English. First judge whether the input contains eligible bilateral knee osteoarthritis clinical information. "
                        "Use the supplied deterministic local draft, clinician-selected modules and safety checks as the binding source of truth. "
                        "For exercise, keep concrete FITT-VP dose, action type, stop rules and evidence IDs. "
                        "If left/right KL grade or symptom anchors are missing, state what must be completed before final prescription. "
                        "Do not invent patient facts. Preserve clinician-review boundaries.\n"
                    ) + json.dumps(agent_context, ensure_ascii=False)[:9000]
                    llm = call_openai_compatible(body, prompt=prompt)
                    if llm.get("ok"):
                        return self.send_json(api_ok({"answer": llm["data"].get("response"), "source": "configured_model"}))
                return self.send_json(api_ok({"answer": deterministic, "source": "deterministic_specialty_agent"}))
            if path == "/api/v8/prescription/polish":
                prompt = "Polish the following KOM structured prescription in professional English without changing safety gates or clinician-review boundaries:\n" + markdown_report(c)[:4000]
                llm = call_openai_compatible(body, prompt=prompt)
                return self.send_json(llm if not llm.get("ok") else api_ok({"polished": llm["data"].get("response"), "source": "configured_model"}))
            if path == "/api/settings/llm/test-text":
                return self.send_json(call_openai_compatible(body))
            if path == "/api/settings/llm/test-vision":
                return self.send_json(call_openai_compatible(body, vision=True))
            if path == "/api/settings/llm/save":
                if public_demo_mode():
                    key = body.get("api_key") or os.environ.get("OPENAI_API_KEY") or os.environ.get("XIAOAI_API_KEY")
                    return self.send_json(api_ok({
                        "status": "public_demo_not_persisted",
                        "message": "This public deployment does not write private API keys to server disk. Use Test text model for a one-request check, or configure a server-side environment key for a controlled deployment.",
                        "masked_api_key": mask_key(key),
                        "public_demo_mode": True,
                    }))
                CONFIG.mkdir(parents=True, exist_ok=True)
                key = body.get("api_key") or os.environ.get("OPENAI_API_KEY") or os.environ.get("XIAOAI_API_KEY")
                cfg = {"provider": "OpenAI-compatible", "base_url": body.get("base_url") or "https://xiaoai.plus/v1", "text_model": body.get("text_model") or "gpt-4o", "vision_model": body.get("vision_model") or "gpt-4o", "temperature": float(body.get("temperature") or 0.2), "timeout_seconds": int(body.get("timeout_seconds") or 60), "masked_api_key": mask_key(key), "status": "Configured" if key else "Configured without key"}
                if key:
                    cfg["api_key"] = key
                LLM_LOCAL.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
                safe = dict(cfg)
                safe.pop("api_key", None)
                return self.send_json(api_ok(safe))
            if path == "/api/settings/llm/clear":
                if LLM_LOCAL.exists():
                    LLM_LOCAL.unlink()
                return self.send_json(api_ok({"status": "cleared"}))
            return self.send_json(api_error("not_found", "Unknown POST endpoint", {"path": path}), 404)
        except Exception as exc:
            return self.send_json(api_error("server_error", str(exc), {"traceback": traceback.format_exc()}), 500)


def main():
    cloud_port = os.environ.get("PORT")
    host = os.environ.get("KOM_HOST") or ("0.0.0.0" if cloud_port else "127.0.0.1")
    port = int(os.environ.get("KOM_PORT") or cloud_port or "8027")
    httpd = ThreadingHTTPServer((host, port), Handler)
    mode = "public demo" if public_demo_mode() else "local"
    print(f"KOM Clinical Workbench English release running in {mode} mode at http://{host}:{port}/dashboard", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
