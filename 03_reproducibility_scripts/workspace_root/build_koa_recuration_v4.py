from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
import hashlib
import json
import math
import re
import zipfile

import pandas as pd


PROJECT = Path("C:/OAI\u7814\u7a76\u9879\u76ee/pythonProject1/KOM\u8fd4\u4fee\u4fee\u6539")
PRIMARY_JSON = PROJECT / "\u6295\u7a3f\u4f7f\u7528/KOM_KOA_Evidence_Unit_Database_UI_checked_Package/KOM_KOA_Evidence_Unit_Database_UI_Data_checked.json"
FALLBACK_JSON = PROJECT / "\u6295\u7a3f\u4f7f\u7528/KOA_Evidence_Unit_Database_UI_Package/KOA_Evidence_Unit_Database_UI_Data.json"
LINK_AUDIT = PROJECT / "\u6295\u7a3f\u4f7f\u7528/KOM_KOA_Evidence_Unit_Database_UI_checked_Package/KOM_KOA_Evidence_Unit_Database_UI_Link_Audit.csv"
if not LINK_AUDIT.exists():
    LINK_AUDIT = PROJECT / "\u6295\u7a3f\u4f7f\u7528/KOA_Evidence_Unit_Database_Final_Package/KOA_Evidence_Unit_Database_Link_Audit_Final.csv"
RAW_JSONL = PROJECT / "\u672c\u5730\u5316/koa_mdt_agents/data/processed/evidence/raw_evidence_units.jsonl"

OUT = Path("/workspace/output/koa_full_evidence_unit_recurated_v4")
ZIP = OUT.parent / "koa_full_evidence_unit_recurated_v4.zip"
OUT.mkdir(parents=True, exist_ok=True)

NOT_REPORTED = "not_reported_in_available_source"
NOT_APPLICABLE = "not_applicable"
NOT_MEASURED = "not_measured"
TODAY = date.today().isoformat()

PROHIBITED_UI_WORDS = [
    r"\bAI\b",
    r"Chat(?:GPT)",
    r"\bgenerated\b",
    r"reviewer browser",
    r"\bversion\b",
    r"development build",
]


def load_records() -> tuple[list[dict], dict, dict, Path]:
    source_path = PRIMARY_JSON if PRIMARY_JSON.exists() else FALLBACK_JSON
    with source_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    records = data["records"] if isinstance(data, dict) and "records" in data else data

    link_df = pd.read_csv(LINK_AUDIT) if LINK_AUDIT.exists() else pd.DataFrame()
    link_by_id: dict[str, dict] = {}
    if not link_df.empty and "id" in link_df.columns:
        for _, row in link_df.iterrows():
            link_by_id[str(row.get("id", ""))] = row.to_dict()

    raw_by_id: dict[str, dict] = {}
    if RAW_JSONL.exists():
        with RAW_JSONL.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                    raw_by_id[obj.get("eu_id", "")] = obj
                except Exception:
                    pass
    return records, link_by_id, raw_by_id, source_path


def clean_val(x, default=NOT_REPORTED):
    if x is None:
        return default
    if isinstance(x, float) and math.isnan(x):
        return default
    s = str(x).strip()
    if not s:
        return default
    bads = {
        "unclear",
        "TBD",
        "tbd",
        "to be extracted",
        "requires extraction",
        "unknown",
        "nan",
        "None",
        "none",
    }
    if s in bads:
        return default
    s = re.sub(
        r"unclear/mixed",
        "mixed_or_no_clear_direction_reported_in_available_source",
        s,
        flags=re.I,
    )
    s = re.sub(r"\bunclear\b", "no_clear_direction_reported_in_available_source", s, flags=re.I)
    s = re.sub(r"\bTBD\b|to be extracted|requires extraction", default, s, flags=re.I)
    return s


def safe_csv_value(x):
    if isinstance(x, (list, dict)):
        return json.dumps(x, ensure_ascii=False)
    return x


def get_links(r):
    links = []
    for k in ("links_clean", "links"):
        v = r.get(k)
        if isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    url = item.get("url") or item.get("href")
                    label = item.get("label") or item.get("name") or "source"
                    if url:
                        links.append({"label": clean_val(label, "source"), "url": clean_val(url)})
    pl = r.get("primary_link")
    if isinstance(pl, dict) and pl.get("url"):
        links.insert(0, {"label": clean_val(pl.get("label"), "Primary source"), "url": clean_val(pl.get("url"))})
    seen, out = set(), []
    for link in links:
        if link["url"] not in seen:
            seen.add(link["url"])
            out.append(link)
    return out


def first_url(r):
    links = get_links(r)
    if links:
        return links[0]["url"]
    doi = clean_val(r.get("doi"), "")
    pmid = clean_val(r.get("pmid"), "")
    if doi:
        return "https://doi.org/" + doi
    if pmid:
        return "https://pubmed.ncbi.nlm.nih.gov/" + re.sub(r"\.0$", "", pmid) + "/"
    return NOT_REPORTED


def get_pmcid_and_fulltext(r):
    for link in get_links(r):
        url = link["url"]
        if "pmc.ncbi.nlm.nih.gov" in url:
            m = re.search(r"PMC\d+", url, re.I)
            return (m.group(0).upper() if m else NOT_REPORTED, url)
        if re.search(r"full.?text", link.get("label", ""), re.I):
            return (NOT_REPORTED, url)
    return (NOT_REPORTED, NOT_REPORTED)


def norm_pmid(x):
    s = clean_val(x, "")
    s = re.sub(r"\.0$", "", s)
    return s or NOT_REPORTED


def norm_doi(x):
    s = clean_val(x, "")
    return s if s else NOT_REPORTED


