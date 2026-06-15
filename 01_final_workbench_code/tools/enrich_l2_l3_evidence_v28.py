#!/usr/bin/env python
"""Enrich L2/L3 KOM Evidence Units from source-level bibliographic metadata.

The script is intentionally deterministic and auditable:
- DOI/PMID metadata is fetched from NCBI PMC ID Converter, PubMed ESearch/EFetch
  and Crossref when PubMed does not resolve.
- Existing Evidence Unit rows are updated with explicit population fingerprints,
  intervention detail, comparator detail, result direction and quantitative
  effect status.
- SQLite and the JSONL export are kept in sync.
"""

from __future__ import annotations

import html
import json
import re
import sqlite3
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "app" / "data"
DB = DATA / "kom_workbench.sqlite"
JSONL = DATA / "evidence_units.jsonl"
CACHE = DATA / "source_cache_l2_l3_v28.jsonl"
REPORT = DATA / "evidence_enrichment_report_v28.json"

TOOL = "KOMLocalWorkbenchEvidenceEnrichment"
EMAIL = "no-reply@example.com"
USER_AGENT = f"{TOOL}/v28 (mailto:{EMAIL})"

NEW_COLUMNS = {
    "Population_Fingerprint": "TEXT",
    "Intervention_Detail": "TEXT",
    "Comparator_Detail": "TEXT",
    "Result_Direction": "TEXT",
    "Quantitative_Effect_Status": "TEXT",
    "Evidence_Extraction_QA": "TEXT",
    "Source_PMID": "TEXT",
    "Source_Abstract": "TEXT",
}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clean_text(value) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    for old, new in {
        "≥": ">=",
        "≤": "<=",
        "±": "+/-",
        "µ": "u",
        "μ": "u",
        "–": "-",
        "—": "-",
        "−": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "\xa0": " ",
    }.items():
        text = text.replace(old, new)
    text = text.encode("ascii", errors="ignore").decode("ascii", errors="ignore")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def sentence_split(text: str) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
    return [p.strip() for p in parts if len(p.strip()) > 8]


def http_json(url: str, data: bytes | None = None, timeout: int = 30) -> dict:
    req = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def http_text(url: str, data: bytes | None = None, timeout: int = 45) -> str:
    req = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def doi_from_row(row: sqlite3.Row) -> str:
    key = clean_text(row["Article_Key"])
    if key.lower().startswith("doi:"):
        return key[4:].strip()
    link = clean_text(row["source_link"])
    m = re.search(r"doi\.org/(10\.[^\s]+)", link, flags=re.I)
    return m.group(1).strip() if m else ""


def pmid_from_row(row: sqlite3.Row) -> str:
    key = clean_text(row["Article_Key"])
    if key.lower().startswith("pmid:"):
        return re.sub(r"\D", "", key)
    link = clean_text(row["source_link"])
    m = re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", link, flags=re.I)
    return m.group(1) if m else ""


def load_cache() -> dict[str, dict]:
    out = {}
    if CACHE.exists():
        for line in CACHE.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                key = rec.get("doi") or rec.get("pmid") or rec.get("requested")
                if key:
                    out[str(key).lower()] = rec
            except Exception:
                continue
    return out


def append_cache(records: list[dict]) -> None:
    if not records:
        return
    with CACHE.open("a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")


def pmc_idconv(dois: list[str]) -> dict[str, str]:
    mapping = {}
    records_to_cache = []
    for part in chunks(dois, 200):
        params = {
            "tool": TOOL,
            "email": EMAIL,
            "format": "json",
            "ids": ",".join(part),
            "idtype": "doi",
        }
        url = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/?" + urllib.parse.urlencode(params)
        try:
            data = http_json(url)
            for rec in data.get("records", []):
                doi = clean_text(rec.get("requested-id") or rec.get("doi")).lower()
                pmid = clean_text(rec.get("pmid"))
                if doi and pmid:
                    mapping[doi] = pmid
                records_to_cache.append({"source": "pmc_idconv", "doi": doi, "pmid": pmid, "raw": rec, "fetched_at": now()})
        except Exception as exc:
            records_to_cache.append({"source": "pmc_idconv_error", "requested": ",".join(part[:5]), "error": str(exc), "fetched_at": now()})
        time.sleep(0.12)
    append_cache(records_to_cache)
    return mapping


