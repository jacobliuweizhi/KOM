from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "app" / "data"
DB = DATA / "kom_workbench.sqlite"
JSONL = DATA / "evidence_units.jsonl"
CONTENT = DATA / "v9_workbench_content.json"
REPORT = DATA / "evidence_enrichment_report_v19.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def level_code(value: str) -> str:
    m = re.search(r"L[1-7]", str(value or ""))
    if m:
        return m.group(0)
    text = str(value or "").lower()
    if "guideline" in text:
        return "L1"
    if "meta" in text or "systematic review" in text:
        return "L2"
    if "rct" in text or "random" in text or "trial" in text:
        return "L3"
    return "L7"


def sample_size(*texts: str) -> str:
    text = " ".join(str(x or "") for x in texts)
    patterns = [
        r"sample size:\s*([0-9,]+)",
        r"\bn\s*=\s*([0-9,]+)",
        r"([0-9,]+)\s+participants",
        r"([0-9,]+)\s+patients",
        r"([0-9,]+)\s+adults",
        r"([0-9,]+)\s+randomi[sz]ed controlled trials",
        r"([0-9,]+)\s+RCTs",
        r"([0-9,]+)\s+studies",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return m.group(1).replace(",", "")
    return "not encoded"


def infer_stage(title: str, domain: str) -> str:
    s = f"{title} {domain}".lower()
    if any(x in s for x in ["arthroplasty", "replacement", "postoperative", "preoperative"]):
        return "advanced OA or arthroplasty pathway"
    if any(x in s for x in ["early", "prevention"]):
        return "early OA or prevention pathway"
    if any(x in s for x in ["obes", "weight", "bmi"]):
        return "symptomatic OA with overweight/obesity context"
    if any(x in s for x in ["exercise", "walking", "cycling", "strength", "aquatic"]):
        return "symptomatic knee OA rehabilitation context"
    return "symptomatic or radiographic knee OA context"


def infer_intervention(title: str, domain: str, current: str) -> str:
    s = f"{title} {domain} {current}".lower()
    mapping = [
        ("semaglutide", "semaglutide 2.4 mg once weekly plus lifestyle intervention"),
        ("cycling", "stationary or low-impact cycling exercise"),
        ("walking", "walking, treadmill, gait, or aerobic walking intervention"),
        ("aquatic", "aquatic exercise or water-based low-impact training"),
        ("strength", "progressive resistance or quadriceps/hip strengthening"),
        ("neuromuscular", "neuromuscular and balance-oriented exercise"),
        ("balance", "balance, fall-prevention, or gait-control training"),
        ("weight loss", "weight-loss intervention with muscle-preservation boundary"),
        ("obes", "obesity or BMI-targeted exposure/intervention"),
        ("hyaluronic", "intra-articular hyaluronic acid or sodium hyaluronate"),
        ("platelet", "platelet-rich plasma injection protocol"),
        ("corticosteroid", "intra-articular corticosteroid injection"),
        ("nsaid", "topical or oral NSAID medication strategy"),
        ("arthroplasty", "orthopedic referral or arthroplasty pathway exposure"),
        ("self-management", "education, self-management, pacing, and adherence support"),
        ("cognitive", "psychological, cognitive, coping, or behavioral intervention"),
    ]
    for key, value in mapping:
        if key in s:
            return value
    if current and current.lower() not in {"not applicable", "unknown"}:
        return current
    return "intervention or exposure described by the source title and evidence domain"


def signal_direction(*texts: str) -> str:
    s = " ".join(str(x or "") for x in texts).lower()
    if any(x in s for x in ["negative", "harm", "worse", "bleed", "infection", "adverse"]):
        return "negative or safety-limited signal"
    positive = any(x in s for x in ["positive", "improv", "benefit", "reduce", "superior", "effective"])
    mixed = any(x in s for x in ["mixed", "null", "no superiority", "no difference", "inconsistent"])
    if positive and mixed:
        return "positive primary signal with mixed or neutral secondary findings"
    if positive:
        return "positive signal"
    if mixed:
        return "mixed or neutral signal"
    return "direction not explicit in local metadata"


def effect_status(row: dict) -> str:
    title = row.get("Title", "")
    pop = row.get("P_Population", "")
    outcomes = row.get("O_Outcomes", "")
    effect = row.get("Effect_Summary", "")
    sample = sample_size(title, pop, outcomes, effect)
    direction = signal_direction(title, outcomes, effect)
    existing = str(effect or "").strip()
    has_numeric = bool(re.search(r"(MD|SMD|RR|OR|HR|CI|%|WOMAC|VAS|KOOS|P\s*[<=>])", existing, re.I) and re.search(r"\d", existing))
    generic = any(
        phrase in existing.lower()
        for phrase in [
            "anchor rule",
            "evidence synthesis: use to rank",
            "supportive evidence: retain",
            "protocol/background only",
            "retrieves",
        ]
    )
    if has_numeric and not generic:
        return existing
    level = level_code(row.get("Evidence_Level", ""))
    unit = "participant/sample" if sample != "not encoded" else "source-linked unit"
    return (
        f"Quantified metadata abstraction: evidence level {level}; sample/evidence set {sample} {unit}; "
        f"result direction {direction}; exact MD/SMD/RR/CI not encoded in this local row unless stated elsewhere, "
        "so magnitude claims require source-level opening before citation."
    )


def enrich_row(row: dict) -> dict:
    title = row.get("Title") or ""
    domain = row.get("Agent_Database") or ""
    level = level_code(row.get("Evidence_Level") or "")
    stage = infer_stage(title, domain)
    sample = sample_size(title, row.get("P_Population", ""), row.get("O_Outcomes", ""), row.get("Effect_Summary", ""))
    population = row.get("P_Population") or "Adults with knee osteoarthritis"
    if "Population detail:" not in population:
        population = (
            f"{population}; Population detail: adults with knee OA or mixed OA including knee OA; "
            f"stage/phenotype: {stage}; sample/evidence set: {sample}; extraction status: local DOI/PMID metadata enriched."
        )
    intervention = infer_intervention(title, domain, row.get("I_Intervention") or "")
    outcomes = row.get("O_Outcomes") or "pain, function, physical performance, structure, safety, adherence, or implementation outcome"
    direction = signal_direction(title, outcomes, row.get("Effect_Summary", ""))
    if "Signal direction:" not in outcomes:
        outcomes = f"{outcomes}; Signal direction: {direction}."
    prescription = row.get("Prescription_Use") or ""
    if "Evidence-use tier:" not in prescription:
        tier = {"L1": "guideline boundary", "L2": "synthesis ranking", "L3": "trial calibration", "L4": "patient-fit/risk context", "L5": "implementation context", "L6": "protocol/background", "L7": "background only"}.get(level, "context")
        prescription = f"{prescription}; Evidence-use tier: {tier}; patient-fit, safety gates and clinician review required."
    row.update(
        {
            "P_Population": population,
            "I_Intervention": intervention,
            "O_Outcomes": outcomes,
            "Effect_Summary": effect_status({**row, "O_Outcomes": outcomes}),
            "Prescription_Use": prescription,
            "source_status": "V19 enriched local Evidence Unit: source identifier retained; PICO, signal direction and effect-availability status completed.",
            "updated_at": now_iso(),
        }
    )
    return row


SEMAGLUTIDE_ROW = {
    "EU_ID": "KOA-EU-STEP9-2024",
    "Article_Key": "doi:10.1056/NEJMoa2403664",
    "Agent_Database": "nutrition_weight_management;weight_management;pharmacologic_or_injection",
    "Title": "Once-weekly semaglutide in persons with obesity and knee osteoarthritis",
    "Evidence_Level": "L3 Randomized or interventional study",
    "KOA_Relevance_Grade": "Included - obesity phenotype with knee OA",
    "Traceability_Status": "Source traceable: DOI",
    "P_Population": "407 adults with obesity and moderate knee osteoarthritis in a 68-week double-blind randomized trial; BMI obesity indication; Population detail: symptomatic moderate knee OA with obesity; sample/evidence set: 407; extraction status: DOI/PubMed verified targeted abstraction.",
    "I_Intervention": "semaglutide 2.4 mg once weekly subcutaneous injection plus lifestyle intervention",
    "C_Comparator": "placebo injection plus lifestyle intervention",
    "O_Outcomes": "body-weight percent change, WOMAC pain score, and physical function; Signal direction: positive signal.",
    "Effect_Summary": "Targeted quantitative abstraction: at week 68, body weight changed -13.7% with semaglutide vs -3.2% with placebo; WOMAC pain changed -41.7 vs -27.5 points; between-group differences were statistically significant (P<0.001).",
    "Safety_or_Contraindication_Note": "Use as obesity pharmacotherapy, not as an autonomous OA analgesic; review pregnancy, pancreatitis/gallbladder disease, MEN2/MTC contraindication, GI adverse effects, cost/coverage and continuation plan.",
    "Prescription_Use": "B: special-population obesity-treatment option for BMI/obesity-eligible knee OA patients; requires prescribing clinician review and lifestyle co-intervention.",
    "source_link": "https://doi.org/10.1056/NEJMoa2403664",
    "year": 2024,
    "source_status": "V19 targeted DOI/PubMed abstraction added for semaglutide STEP 9.",
    "trace_id": "trace-eu-step9-2024",
    "created_at": now_iso(),
    "updated_at": now_iso(),
    "raw_json": json.dumps({"verified_sources": ["NEJM DOI 10.1056/NEJMoa2403664", "PubMed PMID 39476339"]}, ensure_ascii=False),
}


def main() -> None:
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    rows = [dict(r) for r in db.execute("SELECT * FROM evidence_units ORDER BY id").fetchall()]
    columns = [r[1] for r in db.execute("PRAGMA table_info(evidence_units)").fetchall()]
    max_id = max((int(r.get("id") or 0) for r in rows), default=0)
    existing_ids = {r["EU_ID"] for r in rows}
    enriched = [enrich_row(r) for r in rows]
    inserted_semaglutide = False
    if SEMAGLUTIDE_ROW["EU_ID"] not in existing_ids:
        row = dict(SEMAGLUTIDE_ROW)
        row["id"] = max_id + 1
        enriched.append(row)
        inserted_semaglutide = True
    else:
        enriched = [SEMAGLUTIDE_ROW | r if r["EU_ID"] == SEMAGLUTIDE_ROW["EU_ID"] else r for r in enriched]

    with db:
        for row in enriched:
            values = {k: row.get(k) for k in columns if k != "id"}
            if row.get("EU_ID") in existing_ids:
                set_clause = ", ".join(f"{k}=?" for k in values)
                db.execute(f"UPDATE evidence_units SET {set_clause} WHERE EU_ID=?", list(values.values()) + [row["EU_ID"]])
            else:
                insert_cols = ["id"] + [k for k in columns if k != "id"]
                db.execute(
                    f"INSERT INTO evidence_units ({', '.join(insert_cols)}) VALUES ({', '.join(['?'] * len(insert_cols))})",
                    [row.get(k) for k in insert_cols],
                )

    final_rows = [dict(r) for r in db.execute("SELECT * FROM evidence_units ORDER BY id").fetchall()]
    JSONL.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in final_rows) + "\n", encoding="utf-8")

    content = json.loads(CONTENT.read_text(encoding="utf-8"))
    old_count = int(content.get("evidence", {}).get("count", 0) or 0)
    content["version"] = "KOM_LOCAL_CLINICAL_WORKBENCH_PERSISTENT_RX_EVIDENCE_20260615"
    content["release_status"] = "PERSISTENT_RX_EVIDENCE_CLINICAL_RELEASE"
    content["evidence"]["count"] = len(final_rows)
    if inserted_semaglutide:
        levels = content["evidence"].setdefault("distribution", {}).setdefault("levels", {})
        levels["L3"] = int(levels.get("L3", 0)) + 1

    sem_item = {
        "EU_ID": SEMAGLUTIDE_ROW["EU_ID"],
        "title": SEMAGLUTIDE_ROW["Title"],
        "level": "L3",
        "year": 2024,
        "summary": "STEP 9 RCT: semaglutide 2.4 mg weekly plus lifestyle reduced body weight and WOMAC pain more than placebo in adults with obesity and moderate knee OA.",
        "why_selected": "Adds a special-population pharmacologic obesity pathway when BMI/obesity indication fits the patient.",
        "source_link": SEMAGLUTIDE_ROW["source_link"],
        "database_domain": SEMAGLUTIDE_ROW["Agent_Database"],
        "full_evidence_level": SEMAGLUTIDE_ROW["Evidence_Level"],
        "P_Population": SEMAGLUTIDE_ROW["P_Population"],
        "I_Intervention": SEMAGLUTIDE_ROW["I_Intervention"],
        "C_Comparator": SEMAGLUTIDE_ROW["C_Comparator"],
        "O_Outcomes": SEMAGLUTIDE_ROW["O_Outcomes"],
        "Effect_Summary": SEMAGLUTIDE_ROW["Effect_Summary"],
        "Safety_or_Contraindication_Note": SEMAGLUTIDE_ROW["Safety_or_Contraindication_Note"],
        "Prescription_Use": SEMAGLUTIDE_ROW["Prescription_Use"],
        "validation": "Targeted source abstraction: NEJM/PubMed verified; use as obesity-treatment module with clinician prescribing boundary.",
        "directness": "Direct supporting evidence for selected obese knee OA phenotype",
    }
    chain = content["evidence"]["chains"].get("nutrition_weight_management")
    if chain:
        layer = next((x for x in chain["layers"] if "RCT" in x["name"] or "Clinical" in x["name"]), None)
        if layer and not any(i.get("EU_ID") == SEMAGLUTIDE_ROW["EU_ID"] for i in layer["items"]):
            layer["items"].insert(0, sem_item)
    pharm = content["evidence"]["chains"].get("pharmacologic_or_injection")
    if pharm:
        layer = next((x for x in pharm["layers"] if "RCT" in x["name"] or "Clinical" in x["name"]), None)
        if layer and not any(i.get("EU_ID") == SEMAGLUTIDE_ROW["EU_ID"] for i in layer["items"]):
            layer["items"].insert(0, sem_item)

    for case in content.get("standard_cases", []):
        case.setdefault("burden_label", {"early_education": "Low burden", "active_rehab": "Low burden", "medical_complex": "High burden", "surgical_referral": "High burden"}.get(case["id"], "Burden"))
        case.setdefault("demand_label", {"early_education": "Low demand", "active_rehab": "High demand", "medical_complex": "Low demand", "surgical_referral": "High demand"}.get(case["id"], "Demand"))

    CONTENT.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {
        "status": "completed",
        "previous_content_count": old_count,
        "final_database_count": len(final_rows),
        "rows_enriched": len(rows),
        "semaglutide_step9_added": inserted_semaglutide,
        "evidence_unit_contract": [
            "P_Population includes population detail, stage/phenotype, sample/evidence-set status.",
            "I_Intervention states concrete intervention or exposure where inferable.",
            "O_Outcomes includes signal direction.",
            "Effect_Summary includes quantitative abstraction or exact-effect-availability status.",
            "Prescription_Use states evidence-use tier and clinician/safety boundary.",
        ],
        "limitations": "The all-row pass is deterministic local metadata enrichment. STEP 9 was targeted-source abstracted; remaining rows retain DOI/PMID links and mark when exact effect size is not encoded locally.",
        "generated_at": now_iso(),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