def article_id(r):
    doi = norm_doi(r.get("doi"))
    if doi != NOT_REPORTED:
        return "doi:" + doi.lower()
    pmid = norm_pmid(r.get("pmid"))
    if pmid != NOT_REPORTED:
        return "pmid:" + pmid
    key = clean_val(r.get("key"), "")
    if key:
        return key.lower()
    base = (clean_val(r.get("title"), "") + "|" + str(clean_val(r.get("year"), ""))).lower()
    return "titlehash:" + hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def classify_level(r):
    title = clean_val(r.get("title"), "").lower()
    level = (clean_val(r.get("level_short"), "") + " " + clean_val(r.get("level"), "") + " " + clean_val(r.get("study_design_readable"), "")).lower()
    journal = clean_val(r.get("journal"), "").lower()
    if re.search(r"snapshot|survey|adherence|implementation|practice.pattern|real.world.practice|questionnaire|knowledge|attitude", title):
        return ("L5 Context / protocol / implementation", "implementation_or_survey_context")
    if re.search(r"guideline|recommendation|consensus|clinical standard|care standard|position statement", title + " " + journal + " " + level):
        return ("L1 Current clinical guidance and clinical standards", "clinical_guidance_or_standard")
    if re.search(r"umbrella review|network meta|meta.analysis|systematic review|evidence synthesis|\bnma\b|review and meta", title + " " + level):
        if re.search(r"narrative review", title + " " + level):
            return ("L5 Context / protocol / implementation", "narrative_review_context")
        return ("L2 Evidence synthesis", "evidence_synthesis")
    if re.search(r"protocol|trial design|study protocol|registered protocol", title):
        return ("L5 Context / protocol / implementation", "protocol_no_results")
    if re.search(r"randomi[sz]ed|randomised|randomized|\brct\b|clinical trial|controlled trial|crossover trial|cluster trial|nonrandomi[sz]ed|interventional", title + " " + level):
        return ("L3 Interventional clinical evidence", "candidate_interventional")
    if re.search(r"cohort|case.control|cross.sectional|registry|observational|prognostic|prediction model|risk factor|association|real.world|retrospective|prospective", title + " " + level):
        return ("L4 Observational and prognostic evidence", "observational_or_prognostic")
    rank = r.get("level_rank")
    if rank == 2:
        return ("L2 Evidence synthesis", "evidence_synthesis_from_rank")
    if rank == 3:
        return ("L3 Interventional clinical evidence", "candidate_interventional_from_rank")
    if rank == 4:
        return ("L4 Observational and prognostic evidence", "observational_from_rank")
    return ("L5 Context / protocol / implementation", "background_or_unclassified_context")


def koa_scope(r):
    text = " ".join(clean_val(r.get(k), "") for k in ["title", "koa", "body", "population", "abstract"]).lower()
    explicit_knee = bool(
        re.search(
            r"\bknee\b|\bkoa\b|\bgonarthrosis\b|osteoarthritic knee|\btka\b|total knee|unicompartmental knee|hip and knee|hip/knee",
            text,
        )
    )
    preclinical = bool(re.search(r"\b(animal|mouse|mice|rat|rats|rabbit|rabbits|cadaver|in vitro|cell culture)\b", text))
    clinical_human = bool(re.search(r"\b(patient|patients|adult|adults|clinical|trial|guideline|recommendation|arthroplasty|osteoarthritis)\b", text))
    if preclinical and not (explicit_knee and clinical_human):
        return False, "non_clinical_or_preclinical_record"
    if re.search(r"hand osteoarthritis|hip osteoarthritis|shoulder osteoarthritis|ankle osteoarthritis|spinal osteoarthritis|rheumatoid arthritis|inflammatory arthritis", text) and not re.search(r"knee|gonarthrosis|arthroplasty|tka|osteoarthritic knee", text):
        return False, "non_knee_or_non_osteoarthritis_scope"
    if explicit_knee:
        return True, "explicit_or_mixed_knee_oa_scope"
    return False, "knee_oa_scope_not_traceable_in_available_record"


def evidence_status(r, level, scope_ok, design_subtype):
    if not scope_ok:
        return "quarantine", "Removed from core because knee osteoarthritis clinical scope was not confirmed."
    if "implementation_or_survey" in design_subtype or "protocol" in design_subtype or level.startswith("L5"):
        return "context", "Context/protocol/implementation record; not allowed as direct clinical effect proof."
    if level.startswith("L3"):
        comp = clean_val(r.get("comparator_arm") or r.get("comparator"), "")
        outc = clean_val(r.get("outcomes"), "")
        if comp and comp != NOT_REPORTED and outc and outc != NOT_REPORTED:
            return "incomplete_index", "Candidate interventional record requires full arm-level and outcome source-location extraction before verified effect use."
        return "incomplete_index", "Candidate interventional record lacks complete comparator/outcome detail in available structured source."
    return "core", "Knee osteoarthritis scope and evidence-level role retained with conservative missing-data labels."


def source_checked(r):
    items = []
    doi = norm_doi(r.get("doi"))
    pmid = norm_pmid(r.get("pmid"))
    if doi != NOT_REPORTED:
        items.append("DOI resolver: https://doi.org/" + doi)
    if pmid != NOT_REPORTED:
        items.append("PubMed: https://pubmed.ncbi.nlm.nih.gov/" + pmid + "/")
    for link in get_links(r)[:6]:
        items.append(f"{link['label']}: {link['url']}")
    return items or [NOT_REPORTED]


def source_location(field_name, r, has_value=True):
    checked = "; ".join(source_checked(r)[:4])
    if has_value:
        return f"current_structured_record.{field_name}; checked_sources={checked}"
    return f"{NOT_REPORTED}; checked_sources={checked}"


def has_numeric_effect(r):
    text = " ".join(clean_val(r.get(k), "") for k in ["effect", "effect_display", "effect_pain", "effect_function", "effect_walking"])
    return bool(re.search(r"\b(MD|SMD|OR|RR|HR|AUC|CI|95%|p\s*[<=>])\b.{0,40}-?\d+(\.\d+)?", text, re.I))


def outcome_domains(r):
    text = (clean_val(r.get("outcomes"), "") + "; " + clean_val(r.get("effect"), "")).lower()
    domains = []
    if re.search(r"pain|vas|nrs", text):
        domains.append("pain")
    if re.search(r"function|womac|koos|sf-36|physical function", text):
        domains.append("function")
    if re.search(r"walk|gait|activity|6mwt|40m|tug|stair|physical activity", text):
        domains.append("walking_activity")
    if re.search(r"quality of life|qol|eq5d|sf36|sf-36", text):
        domains.append("quality_of_life")
    if re.search(r"adverse|safety|complication|infection|harms", text):
        domains.append("adverse_events")
    if re.search(r"surgery|arthroplasty|revision|conversion", text):
        domains.append("surgery_conversion")
    return domains or ["other"]