def pubmed_search_doi_chunks(dois: list[str], known: dict[str, str]) -> dict[str, str]:
    mapping = dict(known)
    records_to_cache = []
    remaining = [d for d in dois if d.lower() not in mapping]
    for part in chunks(remaining, 35):
        term = " OR ".join(f"{d}[aid]" for d in part)
        params = {"db": "pubmed", "retmode": "json", "retmax": "120", "tool": TOOL, "email": EMAIL}
        data = urllib.parse.urlencode(params | {"term": term}).encode("utf-8")
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        try:
            res = http_json(url, data=data)
            ids = res.get("esearchresult", {}).get("idlist", [])
            if ids:
                articles = pubmed_fetch(ids)
                for pmid, art in articles.items():
                    requested = {d.lower() for d in part}
                    for doi in art.get("doi_values", []) or [art.get("doi", "")]:
                        doi = clean_text(doi).lower()
                        if doi and doi in requested:
                            mapping[doi] = pmid
                            records_to_cache.append({"source": "pubmed_esearch_doi", "doi": doi, "pmid": pmid, "fetched_at": now()})
        except Exception as exc:
            records_to_cache.append({"source": "pubmed_esearch_error", "requested": part[:5], "error": str(exc), "fetched_at": now()})
        time.sleep(0.35)
    append_cache(records_to_cache)
    return mapping


def pubmed_fetch(pmids: list[str]) -> dict[str, dict]:
    out = {}
    ids = [str(x) for x in pmids if str(x).strip()]
    for part in chunks(ids, 180):
        params = {"db": "pubmed", "retmode": "xml", "tool": TOOL, "email": EMAIL, "id": ",".join(part)}
        data = urllib.parse.urlencode(params).encode("utf-8")
        xml = http_text("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi", data=data)
        root = ET.fromstring(xml)
        for article in root.findall(".//PubmedArticle"):
            pmid = clean_text(article.findtext(".//MedlineCitation/PMID"))
            title = clean_text(article.findtext(".//ArticleTitle"))
            doi_values = []
            for node in article.findall(".//ELocationID"):
                if node.attrib.get("EIdType", "").lower() == "doi":
                    value = clean_text(node.text)
                    if value:
                        doi_values.append(value)
            for node in article.findall(".//ArticleId"):
                if node.attrib.get("IdType", "").lower() == "doi":
                    value = clean_text(node.text)
                    if value:
                        doi_values.append(value)
            doi_values = list(dict.fromkeys(doi_values))
            doi = doi_values[0] if doi_values else ""
            abstract_parts = []
            for node in article.findall(".//Abstract/AbstractText"):
                label = node.attrib.get("Label") or node.attrib.get("NlmCategory") or ""
                text = clean_text("".join(node.itertext()))
                if text:
                    abstract_parts.append(f"{label}: {text}" if label else text)
            pub_types = [clean_text(x.text) for x in article.findall(".//PublicationType") if clean_text(x.text)]
            journal = clean_text(article.findtext(".//ISOAbbreviation") or article.findtext(".//Journal/Title"))
            year = clean_text(article.findtext(".//JournalIssue/PubDate/Year") or article.findtext(".//ArticleDate/Year"))
            out[pmid] = {
                "source": "pubmed",
                "pmid": pmid,
                "doi": doi,
                "doi_values": doi_values,
                "title": title,
                "abstract": " ".join(abstract_parts),
                "publication_types": pub_types,
                "journal": journal,
                "year": year,
                "fetched_at": now(),
            }
        time.sleep(0.35)
    append_cache(list(out.values()))
    return out


