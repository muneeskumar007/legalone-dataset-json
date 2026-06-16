"""
judgment_extractor_tool.py
─────────────────────────────────────────────────────────────────
Reusable pipeline to convert ANY Indian court judgment PDF → JSON.
Usage:
    python3 judgment_extractor_tool.py <path_to_pdf>

Outputs:
    <case_name>_dataset.json   — structured LegalOne record
    <case_name>_principles.json — legal principles only (for RAG)
"""

import sys, re, json, pdfplumber
from pathlib import Path
from datetime import datetime


# ════════════════════════════════════════════════════════════════
# LAYER 1 — RAW TEXT EXTRACTION
# ════════════════════════════════════════════════════════════════

def extract_text(pdf_path: str) -> tuple[list, str]:
    """Extract text page by page and return (pages_list, full_text)."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            # Clean up noise: remove http links and page numbers
            text = re.sub(r'http://www\.judis\.nic\.in\S*', '', text)
            text = re.sub(r'Indian Kanoon.*?\d+\s*$', '', text, flags=re.MULTILINE)
            pages.append({"page_number": i + 1, "text": text.strip()})
    full_text = "\n\n".join(p["text"] for p in pages if p["text"])
    return pages, full_text


# ════════════════════════════════════════════════════════════════
# LAYER 2 — STRUCTURED FIELD EXTRACTION (rule-based)
# ════════════════════════════════════════════════════════════════

def extract_case_header(full_text: str) -> dict:
    """Extract court, case numbers, dates, judges from first few pages."""
    header = {}

    # Court
    courts = {
        "HIGH COURT OF JUDICATURE AT MADRAS":      "High Court of Judicature at Madras",
        "HIGH COURT OF JUDICATURE AT BOMBAY":      "High Court of Judicature at Bombay",
        "HIGH COURT OF DELHI":                     "High Court of Delhi",
        "SUPREME COURT OF INDIA":                  "Supreme Court of India",
        "HIGH COURT OF KARNATAKA":                 "High Court of Karnataka",
        "HIGH COURT OF JUDICATURE AT ALLAHABAD":   "High Court of Judicature at Allahabad",
    }
    for pattern, name in courts.items():
        if pattern in full_text.upper():
            header["court"] = name
            break

    # Judges (look for "JUSTICE" keyword)
    judge_matches = re.findall(
        r'(?:MR\.?|MRS\.?|MS\.?)\s*JUSTICE\s+([A-Z][A-Z\.\s]+?)(?:\n|AND|,)',
        full_text.upper()
    )
    header["judges"] = list(set(m.strip().title() for m in judge_matches if len(m.strip()) > 5))

    # Bench type
    if len(header.get("judges", [])) >= 2:
        header["bench"] = "Division Bench"
    elif len(header.get("judges", [])) >= 3:
        header["bench"] = "Full Bench"
    else:
        header["bench"] = "Single Judge"

    # Dates
    dates = re.findall(r'(?:Reserved|Delivered|Decided|Pronounced)\s+on\s*[:\-]?\s*(\d{2}\.\d{2}\.\d{4})', full_text)
    if len(dates) >= 2:
        header["reserved_on"]  = dates[0]
        header["delivered_on"] = dates[1]
    elif len(dates) == 1:
        header["delivered_on"] = dates[0]

    # Case numbers
    case_numbers = re.findall(
        r'(?:W\.P\.No\.|Crl\.A\.No\.|C\.S\.No\.|O\.S\.No\.|RT\.No\.|CMA\.No\.|FAO\(OS\)\.No\.)\s*[\d/\(\)]+\s*(?:of\s*\d{4})?',
        full_text
    )
    header["case_numbers"] = list(set(case_numbers))[:10]

    return header


def extract_acts_sections(full_text: str) -> list:
    """Find all Indian Acts and sections cited."""
    act_patterns = {
        "Indian Penal Code, 1860":                      r'(?:Sections?\s+[\d\[\]\(\)a-z,\s&/]+(?:of\s+)?IPC|IPC\s+[\d\[\]]+)',
        "Code of Criminal Procedure, 1973":             r'(?:Section\s+\d+\s+(?:of\s+)?Cr\.?P\.?C|CrPC\s+[\d]+)',
        "Bharatiya Nyaya Sanhita, 2023":               r'BNS\s+[\d]+',
        "Bharatiya Nagarik Suraksha Sanhita, 2023":   r'BNSS\s+[\d]+',
        "Indian Evidence Act, 1872":                   r'(?:Section\s+65B|Section\s+\d+\s+of\s+(?:the\s+)?Evidence Act)',
        "Code of Civil Procedure, 1908":               r'(?:Order\s+[IVXLC]+|Section\s+\d+\s+(?:of\s+)?CPC)',
        "Negotiable Instruments Act, 1881":            r'(?:Section\s+138|NI\s+Act\s+Section\s+\d+)',
        "Hindu Marriage Act, 1955":                    r'(?:HMA\s+\d+|Section\s+\d+\s+of\s+the\s+Hindu\s+Marriage)',
        "Transfer of Property Act, 1882":              r'(?:TPA\s+Section\s+\d+|Section\s+\d+\s+of\s+the\s+Transfer)',
        "SC/ST Prevention of Atrocities Act":          r'(?:SC/ST|Scheduled\s+Castes\s+and\s+Scheduled\s+Tribes).*?Section\s+\d+',
        "Specific Relief Act, 1963":                   r'Section\s+\d+\s+of\s+(?:the\s+)?Specific\s+Relief',
        "Limitation Act, 1963":                        r'Section\s+\d+\s+of\s+(?:the\s+)?Limitation\s+Act',
    }
    found_acts = []
    for act_name, pattern in act_patterns.items():
        matches = re.findall(pattern, full_text, re.IGNORECASE)
        if matches:
            sections_raw = " | ".join(set(m.strip() for m in matches[:6]))
            found_acts.append({"act": act_name, "matches_in_text": sections_raw})
    return found_acts


def extract_cited_cases(full_text: str) -> list:
    """Extract Supreme Court and High Court case citations."""
    # Patterns: AIR + SCC + Madras CTC
    patterns = [
        r'\d{4}\s+\[\d+\]\s+SCC\s+\d+\s+\[[^\]]+\]',          # 2014 [10] SCC 473 [Case Name]
        r'\d{4}\s*\(\d+\)\s+SCC\s+\d+',                         # (2007) 4 SCC 511
        r'AIR\s+\d{4}\s+SC\s+\d+',                              # AIR 1958 SC 350
        r'\d{4}\s+\[\d+\]\s+CTC\s+\d+',                         # 2016 [2] CTC 135
        r'\d{4}\s*\[\d+\]\s+SCALE\s+\d+',                       # 2019 [4] SCALE 622
    ]
    citations = []
    for pattern in patterns:
        matches = re.findall(pattern, full_text)
        citations.extend(m.strip() for m in matches)
    # Deduplicate
    return list(dict.fromkeys(citations))[:30]


def extract_held(full_text: str) -> list:
    """Extract 'held', 'observed', 'concluded' paragraphs — core legal findings."""
    held_patterns = [
        r'(?:this Court holds?|it is held|we hold|the court holds?)[^\n]{30,300}',
        r'(?:accordingly[,\s]+this Court)[^\n]{30,300}',
        r'(?:in the result|in the circumstances)[^\n]{30,300}',
        r'(?:the appeal is|the petition is|the suit is)\s+(?:allowed|dismissed|decreed)[^\n]{0,200}',
    ]
    held = []
    for pattern in held_patterns:
        matches = re.findall(pattern, full_text, re.IGNORECASE)
        held.extend(m.strip() for m in matches[:3])
    return held[:8]


def detect_domain(full_text: str) -> dict:
    """Detect case domain and sub-domain from keywords."""
    domain_keywords = {
        "criminal":       ["murder", "accused", "conviction", "sentence", "CrPC", "FIR", "cognizance"],
        "civil":          ["plaintiff", "defendant", "decree", "suit", "injunction", "CPC"],
        "family":         ["divorce", "matrimonial", "Hindu Marriage Act", "custody", "maintenance"],
        "property":       ["sale deed", "possession", "title", "encroachment", "partition", "TPA"],
        "cheque_bounce":  ["Section 138", "dishonour", "cheque", "NI Act", "drawer"],
        "consumer":       ["consumer", "deficiency", "service", "Consumer Protection Act"],
        "constitutional": ["Article", "writ", "fundamental right", "mandamus", "certiorari"],
    }
    scores = {}
    text_lower = full_text.lower()
    for domain, keywords in domain_keywords.items():
        scores[domain] = sum(1 for kw in keywords if kw.lower() in text_lower)
    primary   = max(scores, key=lambda k: scores[k])
    secondary = sorted(scores, key=lambda k: scores[k], reverse=True)[1]
    return {
        "primary_domain":   primary,
        "secondary_domain": secondary if scores[secondary] > 0 else None,
        "domain_scores":    {k: v for k, v in scores.items() if v > 0}
    }


def extract_keywords(full_text: str) -> list:
    """Generate keywords for RAG retrieval."""
    # High-value legal terms
    legal_terms = [
        "rarest of rare", "death sentence", "life imprisonment", "commutation",
        "honour killing", "inter-caste marriage", "criminal conspiracy", "hired killer",
        "CCTV evidence", "electronic evidence", "65B certificate", "test identification parade",
        "adverse inference", "acquittal", "conviction", "circumstantial evidence",
        "corroboration", "eyewitness", "forensic expert", "CDR call records",
        "preponderance of probabilities", "beyond reasonable doubt",
        "divorce cruelty", "mental cruelty", "maintenance", "custody",
        "cheque bounce", "Section 138", "presumption", "legally enforceable debt",
        "injunction", "balance of convenience", "prima facie case", "irreparable injury",
        "SC ST atrocities", "caste discrimination", "honour crime",
    ]
    found = [term for term in legal_terms if term.lower() in full_text.lower()]

    # Also extract proper nouns that look like legal principles
    principle_phrases = re.findall(
        r'(?:the principle of|it is settled law that|the law is well settled)[^\n]{20,120}',
        full_text, re.IGNORECASE
    )
    short_principles = [p.strip()[:80] for p in principle_phrases[:5]]

    return found + short_principles


# ════════════════════════════════════════════════════════════════
# LAYER 3 — ASSEMBLE FULL RECORD
# ════════════════════════════════════════════════════════════════

def build_record(pdf_path: str) -> dict:
    print(f"\n[1/6] Extracting text from {pdf_path}…")
    pages, full_text = extract_text(pdf_path)
    print(f"      {len(pages)} pages, {len(full_text):,} characters")

    print("[2/6] Extracting case header…")
    header = extract_case_header(full_text)

    print("[3/6] Detecting domain…")
    domain = detect_domain(full_text)

    print("[4/6] Extracting acts and sections…")
    acts = extract_acts_sections(full_text)

    print("[5/6] Extracting cited cases…")
    citations = extract_cited_cases(full_text)

    print("[6/6] Extracting held / outcome…")
    held = extract_held(full_text)
    keywords = extract_keywords(full_text)

    # Build short summary from first 600 chars of body text
    body_start = full_text[full_text.find("JUDGMENT"):][:600] if "JUDGMENT" in full_text else full_text[500:1100]
    summary_raw = re.sub(r'\s+', ' ', body_start).strip()
    summary     = summary_raw[:400] + "…" if len(summary_raw) > 400 else summary_raw

    # ID from filename
    pdf_name = Path(pdf_path).stem.replace(" ", "_")

    record = {
        # ── Identity ────────────────────────────────────────────────────────
        "id":                   f"judgment_{pdf_name}_{datetime.now().strftime('%Y%m%d')}",
        "source":               "Indian Kanoon",
        "source_url":           "",               # fill manually
        "pdf_path":             pdf_path,
        "total_pages":          len(pages),
        "extracted_at":         datetime.now().isoformat(),

        # ── Domain ──────────────────────────────────────────────────────────
        "primary_domain":       domain["primary_domain"],
        "secondary_domain":     domain["secondary_domain"],

        # ── Header ──────────────────────────────────────────────────────────
        "court":                header.get("court",        ""),
        "bench":                header.get("bench",        ""),
        "judges":               header.get("judges",       []),
        "case_numbers":         header.get("case_numbers", []),
        "reserved_on":          header.get("reserved_on",  ""),
        "delivered_on":         header.get("delivered_on", ""),

        # ── Fill manually (requires reading) ────────────────────────────────
        "case_name":            "",       # "Plaintiff/Petitioner v. Defendant/Respondent"
        "citation":             "",       # e.g. "(2020) HC Madras"
        "parties":              {         # fill after reading
            "petitioner":       "",
            "respondent":       "",
        },

        # ── Auto-extracted ───────────────────────────────────────────────────
        "acts_cited":           acts,
        "case_citations":       citations,
        "auto_summary":         summary,
        "held_statements":      held,
        "keywords":             keywords,

        # ── Fill manually after reading ──────────────────────────────────────
        "facts_of_case":        "",       # 2-3 sentence factual summary
        "issues_decided":       [],       # list of legal questions answered
        "legal_principles":     [],       # see format below

        # ── legal_principles format: ─────────────────────────────────────────
        # {
        #   "principle":    "One-line statement of the legal rule established",
        #   "held":         "What the court actually decided on this point",
        #   "applicable_sections": ["Act Section"],
        #   "cited_cases":  ["Citation 1", "Citation 2"],
        #   "favours":      "petitioner | respondent | neutral"
        # }

        "outcome":              "",       # one-line final order
        "relevance_score":      0,        # 1-5 (fill after reading)
        "precedent_value":      "",       # "High / Medium / Low"
        "use_for_drafting":     [],       # which case types this helps with
        "annotation_verified":  False,
        "annotated_by":         None,
        "dataset_version":      "1.0",
    }

    return record


# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads/Chinnasamy_vs_.PDF"

    record = build_record(pdf_path)

    # Save full record
    out_name = Path(pdf_path).stem.replace(" ", "_") + "_dataset.json"
    out_path = Path("/home/claude") / out_name
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    # Save principles-only file for RAG
    principles_path = out_path.parent / (out_path.stem + "_principles.json")
    principles_only = {
        "id":               record["id"],
        "court":            record["court"],
        "domain":           record["primary_domain"],
        "keywords":         record["keywords"],
        "legal_principles": record["legal_principles"],
        "held_statements":  record["held_statements"],
        "case_citations":   record["case_citations"][:10],
    }
    with open(principles_path, "w", encoding="utf-8") as f:
        json.dump(principles_only, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Full record   → {out_path}")
    print(f"✓ Principles    → {principles_path}")
    print(f"\nAuto-filled fields:  court, bench, judges, case_numbers, dates, acts_cited,")
    print(f"                     case_citations, keywords, held_statements, domain")
    print(f"Manual fields needed: case_name, parties, facts_of_case, legal_principles,")
    print(f"                      issues_decided, outcome, relevance_score, use_for_drafting")
    print(f"\nActs detected: {len(record['acts_cited'])}")
    print(f"Citations found: {len(record['case_citations'])}")
    print(f"Keywords: {len(record['keywords'])}")