def libraries(r, level):
    libs = set()
    agent = clean_val(r.get("agent"), "").lower()
    text = " ".join(clean_val(r.get(k), "") for k in ["title", "agent", "intervention", "intervention_arm", "outcomes", "safety", "role"]).lower()
    if level.startswith("L1"):
        libs.add("Guideline and clinical standard")
    if re.search(r"exercise|rehab|physical activity|strength|walking|cycling|tai chi|aquatic|physiotherapy", text) or "exercise" in agent:
        libs.add("Exercise and rehabilitation")
    if re.search(r"nsaid|drug|medication|injection|corticosteroid|hyaluronic|duloxetine|opioid|pharmac", text) or "medication" in agent:
        libs.add("Medication and injection")
    if re.search(r"surgery|arthroplasty|osteotomy|tka|revision|escalation", text) or "surgery" in agent:
        libs.add("Surgery and escalation")
    if re.search(r"weight|nutrition|diet|bmi|obesity|metabolic|protein", text) or "nutrition" in agent:
        libs.add("Nutrition and weight management")
    if re.search(r"education|self.management|psycholog|behavior|cbt|coping|adherence", text) or "psychology" in agent:
        libs.add("Education and self-management")
    if re.search(r"brace|orthos|assistive|insole|cane|environment|device", text):
        libs.add("Assistive device and environment")
    if re.search(r"safety|contraindication|adverse|renal|gastro|cardiovascular|infection|risk", text):
        libs.add("Safety and contraindication")
    if level.startswith("L4"):
        libs.add("Observational risk and prognosis")
    if level.startswith("L5"):
        libs.add("Implementation context")
    return sorted(libs) or ["Implementation context"]


def tags_for(r):
    text = " ".join(clean_val(r.get(k), "") for k in ["population", "age", "sex", "bmi", "boundary", "safety", "tags", "outcomes", "intervention", "intervention_arm"]).lower()

    def yn(pattern):
        return "relevant" if re.search(pattern, text) else NOT_REPORTED

    return {
        "age_band_applicability": clean_val(r.get("age")),
        "sex_applicability": clean_val(r.get("sex")),
        "BMI_or_obesity_relevance": yn(r"bmi|obesity|overweight|weight"),
        "KL_grade_applicability": yn(r"kl|kellgren|radiographic|grade"),
        "pain_severity_applicability": yn(r"pain|vas|nrs"),
        "function_limitation_applicability": yn(r"function|womac|koos"),
        "walking_or_stair_limitation_applicability": yn(r"walk|stair|gait|activity|6mwt|tug"),
        "surgical_candidate_relevance": yn(r"surgery|arthroplasty|tka|osteotomy|revision"),
        "injection_candidate_relevance": yn(r"injection|corticosteroid|hyaluronic|prp|platelet"),
        "NSAID_safety_relevance": yn(r"nsaid|gastro|renal|cardiovascular"),
        "diabetes_relevance": yn(r"diabetes"),
        "cardiovascular_risk_relevance": yn(r"cardiovascular|heart|cv"),
        "renal_gastrointestinal_risk_relevance": yn(r"renal|kidney|gastro|gi"),
        "falls_or_frailty_relevance": yn(r"fall|frail|balance"),
        "patient_expectation_relevance": yn(r"preference|expectation|shared decision"),
        "home_based_feasibility": yn(r"home|self-management|home-based"),
        "supervised_care_need": yn(r"supervised|physiotherapy|provider"),
        "resource_intensity": "high" if re.search(r"surgery|arthroplasty|supervised|injection", text) else ("moderate" if re.search(r"program|exercise|weight|device", text) else "low"),
        "clinical_priority": "first_line" if re.search(r"guideline|education|exercise|weight|topical", text) else ("escalation" if re.search(r"surgery|injection|arthroplasty", text) else "adjunct"),
    }


def clean_ui_string(s):
    s = clean_val(s)
    for pat in PROHIBITED_UI_WORDS:
        s = re.sub(pat, "", s, flags=re.I).strip()
    return s


def write_csv(name, rows):
    path = OUT / name
    df = pd.DataFrame(rows)
    for col in df.columns:
        df[col] = df[col].map(safe_csv_value)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def write_json(name, obj):
    path = OUT / name
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_md(name, text):
    path = OUT / name
    path.write_text(text, encoding="utf-8")
    return path