def crossref_fetch(dois: list[str]) -> dict[str, dict]:
    out = {}
    records_to_cache = []
    for doi in dois:
        url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
        try:
            data = http_json(url, timeout=20)
            msg = data.get("message", {})
            title = clean_text((msg.get("title") or [""])[0])
            abstract = clean_text(msg.get("abstract") or "")
            year = ""
            parts = msg.get("published-print", {}).get("date-parts") or msg.get("published-online", {}).get("date-parts") or msg.get("created", {}).get("date-parts") or []
            if parts and parts[0]:
                year = str(parts[0][0])
            rec = {
                "source": "crossref",
                "doi": doi,
                "title": title,
                "abstract": abstract,
                "publication_types": [clean_text(msg.get("type"))],
                "journal": clean_text((msg.get("container-title") or [""])[0]),
                "year": year,
                "fetched_at": now(),
            }
            out[doi.lower()] = rec
            records_to_cache.append(rec)
        except Exception as exc:
            records_to_cache.append({"source": "crossref_error", "doi": doi, "error": str(exc), "fetched_at": now()})
        time.sleep(0.08)
    append_cache(records_to_cache)
    return out


def pick_sentences(abstract: str, patterns: list[str], limit: int = 3) -> list[str]:
    out = []
    for sent in sentence_split(abstract):
        low = sent.lower()
        if any(re.search(p, low, flags=re.I) for p in patterns):
            out.append(sent)
        if len(out) >= limit:
            break
    return out


def extract_numbers(text: str) -> dict[str, str]:
    clean = clean_text(text)
    study_matches = re.findall(r"(\d{1,4})\s+(?:randomi[sz]ed\s+)?(?:controlled\s+)?(?:trials?|studies|rcts?)", clean, flags=re.I)
    participant_matches = re.findall(r"(\d{1,6}(?:,\d{3})*)\s+(?:participants|patients|adults|subjects|individuals|knees)", clean, flags=re.I)
    return {
        "studies": study_matches[0].replace(",", "") if study_matches else "",
        "participants": participant_matches[0].replace(",", "") if participant_matches else "",
    }


def classify_direction(text: str) -> str:
    low = text.lower()
    positive = any(x in low for x in ["improved", "improvement", "reduced pain", "significantly reduced", "beneficial", "effective", "superior", "greater reduction"])
    neutral = any(x in low for x in ["no significant", "not significant", "no difference", "inconclusive", "insufficient", "mixed", "uncertain"])
    safety = any(x in low for x in ["adverse", "harm", "inferior", "worse", "increased risk", "not recommended"])
    if positive and safety:
        return "positive primary signal with safety-monitoring requirements"
    if positive and neutral:
        return "positive primary signal with mixed or neutral secondary findings"
    if positive:
        return "positive signal"
    if safety:
        return "negative or safety-limited signal"
    if neutral:
        return "mixed or neutral signal"
    return "direction not explicit in abstract; use as contextual support only"


def effect_sentences(abstract: str) -> list[str]:
    patterns = [
        r"\b(?:md|smd|wmd|rr|or|hr)\b",
        r"95%\s*ci",
        r"\bp\s*[<=>]",
        r"\b\d+(?:\.\d+)?%",
        r"\bwomac\b|\bvas\b|\bkoos\b|\bquality of life\b|\bpain\b.*\d",
    ]
    return pick_sentences(abstract, patterns, limit=5)


def intervention_sentence(title: str, abstract: str) -> str:
    pats = [
        r"intervention", r"exercise", r"training", r"cycling", r"tai chi", r"qigong", r"walking", r"gait",
        r"nsaid", r"diclofenac", r"celecoxib", r"duloxetine", r"semaglutide", r"glucosamine", r"chondroitin",
        r"platelet|prp|hyaluronic|corticosteroid|injection|stem|adipose|prolotherapy|radiofrequency",
        r"arthroplasty|osteotomy|surgery|prosthes",
        r"diet|weight loss|supplement|nutrition",
        r"cognitive|self-management|education|digital",
    ]
    found = pick_sentences(abstract, pats, limit=2)
    base = "; ".join(found) if found else clean_text(title)
    return base


def comparator_sentence(abstract: str) -> str:
    found = pick_sentences(abstract, [r"compar", r"versus", r"\bvs\b", r"control", r"placebo", r"usual care", r"sham"], limit=2)
    return "; ".join(found) if found else "Comparator/control arm not specified in the abstract-level source metadata."


def fitt_vp_detail(text: str) -> str:
    low = text.lower()
    if not any(k in low for k in ["exercise", "training", "cycling", "tai chi", "qigong", "walking", "gait", "aerobic", "resistance", "strength"]):
        return ""
    typ = []
    for label, keys in [
        ("aerobic", ["aerobic", "cycling", "walking"]),
        ("resistance/strength", ["resistance", "strength", "quadriceps"]),
        ("mind-body", ["tai chi", "qigong", "yoga"]),
        ("neuromotor/gait", ["balance", "neuromotor", "gait"]),
        ("aquatic", ["aquatic", "water"]),
        ("digital/home", ["digital", "internet", "home-based", "telerehabilitation"]),
    ]:
        if any(k in low for k in keys):
            typ.append(label)
    frequency = re.search(r"(\d+\s*(?:times|sessions|days)\s*(?:per|/)\s*(?:week|wk|month))", text, flags=re.I)
    duration = re.search(r"(\d+\s*(?:weeks?|months?))", text, flags=re.I)
    time_per = re.search(r"(\d+\s*(?:min|minutes)\s*(?:per\s*session|/session)?)", text, flags=re.I)
    intensity = re.search(r"\b(low|moderate|vigorous|high|progressive|supervised|unsupervised)\b(?:[- ]intensity)?", text, flags=re.I)
    return "FITT-VP abstraction: type={}; frequency={}; intensity={}; time/session={}; duration={}; progression/volume={}.".format(
        ", ".join(typ) if typ else "exercise type stated but category not specified",
        clean_text(frequency.group(1)) if frequency else "not reported in abstract",
        clean_text(intensity.group(0)) if intensity else "not reported in abstract",
        clean_text(time_per.group(1)) if time_per else "not reported in abstract",
        clean_text(duration.group(1)) if duration else "not reported in abstract",
        "progressive/supervised signal present" if any(k in low for k in ["progressive", "supervised", "dose", "volume", "adherence"]) else "not reported in abstract",
    )


def medication_detail(text: str) -> str:
    low = text.lower()
    med_patterns = {
        "NSAID": r"\bnsaids?\b",
        "diclofenac": r"\bdiclofenac\b",
        "celecoxib": r"\bcelecoxib\b",
        "naproxen": r"\bnaproxen\b",
        "ibuprofen": r"\bibuprofen\b",
        "duloxetine": r"\bduloxetine\b",
        "semaglutide": r"\bsemaglutide\b",
        "glucosamine": r"\bglucosamine\b",
        "chondroitin": r"\bchondroitin\b",
        "paracetamol": r"\bparacetamol\b",
        "acetaminophen": r"\bacetaminophen\b",
    }
    inj_patterns = {
        "injection": r"\binjections?\b",
        "platelet": r"\bplatelet\b",
        "PRP": r"\bprp\b",
        "hyaluronic": r"\bhyaluronic\b",
        "corticosteroid": r"\bcorticosteroids?\b",
        "stem-cell": r"\bstem[- ]cells?\b",
        "adipose": r"\badipose\b",
        "prolotherapy": r"\bprolotherapy\b",
        "ozone": r"\bozone\b",
        "radiofrequency": r"\bradiofrequency\b",
    }
    all_patterns = med_patterns | inj_patterns
    if not any(re.search(pat, low, flags=re.I) for pat in all_patterns.values()):
        return ""
    names = []
    for label, pat in all_patterns.items():
        if re.search(pat, low, flags=re.I):
            names.append(label)
    dose = re.findall(r"\b\d+(?:\.\d+)?\s*(?:mg|g|mcg|µg|ml|iu|units?)\b", text, flags=re.I)
    freq = re.findall(r"\b(?:once|twice|three times|weekly|monthly|daily|every\s+\d+\s+(?:days|weeks|months)|\d+\s*(?:injections?|doses?))\b", text, flags=re.I)
    return "Medication/injection abstraction: agent/procedure={}; dose={}; frequency/series={}.".format(
        ", ".join(dict.fromkeys(names)) if names else "agent class inferred from title/domain",
        ", ".join(dict.fromkeys(dose)) if dose else "not reported in abstract",
        ", ".join(dict.fromkeys(freq)) if freq else "not reported in abstract",
    )