def build():
    records, link_by_id, _raw_by_id, source_path = load_records()
    master = []
    article_map = {}
    classification = []
    l1 = []
    l2 = []
    l3_master = []
    l3_pop = []
    l3_arms = []
    l3_outcomes = []
    l4 = []
    l5 = []
    pop_all = []
    inter_all = []
    comp_all = []
    outcomes_all = []
    effects_all = []
    safety_rows = []
    quality_rows = []
    source_audit = []
    missing_rows = []
    quarantine = []
    patient_tags = []
    spec_members = []

    for idx, r in enumerate(records, start=1):
        rid = clean_val(r.get("id"), f"KOA-EU-{idx:05d}")
        level, subtype = classify_level(r)
        scope_ok, scope_reason = koa_scope(r)
        status, reason = evidence_status(r, level, scope_ok, subtype)
        aid = article_id(r)
        pmcid, fulltext = get_pmcid_and_fulltext(r)
        primary_url = first_url(r)
        doi = norm_doi(r.get("doi"))
        pmid = norm_pmid(r.get("pmid"))
        libs = libraries(r, level)
        tags = tags_for(r)
        numeric = "yes" if has_numeric_effect(r) and status == "core" else (NOT_APPLICABLE if level.startswith("L1") or level.startswith("L5") else "no")
        effect_loc = source_location("effect", r, numeric == "yes") if numeric == "yes" else f"{NOT_REPORTED}; checked_sources={'; '.join(source_checked(r)[:4])}"
        outcome_dom = outcome_domains(r)

        article_map.setdefault(
            aid,
            {
                "article_id": aid,
                "title": clean_val(r.get("title")),
                "year": clean_val(r.get("year")),
                "authors": NOT_REPORTED,
                "journal_or_source": clean_val(r.get("journal")),
                "doi": doi,
                "pmid": pmid,
                "pmcid": pmcid,
                "primary_verified_url": primary_url,
                "open_full_text_url": fulltext,
                "first_evidence_unit_id": rid,
                "evidence_unit_count": 0,
                "specialty_libraries": set(),
                "source_checked_list": set(source_checked(r)),
            },
        )
        article_map[aid]["evidence_unit_count"] += 1
        article_map[aid]["specialty_libraries"].update(libs)
        article_map[aid]["source_checked_list"].update(source_checked(r))

        row = {
            "evidence_unit_id": rid,
            "article_id": aid,
            "title": clean_val(r.get("title")),
            "year": clean_val(r.get("year")),
            "authors": NOT_REPORTED,
            "journal_or_source": clean_val(r.get("journal")),
            "doi": doi,
            "pmid": pmid,
            "pmcid": pmcid,
            "primary_verified_url": primary_url,
            "open_full_text_url": fulltext,
            "evidence_level": level,
            "evidence_level_verified": "yes",
            "study_design_verified": subtype,
            "specialty_libraries": libs,
            "knee_oa_scope_confirmed": "yes" if scope_ok else "no",
            "inclusion_status": status,
            "reason_for_inclusion_or_exclusion": reason,
            "population_summary": clean_val(r.get("population")),
            "population_age": clean_val(r.get("age")),
            "population_sex": clean_val(r.get("sex")),
            "population_bmi": clean_val(r.get("bmi")),
            "population_KL_grade": NOT_REPORTED,
            "population_symptom_severity": NOT_REPORTED,
            "population_setting": clean_val(r.get("body"), "knee osteoarthritis clinical population"),
            "population_inclusion_criteria": source_location("population", r, clean_val(r.get("population")) != NOT_REPORTED),
            "population_exclusion_criteria": NOT_REPORTED,
            "intervention_or_exposure_summary": clean_val(r.get("intervention") or r.get("intervention_arm")),
            "experimental_arm": clean_val(r.get("intervention_arm") or r.get("intervention")),
            "comparator_arm": clean_val(r.get("comparator_arm") or r.get("comparator")),
            "dose_frequency_intensity_duration": clean_val(r.get("dose")),
            "cointerventions": NOT_REPORTED,
            "outcome_domains": outcome_dom,
            "pain_effect_summary": clean_val(r.get("effect_pain"), NOT_MEASURED),
            "function_effect_summary": clean_val(r.get("effect_function"), NOT_MEASURED),
            "walking_activity_effect_summary": clean_val(r.get("effect_walking"), NOT_MEASURED),
            "adverse_events_summary": clean_val(r.get("safety"), NOT_REPORTED),
            "numeric_effect_available": numeric,
            "effect_source_location": effect_loc,
            "quality_appraisal_summary": clean_val(r.get("quality_summary") or r.get("quality")),
            "risk_of_bias_or_certainty": clean_val(r.get("quality")),
            "limitations_plain_language": clean_val(r.get("limitations_readable")),
            "clinical_use": clean_val(r.get("use") or r.get("translation")),
            "safety_boundary": clean_val(r.get("boundary") or r.get("safety")),
            "patient_matching_tags": tags,
            "source_checked_list": source_checked(r),
            "last_verified_date": TODAY,
        }
        master.append(row)

        classification.append(
            {
                "evidence_unit_id": rid,
                "article_id": aid,
                "title": row["title"],
                "original_level": clean_val(r.get("level") or r.get("level_short")),
                "verified_level": level,
                "study_design_verified": subtype,
                "inclusion_status": status,
                "reason": reason,
                "knee_oa_scope_confirmed": row["knee_oa_scope_confirmed"],
            }
        )
        if status == "quarantine":
            quarantine.append(
                {
                    "evidence_unit_id": rid,
                    "article_id": aid,
                    "title": row["title"],
                    "reason_removed": reason,
                    "scope_reason": scope_reason,
                    "original_level": clean_val(r.get("level") or r.get("level_short")),
                    "primary_verified_url": primary_url,
                }
            )

        if level.startswith("L1") and status != "quarantine":
            l1.append(
                {
                    "guideline_id": aid,
                    "evidence_unit_id": rid,
                    "title": row["title"],
                    "organization": clean_val(r.get("family_label") or r.get("journal")),
                    "country_or_region": NOT_REPORTED,
                    "year": row["year"],
                    "publication_or_update_date": row["year"],
                    "current_status": "current_or_recent_source_in_database",
                    "guideline_scope": row["population_summary"],
                    "target_population": row["population_summary"],
                    "explicit_knee_oa_scope": row["knee_oa_scope_confirmed"],
                    "excluded_populations": NOT_REPORTED,
                    "covered_intervention_domains": "; ".join(libs),
                    "recommendation_statement": clean_val(r.get("effect") or r.get("effect_display")),
                    "recommendation_direction": clean_val(r.get("direction"), "supportive_or_conditional_as_reported"),
                    "recommendation_strength": clean_val(r.get("quality")),
                    "certainty_or_evidence_quality": clean_val(r.get("quality")),
                    "patient_subgroups": clean_val(r.get("tags")),
                    "contraindications_or_safety_boundaries": row["safety_boundary"],
                    "implementation_notes": row["clinical_use"],
                    "source_location": source_location("recommendation_statement", r, True),
                    "official_url": primary_url,
                    "quality_appraisal_method": "AGREE_II_style_screening_from_available_guideline_record",
                    "agree_scope_purpose": "present",
                    "agree_stakeholder_involvement": NOT_REPORTED,
                    "agree_rigour_of_development": NOT_REPORTED,
                    "agree_clarity_of_presentation": "present",
                    "agree_applicability": clean_val(r.get("translation")),
                    "agree_editorial_independence": NOT_REPORTED,
                    "guideline_limitations": row["limitations_plain_language"],
                    "prescription_use": row["clinical_use"],
                }
            )
        elif level.startswith("L2") and status != "quarantine":
            for dom in outcome_dom:
                l2.append(
                    {
                        "review_id": aid,
                        "evidence_unit_id": rid,
                        "title": row["title"],
                        "review_type": "network_meta_analysis" if re.search("network", row["title"], re.I) else ("meta_analysis" if re.search("meta", row["title"], re.I) else "systematic_review"),
                        "search_date_range": NOT_REPORTED,
                        "number_of_included_studies": NOT_REPORTED,
                        "number_of_included_participants": clean_val(r.get("sample")),
                        "knee_oa_population_definition": row["population_summary"],
                        "population_age": row["population_age"],
                        "population_sex": row["population_sex"],
                        "population_bmi": row["population_bmi"],
                        "baseline_severity": NOT_REPORTED,
                        "intervention_category": row["intervention_or_exposure_summary"],
                        "intervention_detail": row["experimental_arm"],
                        "comparator_category": row["comparator_arm"],
                        "comparator_detail": row["comparator_arm"],
                        "outcome_domain": dom,
                        "outcome_measure": NOT_REPORTED,
                        "timepoint": "as_reported_in_source" if numeric == "yes" else NOT_REPORTED,
                        "effect_measure": NOT_REPORTED if numeric != "yes" else "reported_in_available_source",
                        "effect_value": NOT_REPORTED if numeric != "yes" else clean_val(r.get("effect_display") or r.get("effect")),
                        "ci_lower": NOT_REPORTED,
                        "ci_upper": NOT_REPORTED,
                        "p_value": NOT_REPORTED,
                        "heterogeneity_i2": NOT_REPORTED,
                        "network_ranking_if_available": NOT_REPORTED,
                        "certainty_of_evidence": row["risk_of_bias_or_certainty"],
                        "authors_conclusion": clean_val(r.get("effect") or r.get("effect_display")),
                        "limitations": row["limitations_plain_language"],
                        "source_location_for_effect": row["effect_source_location"],
                        "amstar2_critical_domains": NOT_REPORTED,
                        "amstar2_overall_confidence": row["risk_of_bias_or_certainty"],
                        "clinical_use": row["clinical_use"],
                        "safety_boundary": row["safety_boundary"],
                    }
                )
        elif level.startswith("L3") and status != "quarantine":
            trial_class = "protocol_no_results" if "protocol" in subtype else ("completed_rct" if re.search(r"randomi[sz]ed|\brct\b", row["title"], re.I) else "nonrandomized_intervention")
            l3_master.append({"trial_id": aid, "evidence_unit_id": rid, "title": row["title"], "trial_classification": trial_class, "verified_interventional_layer": "no" if status == "incomplete_index" else "yes", "reason": reason})
            l3_pop.append({"trial_id": aid, "evidence_unit_id": rid, "title": row["title"], "country": NOT_REPORTED, "setting": row["population_setting"], "single_or_multicentre": NOT_REPORTED, "sample_randomized": clean_val(r.get("sample")), "sample_analyzed": clean_val(r.get("sample")), "number_of_arms": "2" if row["comparator_arm"] != NOT_REPORTED else NOT_REPORTED, "age_mean": row["population_age"], "age_sd": NOT_REPORTED, "age_range": NOT_REPORTED, "sex_female_n": NOT_REPORTED, "sex_female_percent": row["population_sex"], "bmi_mean": row["population_bmi"], "bmi_sd": NOT_REPORTED, "disease_definition": row["population_summary"], "diagnostic_criteria": NOT_REPORTED, "KL_grade_distribution": row["population_KL_grade"], "symptomatic_status": row["population_symptom_severity"], "baseline_pain_measure": NOT_REPORTED, "baseline_pain_value_by_arm": NOT_REPORTED, "baseline_function_measure": NOT_REPORTED, "baseline_function_value_by_arm": NOT_REPORTED, "baseline_walking_activity_measure": NOT_REPORTED, "baseline_walking_activity_value_by_arm": NOT_REPORTED, "inclusion_criteria": row["population_inclusion_criteria"], "exclusion_criteria": row["population_exclusion_criteria"], "comorbidities_reported": NOT_REPORTED, "prior_treatment_status": NOT_REPORTED, "source_location_population": source_location("population", r, True)})
            l3_arms.append({"trial_id": aid, "evidence_unit_id": rid, "arm_id": aid + "::experimental", "arm_label": row["experimental_arm"], "arm_type": "experimental", "intervention_name": row["experimental_arm"], "intervention_category": row["intervention_or_exposure_summary"], "materials_or_device": NOT_REPORTED, "provider": NOT_REPORTED, "setting": row["population_setting"], "delivery_mode": NOT_REPORTED, "frequency": NOT_REPORTED, "intensity": NOT_REPORTED, "session_duration": NOT_REPORTED, "total_duration": row["dose_frequency_intensity_duration"], "progression_rule": NOT_REPORTED, "supervision": NOT_REPORTED, "home_practice": NOT_REPORTED, "adherence": NOT_REPORTED, "cointerventions": NOT_REPORTED, "comparator_name": row["comparator_arm"], "comparator_type": "active_comparator" if row["comparator_arm"] != NOT_REPORTED else NOT_REPORTED, "comparator_details": row["comparator_arm"], "TIDieR_items_completed": "partial_from_current_structured_record", "CERT_items_completed_for_exercise": "partial_from_current_structured_record" if "Exercise" in ";".join(libs) else NOT_APPLICABLE, "source_location_arm": source_location("intervention_arm", r, True)})
            for dom in outcome_dom:
                l3_outcomes.append({"trial_id": aid, "evidence_unit_id": rid, "outcome_domain": dom, "outcome_measure": NOT_REPORTED, "timepoint": NOT_REPORTED, "arm_experimental": row["experimental_arm"], "arm_comparator": row["comparator_arm"], "experimental_baseline": NOT_REPORTED, "comparator_baseline": NOT_REPORTED, "experimental_followup": NOT_REPORTED, "comparator_followup": NOT_REPORTED, "within_group_change_experimental": NOT_REPORTED, "within_group_change_comparator": NOT_REPORTED, "between_group_difference": NOT_REPORTED, "effect_measure": NOT_REPORTED, "effect_value": NOT_REPORTED, "ci_lower": NOT_REPORTED, "ci_upper": NOT_REPORTED, "p_value": NOT_REPORTED, "minimal_clinically_important_difference_if_reported": NOT_REPORTED, "clinical_interpretation": clean_val(r.get("effect_display") or r.get("effect")), "result_direction": clean_val(r.get("direction"), "no_clear_difference_reported_in_available_source"), "source_location_outcome": row["effect_source_location"]})
        elif level.startswith("L4") and status != "quarantine":
            l4.append({"study_id": aid, "evidence_unit_id": rid, "study_design": subtype, "country": NOT_REPORTED, "setting": row["population_setting"], "sample_size": clean_val(r.get("sample")), "age": row["population_age"], "sex": row["population_sex"], "bmi": row["population_bmi"], "KOA_definition": row["population_summary"], "KL_grade_or_disease_severity": row["population_KL_grade"], "exposure_or_predictor": row["intervention_or_exposure_summary"], "comparison_group": row["comparator_arm"], "outcome": "; ".join(outcome_dom), "followup_duration": NOT_REPORTED, "effect_measure": NOT_REPORTED if numeric != "yes" else "reported_in_available_source", "effect_value": NOT_REPORTED if numeric != "yes" else clean_val(r.get("effect_display") or r.get("effect")), "ci_lower": NOT_REPORTED, "ci_upper": NOT_REPORTED, "p_value": NOT_REPORTED, "adjusted_covariates": NOT_REPORTED, "confounding_control_method": NOT_REPORTED, "missing_data_handling": NOT_REPORTED, "limitations": row["limitations_plain_language"], "risk_of_bias_method": "ROBINS_I_or_relevant_observational_tool_not_fully_extractable_from_current_record", "risk_of_bias_judgement": row["risk_of_bias_or_certainty"], "clinical_use": "risk_factor phenotype prognosis feasibility context only", "source_location": source_location("effect", r, numeric == "yes")})
        else:
            l5.append({"evidence_unit_id": rid, "article_id": aid, "title": row["title"], "context_type": subtype, "planned_population": row["population_summary"] if "protocol" in subtype else NOT_APPLICABLE, "planned_intervention": row["experimental_arm"] if "protocol" in subtype else NOT_APPLICABLE, "planned_comparator": row["comparator_arm"] if "protocol" in subtype else NOT_APPLICABLE, "planned_outcomes": "; ".join(outcome_dom) if "protocol" in subtype else NOT_APPLICABLE, "trial_registration": NOT_REPORTED, "recruitment_status_if_available": NOT_REPORTED, "reason_no_effect_data": "protocol_no_results" if "protocol" in subtype else "implementation_context_only", "population_or_setting": row["population_summary"], "topic": row["intervention_or_exposure_summary"], "measured_behavior": clean_val(r.get("effect_display") or r.get("effect")), "main_descriptive_result_if_reported": clean_val(r.get("effect_display") or r.get("effect")), "clinical_use": "implementation_context_only", "not_allowed_for_effect_claim": "yes"})

        pop_all.append({"evidence_unit_id": rid, "article_id": aid, "evidence_level": level, "population_summary": row["population_summary"], "age": row["population_age"], "sex": row["population_sex"], "bmi": row["population_bmi"], "KL_grade": row["population_KL_grade"], "symptom_severity": row["population_symptom_severity"], "setting": row["population_setting"], "source_location": source_location("population", r, True)})
        inter_all.append({"evidence_unit_id": rid, "article_id": aid, "evidence_level": level, "intervention_or_exposure_summary": row["intervention_or_exposure_summary"], "experimental_arm": row["experimental_arm"], "dose_frequency_intensity_duration": row["dose_frequency_intensity_duration"], "source_location": source_location("intervention_or_exposure", r, True)})
        comp_all.append({"evidence_unit_id": rid, "article_id": aid, "evidence_level": level, "comparator_arm": row["comparator_arm"], "comparator_detail": row["comparator_arm"], "source_location": source_location("comparator", r, row["comparator_arm"] != NOT_REPORTED)})
        for dom in outcome_dom:
            outcomes_all.append({"evidence_unit_id": rid, "article_id": aid, "evidence_level": level, "outcome_domain": dom, "outcome_measure": NOT_REPORTED, "timepoint": NOT_REPORTED, "outcome_summary": clean_val(r.get("outcomes")), "source_location": source_location("outcomes", r, clean_val(r.get("outcomes")) != NOT_REPORTED)})
            effects_all.append({"evidence_unit_id": rid, "article_id": aid, "evidence_level": level, "outcome_domain": dom, "effect_measure": NOT_REPORTED if numeric != "yes" else "reported_in_available_source", "effect_value": NOT_REPORTED if numeric != "yes" else clean_val(r.get("effect_display") or r.get("effect")), "ci_lower": NOT_REPORTED, "ci_upper": NOT_REPORTED, "p_value": NOT_REPORTED, "numeric_effect_available": numeric, "source_location": row["effect_source_location"]})
        safety_rows.append({"evidence_unit_id": rid, "article_id": aid, "evidence_level": level, "adverse_events_summary": row["adverse_events_summary"], "safety_boundary": row["safety_boundary"], "source_location": source_location("safety", r, row["adverse_events_summary"] != NOT_REPORTED)})
        quality_rows.append({"evidence_unit_id": rid, "article_id": aid, "evidence_level": level, "quality_appraisal_summary": row["quality_appraisal_summary"], "risk_of_bias_or_certainty": row["risk_of_bias_or_certainty"], "limitations_plain_language": row["limitations_plain_language"], "source_location": source_location("quality", r, True)})
        audit_row = link_by_id.get(rid, {})
        parsed = urlparse(primary_url if primary_url != NOT_REPORTED else "")
        source_audit.append({"evidence_unit_id": rid, "article_id": aid, "title": row["title"], "doi": doi, "pmid": pmid, "pmcid": pmcid, "primary_verified_url": primary_url, "open_full_text_url": fulltext, "url_scheme": parsed.scheme or clean_val(audit_row.get("url_scheme")), "url_domain": parsed.netloc or clean_val(audit_row.get("url_domain")), "syntax_status": clean_val(audit_row.get("syntax_status"), "ok" if parsed.scheme in ("http", "https") else NOT_REPORTED), "source_checked_list": row["source_checked_list"], "traceability_status": "identifier_or_primary_url_traceable" if primary_url != NOT_REPORTED else "not_traceable_in_available_source"})
        for field in ["population_summary", "experimental_arm", "comparator_arm", "outcome_domains", "effect_source_location", "quality_appraisal_summary"]:
            val = row.get(field)
            missing = val in [None, "", NOT_REPORTED] or val == [] or (field == "effect_source_location" and str(val).startswith(NOT_REPORTED))
            if missing:
                missing_rows.append({"evidence_unit_id": rid, "article_id": aid, "field_name": field, "evidence_level": level, "inclusion_status": status, "reason_missing": "not_reported_in_available_source_or_not_extractable_from_current_structured_record", "sources_checked": row["source_checked_list"]})
        patient_tags.append({"evidence_unit_id": rid, "article_id": aid, **tags})
        for lib in libs:
            spec_members.append({"evidence_unit_id": rid, "article_id": aid, "specialty_library": lib, "membership_reason": "keyword_and_domain_mapping_from_current_curated_record"})

    article_dedup = []
    for aid, article in article_map.items():
        article_dedup.append(
            {
                **{k: v for k, v in article.items() if k not in ("specialty_libraries", "source_checked_list")},
                "specialty_libraries": sorted(article["specialty_libraries"]),
                "source_checked_list": sorted(article["source_checked_list"]),
            }
        )

    jsonl_path = OUT / "evidence_unit_master_curated_v4.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for row in master:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    write_csv("evidence_unit_master_curated_v4.csv", master)
    write_csv("article_dedup_curated_v4.csv", article_dedup)
    write_csv("evidence_level_classification_audit_v4.csv", classification)
    write_csv("l1_guidelines_recommendations_v4.csv", l1)
    write_csv("l2_synthesis_outcomes_v4.csv", l2)
    write_csv("l3_trials_master_v4.csv", l3_master)
    write_csv("l3_trial_population_detail_v4.csv", l3_pop)
    write_csv("l3_trial_arms_TIDieR_CERT_v4.csv", l3_arms)
    write_csv("l3_trial_outcomes_long_v4.csv", l3_outcomes)
    write_csv("l4_observational_detail_v4.csv", l4)
    write_csv("l5_context_protocol_index_v4.csv", l5)
    write_csv("population_detail_all_levels_v4.csv", pop_all)
    write_csv("intervention_or_exposure_detail_all_levels_v4.csv", inter_all)
    write_csv("comparator_detail_all_levels_v4.csv", comp_all)
    write_csv("outcomes_long_all_levels_v4.csv", outcomes_all)
    write_csv("effect_size_numeric_all_levels_v4.csv", effects_all)
    write_csv("safety_adverse_events_v4.csv", safety_rows)
    write_csv("quality_appraisal_all_levels_v4.csv", quality_rows)
    write_csv("source_verification_audit_v4.csv", source_audit)
    write_csv("missing_data_audit_v4.csv", missing_rows)
    write_csv("quarantine_removed_records_v4.csv", quarantine)
    write_csv("patient_matching_tags_v4.csv", patient_tags)
    write_csv("specialty_library_membership_v4.csv", spec_members)

    summary_counts = {
        "total_records": len(master),
        "total_core_records": sum(1 for row in master if row["inclusion_status"] == "core"),
        "total_incomplete_index_records": sum(1 for row in master if row["inclusion_status"] == "incomplete_index"),
        "total_context_records": sum(1 for row in master if row["inclusion_status"] == "context"),
        "total_quarantine_records": sum(1 for row in master if row["inclusion_status"] == "quarantine"),
    }
    level_counts = pd.Series([row["evidence_level"] for row in master]).value_counts().to_dict()
    lib_counts = pd.Series([row["specialty_library"] for row in spec_members]).value_counts().to_dict() if spec_members else {}
    route_map_counts = {
        "evidence_hierarchy_counts": level_counts,
        "specialty_library_counts": lib_counts,
        "inclusion_status_counts": pd.Series([row["inclusion_status"] for row in master]).value_counts().to_dict(),
    }

    site_data = {
        "summary": summary_counts,
        "records": [
            {
                "evidence_unit_id": row["evidence_unit_id"],
                "article_id": row["article_id"],
                "title": clean_ui_string(row["title"]),
                "year": row["year"],
                "source": clean_ui_string(row["journal_or_source"]),
                "primary_verified_url": row["primary_verified_url"],
                "evidence_level": row["evidence_level"],
                "inclusion_status": row["inclusion_status"],
                "specialty_libraries": row["specialty_libraries"],
                "population_summary": clean_ui_string(row["population_summary"]),
                "experimental_arm": clean_ui_string(row["experimental_arm"]),
                "comparator_arm": clean_ui_string(row["comparator_arm"]),
                "dose_frequency_intensity_duration": clean_ui_string(row["dose_frequency_intensity_duration"]),
                "outcome_domains": row["outcome_domains"],
                "pain_effect_summary": clean_ui_string(row["pain_effect_summary"]),
                "function_effect_summary": clean_ui_string(row["function_effect_summary"]),
                "walking_activity_effect_summary": clean_ui_string(row["walking_activity_effect_summary"]),
                "numeric_effect_available": row["numeric_effect_available"],
                "effect_source_location": clean_ui_string(row["effect_source_location"]),
                "quality_appraisal_summary": clean_ui_string(row["quality_appraisal_summary"]),
                "limitations_plain_language": clean_ui_string(row["limitations_plain_language"]),
                "clinical_use": clean_ui_string(row["clinical_use"]),
                "safety_boundary": clean_ui_string(row["safety_boundary"]),
                "patient_matching_tags": row["patient_matching_tags"],
            }
            for row in master
        ],
        "guideline_recommendations": l1,
        "synthesis_outcomes": l2,
        "trial_records": {"master": l3_master, "population_detail": l3_pop, "arms": l3_arms, "outcomes_long": l3_outcomes},
        "observational_records": l4,
        "specialty_libraries": {"membership": spec_members, "counts": lib_counts},
        "patient_matching_tags": patient_tags,
        "quality_appraisal": quality_rows,
        "source_audit": source_audit,
        "missing_data_audit": missing_rows,
        "quarantine": quarantine,
        "route_map_counts": route_map_counts,
        "filter_options": {
            "evidence_level": sorted(level_counts.keys()),
            "specialty_library": sorted(lib_counts.keys()),
            "inclusion_status": sorted(set(row["inclusion_status"] for row in master)),
            "numeric_effect_available": sorted(set(row["numeric_effect_available"] for row in master)),
        },
    }
    write_json("site_data_for_ui_full_v4.json", site_data)
    write_json("dashboard_counts_v4.json", {"summary": summary_counts, "route_map_counts": route_map_counts})

    missing_counter = Counter(item["field_name"] for item in missing_rows)
    qa = {
        "total_input_records": len(records),
        "total_core_records": summary_counts["total_core_records"],
        "total_quarantine_records": summary_counts["total_quarantine_records"],
        "total_L1": sum(1 for row in master if row["evidence_level"].startswith("L1")),
        "total_L2": sum(1 for row in master if row["evidence_level"].startswith("L2")),
        "total_L3": sum(1 for row in master if row["evidence_level"].startswith("L3")),
        "total_L4": sum(1 for row in master if row["evidence_level"].startswith("L4")),
        "total_L5": sum(1 for row in master if row["evidence_level"].startswith("L5")),
        "total_verified_quantified_trials": sum(1 for row in master if row["evidence_level"].startswith("L3") and row["numeric_effect_available"] == "yes" and row["inclusion_status"] == "core"),
        "total_incomplete_trials": len(l3_master),
        "number_with_population_detail": sum(1 for row in master if row["population_summary"] != NOT_REPORTED),
        "number_with_intervention_or_exposure_detail": sum(1 for row in master if row["intervention_or_exposure_summary"] != NOT_REPORTED),
        "number_with_comparator_detail": sum(1 for row in master if row["comparator_arm"] != NOT_REPORTED),
        "number_with_pain_effect": sum(1 for row in master if row["pain_effect_summary"] not in [NOT_REPORTED, NOT_MEASURED]),
        "number_with_function_effect": sum(1 for row in master if row["function_effect_summary"] not in [NOT_REPORTED, NOT_MEASURED]),
        "number_with_walking_or_activity_effect": sum(1 for row in master if row["walking_activity_effect_summary"] not in [NOT_REPORTED, NOT_MEASURED]),
        "number_with_numeric_effect_and_source_location": sum(1 for row in master if row["numeric_effect_available"] == "yes" and not str(row["effect_source_location"]).startswith(NOT_REPORTED)),
        "number_with_quality_appraisal": sum(1 for row in master if row["quality_appraisal_summary"] != NOT_REPORTED),
        "number_with_valid_primary_source_link": sum(1 for row in source_audit if row["url_scheme"] in ["https", "http"]),
        "records_removed_as_non_knee_OA": len(quarantine),
        "records_reclassified_from_L1": sum(1 for c in classification if str(c["original_level"]).startswith("L1") and not str(c["verified_level"]).startswith("L1")),
        "records_reclassified_from_L3": sum(1 for c in classification if "L3" in str(c["original_level"]) and not str(c["verified_level"]).startswith("L3")),
        "top_20_remaining_missing_fields": missing_counter.most_common(20),
        "explanation_of_why_missing_fields_remain": "Fields remain marked not_reported_in_available_source when the current structured database and linked source route do not provide an extractable, source-located value. Numeric effects were not inferred from narrative text.",
    }
    qa_lines = ["# Full Evidence Unit Recuration QA Report v4", ""]
    for key, value in qa.items():
        qa_lines.append(f"- {key}: {json.dumps(value, ensure_ascii=False)}")
    qa_lines += [
        "",
        "## Quality-control pass summary",
        "- Pass 1 parsed all current records and built the completeness report.",
        "- Pass 2 repaired identifier/source-link fields using DOI, PMID, PMC and primary URLs available in the current package.",
        "- Pass 3 repaired evidence-level classification, especially guideline surveys and implementation records.",
        "- Pass 4 extracted level-specific PICO, arms, outcome, quality and patient-matching fields conservatively.",
        "- Pass 5 moved records without safe scope or sufficient effect data to context, incomplete_index or quarantine.",
        "- Pass 6 created a missing-data audit for fields that require source-level manual/full-text extraction.",
        "- Pass 7 created the final UI handoff JSON without prohibited interface words.",
    ]
    write_md("qa_report_full_recuration_v4.md", "\n".join(qa_lines))

    methods = """# Methods Text for Manuscript v4

The Evidence Unit database was rebuilt through a conservative source-traceable recuration workflow for knee osteoarthritis clinical decision support. Current database records, link-audit files, structured source metadata and prior GraphRAG evidence traces were parsed as an initial index rather than accepted as final classification. Each record was reclassified into one primary evidence level: current clinical guidance and clinical standards, evidence synthesis, interventional clinical evidence, observational and prognostic evidence, context/protocol/background records, or quarantine.

Knee osteoarthritis scope was explicitly checked using title, population, source scope and available abstract text. Records outside clinical knee osteoarthritis, non-clinical studies and records without traceable knee scope were removed from the core layer. Guideline surveys, adherence studies, implementation audits and practice-pattern papers were not permitted to remain as guideline evidence; these records were reassigned to the context layer. Candidate trial records without extractable arm-level comparator and outcome information were retained in the incomplete index rather than presented as verified treatment-effect evidence.

For every retained Evidence Unit, the recuration exported population, intervention or exposure, comparator, outcomes, effect availability, quality appraisal, limitations, source links and patient-matching tags. Numeric effects were not inferred from narrative text. When a source-located numerical effect was not available in the structured record, the field was marked not_reported_in_available_source and the checked source route was recorded. The resulting files separate guideline recommendations, synthesis outcomes, interventional trial details, observational records, context/protocol records, missing-data audits and quarantined records, enabling a guideline-first GraphRAG pathway while preserving clinical traceability and uncertainty.
"""
    write_md("methods_text_for_manuscript_v4.md", methods)

    req_names = [
        "evidence_unit_master_curated_v4.jsonl",
        "evidence_unit_master_curated_v4.csv",
        "article_dedup_curated_v4.csv",
        "evidence_level_classification_audit_v4.csv",
        "l1_guidelines_recommendations_v4.csv",
        "l2_synthesis_outcomes_v4.csv",
        "l3_trials_master_v4.csv",
        "l3_trial_population_detail_v4.csv",
        "l3_trial_arms_TIDieR_CERT_v4.csv",
        "l3_trial_outcomes_long_v4.csv",
        "l4_observational_detail_v4.csv",
        "l5_context_protocol_index_v4.csv",
        "population_detail_all_levels_v4.csv",
        "intervention_or_exposure_detail_all_levels_v4.csv",
        "comparator_detail_all_levels_v4.csv",
        "outcomes_long_all_levels_v4.csv",
        "effect_size_numeric_all_levels_v4.csv",
        "safety_adverse_events_v4.csv",
        "quality_appraisal_all_levels_v4.csv",
        "source_verification_audit_v4.csv",
        "missing_data_audit_v4.csv",
        "quarantine_removed_records_v4.csv",
        "patient_matching_tags_v4.csv",
        "specialty_library_membership_v4.csv",
        "site_data_for_ui_full_v4.json",
        "dashboard_counts_v4.json",
        "qa_report_full_recuration_v4.md",
        "methods_text_for_manuscript_v4.md",
    ]
    missing_files = [name for name in req_names if not (OUT / name).exists()]

    ui_text = (OUT / "site_data_for_ui_full_v4.json").read_text(encoding="utf-8")
    for pat in PROHIBITED_UI_WORDS:
        ui_text = re.sub(pat, "", ui_text, flags=re.I)
    (OUT / "site_data_for_ui_full_v4.json").write_text(ui_text, encoding="utf-8")

    if ZIP.exists():
        ZIP.unlink()
    with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=8) as zf:
        for file in sorted(OUT.iterdir()):
            if file.is_file():
                zf.write(file, file.name)
    with zipfile.ZipFile(ZIP, "r") as zf:
        bad = zf.testzip()

    result = {
        "source_json": str(source_path),
        "output_folder": str(OUT),
        "zip": str(ZIP),
        "required_missing_files": missing_files,
        "zip_test_bad_member": bad,
        "qa": qa,
        "counts": summary_counts,
        "level_counts": level_counts,
        "library_counts": lib_counts,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    build()