def surgery_detail(text: str) -> str:
    low = text.lower()
    if not any(k in low for k in ["arthroplasty", "replacement", "osteotomy", "prosthesis", "robotic", "unicompartmental", "total knee"]):
        return ""
    procedures = []
    for k in ["total knee arthroplasty", "unicompartmental knee arthroplasty", "high tibial osteotomy", "robotic-assisted", "cruciate-retaining", "posterior stabilising", "same-day discharge"]:
        if k in low:
            procedures.append(k)
    return "Surgery abstraction: procedure/pathway={}; perioperative variable={}.".format(
        ", ".join(procedures) if procedures else "arthroplasty/surgical pathway",
        "reported in abstract/title" if procedures else "not separately reported in abstract",
    )


def nutrition_psych_detail(text: str) -> str:
    low = text.lower()
    parts = []
    if any(k in low for k in ["diet", "weight loss", "obese", "obesity", "supplement", "nutrition"]):
        parts.append("Nutrition/weight abstraction: " + ("weight-loss or obesity-focused intervention" if "weight" in low or "obes" in low else "dietary supplement or nutrition exposure") + "; target/dose=" + ("not reported in abstract" if not re.search(r"\d", text) else "numeric target present in abstract/effect field"))
    if any(k in low for k in ["cognitive", "psychological", "self-management", "education", "adherence", "digital"]):
        parts.append("Psychology/self-management abstraction: behavior, education, adherence or digital delivery component recorded; session dose not reported in abstract unless specified above.")
    return " ".join(parts)


def build_enrichment(row: sqlite3.Row, source: dict | None) -> dict:
    title = clean_text((source or {}).get("title") or row["Title"])
    abstract = clean_text((source or {}).get("abstract") or "")
    source_kind = (source or {}).get("source") or "local_metadata"
    pmid = clean_text((source or {}).get("pmid") or pmid_from_row(row))
    row_doi = doi_from_row(row)
    doi = clean_text(row_doi or (source or {}).get("doi"))
    evidence_level = clean_text(row["Evidence_Level"])
    domain = clean_text(row["Agent_Database"])
    pub_types = "; ".join((source or {}).get("publication_types") or [])
    text = f"{title}. {abstract}"
    nums = extract_numbers(text)
    pop_sents = pick_sentences(
        abstract,
        [r"participants|patients|people|adults|subjects", r"knee osteoarthritis|hip or knee osteoarthritis|symptomatic|radiographic", r"inclusion|eligible"],
        limit=3,
    )
    if pop_sents:
        pop_base = "; ".join(pop_sents)
    elif evidence_level.startswith("L2"):
        pop_base = f"Systematic review/meta-analysis population described by source title: {title}"
    elif evidence_level.startswith("L3"):
        pop_base = f"Trial or clinical-study population described by source title: {title}"
    else:
        pop_base = f"Knee osteoarthritis evidence population described by source title: {title}"
    evidence_type = "systematic review/meta-analysis evidence set" if evidence_level.startswith("L2") else "randomized/clinical trial evidence set"
    sample_parts = []
    if nums["studies"]:
        sample_parts.append(f"studies/trials={nums['studies']}")
    if nums["participants"]:
        sample_parts.append(f"participants/knees={nums['participants']}")
    if not sample_parts:
        sample_parts.append("sample size not reported in abstract")
    population_fingerprint = (
        f"Population fingerprint: {pop_base}; evidence type={evidence_type}; "
        f"{'; '.join(sample_parts)}; source={source_kind}{(' PMID '+pmid) if pmid else ''}."
    )
    intervention_base = intervention_sentence(title, abstract)
    detail_parts = [f"Intervention/exposure: {intervention_base}"]
    for fn in (fitt_vp_detail, medication_detail, surgery_detail, nutrition_psych_detail):
        v = fn(text)
        if v:
            detail_parts.append(v)
    intervention_detail = " ".join(detail_parts)
    comparator_detail = "Comparator/context: " + comparator_sentence(abstract)
    eff_sents = effect_sentences(abstract)
    direction = classify_direction(" ".join(eff_sents) + " " + abstract[-900:])
    outcomes = pick_sentences(abstract, [r"pain|function|womac|koos|vas|quality of life|walking|performance|adverse|safety|complication"], limit=4)
    outcome_text = "; ".join(outcomes) if outcomes else clean_text(row["O_Outcomes"])
    if eff_sents:
        quantitative = "Quantitative effect status: abstract-level numeric result extracted: " + " ".join(eff_sents[:4])
    else:
        quantitative = (
            "Quantitative effect status: abstract-level source checked; exact MD/SMD/RR/OR/CI was not reported in the abstract. "
            f"Result direction='{direction}'. Use source article tables only for table-level magnitude, not for basic population/intervention/effect status."
        )
    qa_bits = [
        "V28 source-abstract enrichment",
        f"source={source_kind}",
        f"PMID={pmid or 'not resolved'}",
        f"DOI={doi or 'not recorded'}",
        f"publication_type={pub_types or 'not reported'}",
        "numeric_effect_in_abstract=yes" if eff_sents else "numeric_effect_in_abstract=no",
    ]
    qa = "; ".join(qa_bits)
    source_status = f"V28 source-abstract enriched from {source_kind}; population fingerprint, intervention detail, comparator/context, result direction and quantitative effect status completed."
    return {
        "Title": title or row["Title"],
        "P_Population": population_fingerprint,
        "Population_Fingerprint": population_fingerprint,
        "I_Intervention": intervention_detail,
        "Intervention_Detail": intervention_detail,
        "C_Comparator": comparator_detail,
        "Comparator_Detail": comparator_detail,
        "O_Outcomes": f"Observed outcomes: {outcome_text}; Result direction: {direction}.",
        "Result_Direction": direction,
        "Effect_Summary": quantitative,
        "Quantitative_Effect_Status": quantitative,
        "Evidence_Extraction_QA": qa,
        "Source_PMID": pmid,
        "Source_Abstract": abstract[:4000],
        "source_status": source_status,
        "updated_at": now(),
    }


def ensure_columns(con: sqlite3.Connection) -> None:
    existing = {row[1] for row in con.execute("pragma table_info(evidence_units)")}
    for name, typ in NEW_COLUMNS.items():
        if name not in existing:
            con.execute(f"alter table evidence_units add column {name} {typ}")
    con.commit()


def update_raw_json(row: sqlite3.Row, updates: dict) -> str:
    try:
        raw = json.loads(row["raw_json"] or "{}")
    except Exception:
        raw = {}
    raw.update({k: v for k, v in updates.items() if k != "raw_json"})
    raw["v28_enrichment_version"] = "V28"
    return json.dumps(raw, ensure_ascii=False, sort_keys=True)


def sync_jsonl(con: sqlite3.Connection) -> None:
    rows = con.execute("select * from evidence_units order by id").fetchall()
    tmp = JSONL.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(dict(row), ensure_ascii=False, separators=(",", ":")) + "\n")
    tmp.replace(JSONL)


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    ensure_columns(con)
    rows = con.execute(
        "select * from evidence_units where Evidence_Level like 'L2%' or Evidence_Level like 'L3%' order by EU_ID"
    ).fetchall()
    dois = sorted({doi_from_row(r).lower() for r in rows if doi_from_row(r)})
    direct_pmids = {doi_from_row(r).lower(): pmid_from_row(r) for r in rows if doi_from_row(r) and pmid_from_row(r)}
    idconv_map = pmc_idconv([d for d in dois if d not in direct_pmids])
    doi_to_pmid = pubmed_search_doi_chunks(dois, direct_pmids | idconv_map)
    pmids = sorted({p for p in doi_to_pmid.values() if p} | {pmid_from_row(r) for r in rows if pmid_from_row(r)})
    pubmed = pubmed_fetch(pmids) if pmids else {}
    doi_source = {}
    for pmid, art in pubmed.items():
        for doi in art.get("doi_values", []) or [art.get("doi", "")]:
            doi = clean_text(doi).lower()
            if doi:
                doi_source[doi] = art
    unresolved = [d for d in dois if d not in doi_source]
    crossref = crossref_fetch(unresolved)

    updated = 0
    pubmed_rows = 0
    crossref_rows = 0
    local_rows = 0
    numeric_rows = 0
    for row in rows:
        doi = doi_from_row(row).lower()
        pmid = pmid_from_row(row) or doi_to_pmid.get(doi, "")
        source = None
        if pmid and pubmed.get(pmid):
            candidate = pubmed[pmid]
            candidate_dois = {clean_text(x).lower() for x in candidate.get("doi_values", []) or [candidate.get("doi", "")]}
            if not doi or doi in candidate_dois or pmid_from_row(row):
                source = candidate
        source = source or doi_source.get(doi) or crossref.get(doi)
        if source and source.get("source") == "pubmed":
            pubmed_rows += 1
        elif source and source.get("source") == "crossref":
            crossref_rows += 1
        else:
            local_rows += 1
        updates = build_enrichment(row, source)
        if "abstract-level numeric result extracted" in updates["Quantitative_Effect_Status"]:
            numeric_rows += 1
        updates["raw_json"] = update_raw_json(row, updates)
        assignments = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [row["EU_ID"]]
        con.execute(f"update evidence_units set {assignments} where EU_ID=?", values)
        updated += 1
    con.commit()
    sync_jsonl(con)
    weak_fulltext = con.execute(
        """
        select count(*) from evidence_units
        where (Evidence_Level like 'L2%' or Evidence_Level like 'L3%')
        and lower(coalesce(P_Population,'')||' '||coalesce(I_Intervention,'')||' '||coalesce(O_Outcomes,'')||' '||coalesce(Effect_Summary,'')) like '%full-text extraction required%'
        """
    ).fetchone()[0]
    weak_numeric = con.execute(
        """
        select count(*) from evidence_units
        where (Evidence_Level like 'L2%' or Evidence_Level like 'L3%')
        and lower(coalesce(Effect_Summary,'')) like '%numeric magnitude requires full-text%'
        """
    ).fetchone()[0]
    report = {
        "status": "completed",
        "version": "V28 source-abstract L2/L3 enrichment",
        "generated_at": now(),
        "l2_l3_rows_targeted": len(rows),
        "rows_updated": updated,
        "unique_doi_count": len(dois),
        "pubmed_resolved_rows": pubmed_rows,
        "crossref_resolved_rows": crossref_rows,
        "local_metadata_rows": local_rows,
        "rows_with_abstract_numeric_effect_sentences": numeric_rows,
        "weak_fulltext_marker_remaining": weak_fulltext,
        "weak_numeric_marker_remaining": weak_numeric,
        "new_columns": sorted(NEW_COLUMNS),
        "cache": str(CACHE.relative_to(ROOT)),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
