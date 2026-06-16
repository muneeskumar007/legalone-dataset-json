"""
batch_processor.py
──────────────────────────────────────────────────────────────────
STEP 1 of LegalOne Dataset Pipeline
Processes 30+ judgment PDFs in one go:
  - Extracts raw text from each PDF
  - Auto-detects domain, court, dates, acts, citations
  - Creates a shell JSON for each judgment (ready for manual annotation)
  - Generates a master index (batch_index.json)

Usage:
    python3 batch_processor.py --input /path/to/pdf/folder --output /path/to/output/folder
    python3 batch_processor.py --input ./pdfs --output ./dataset
"""

import argparse, json, re, os, sys
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

try:
    import pdfplumber
except ImportError:
    print("Run: pip install pdfplumber tqdm")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════
# CONFIG — DOMAIN DETECTION
# ═══════════════════════════════════════════════════════════════

DOMAIN_KEYWORDS = {
    "divorce": [
        "hindu marriage act", "section 13", "divorce", "matrimonial",
        "cruelty", "desertion", "adultery", "irretrievable breakdown",
        "restitution of conjugal rights", "judicial separation",
        "maintenance", "alimony", "section 25", "section 24"
    ],
    "cheque_bounce": [
        "section 138", "negotiable instruments", "dishonour",
        "cheque", "drawer", "payee", "legally enforceable debt",
        "insufficient funds", "ni act", "demand notice"
    ],
    "partition": [
        "partition", "coparcenary", "ancestral property", "joint family",
        "kartha", "mitakshara", "hindu succession", "coparcener",
        "preliminary decree", "final decree", "share"
    ],
    "maintenance": [
        "section 125 crpc", "section 144 bnss", "maintenance",
        "wife", "child maintenance", "neglect", "unable to maintain"
    ],
    "custody": [
        "custody", "guardianship", "welfare of child", "minor",
        "visitation", "section 26", "section 6 hmga"
    ],
    "domestic_violence": [
        "domestic violence", "protection order", "shared household",
        "pwdva", "section 12", "section 18", "section 19", "section 20"
    ],
    "land_acquisition": [
        "land acquisition", "compensation", "market value",
        "section 4", "section 6", "rfctlarr", "solatium",
        "reference court", "award"
    ],
    "murder_criminal": [
        "section 302", "ipc", "murder", "culpable homicide",
        "death sentence", "life imprisonment", "accused", "conviction"
    ],
    "property_dispute": [
        "title", "possession", "sale deed", "injunction",
        "specific performance", "declaration", "encroachment"
    ],
    "will_succession": [
        "will", "testator", "legatee", "probate", "letters of administration",
        "executor", "attestation", "bequeath", "succession"
    ]
}

COURT_NAMES = {
    "HIGH COURT OF JUDICATURE AT MADRAS":     "High Court of Judicature at Madras",
    "MADRAS HIGH COURT":                       "High Court of Judicature at Madras",
    "HIGH COURT OF JUDICATURE AT BOMBAY":      "High Court of Judicature at Bombay",
    "HIGH COURT OF DELHI":                     "High Court of Delhi",
    "SUPREME COURT OF INDIA":                  "Supreme Court of India",
    "HIGH COURT OF KARNATAKA":                 "High Court of Karnataka",
    "HIGH COURT OF JUDICATURE AT ALLAHABAD":   "High Court of Judicature at Allahabad",
    "HIGH COURT OF KERALA":                    "High Court of Kerala",
    "DISTRICT COURT":                          "District Court",
    "FAMILY COURT":                            "Family Court",
    "SESSIONS COURT":                          "Sessions Court",
}

ACT_PATTERNS = {
    "Hindu Marriage Act, 1955":              r'hindu marriage act|hma\s+\d+|section\s+\d+\s+of\s+the\s+hindu marriage',
    "Hindu Succession Act, 1956":            r'hindu succession act|section\s+6\s+hsa|section\s+15\s+hsa',
    "Hindu Minority and Guardianship Act":   r'hindu minority|hmga|section\s+6\s+hmg',
    "Code of Civil Procedure, 1908":         r'order\s+[ivxlc]+\s+rule|section\s+\d+\s+cpc|code of civil procedure',
    "Code of Criminal Procedure, 1973":      r'section\s+125\s+cr\.?p\.?c|crpc|code of criminal procedure',
    "Bharatiya Nagarik Suraksha Sanhita, 2023": r'bnss|section\s+\d+\s+bnss',
    "Indian Penal Code, 1860":               r'section\s+498.?a|ipc\s+section|section\s+302|section\s+307',
    "Bharatiya Nyaya Sanhita, 2023":         r'bns\s+section|section\s+\d+\s+bns',
    "Negotiable Instruments Act, 1881":      r'section\s+138|ni act|negotiable instruments act',
    "Protection of Women from DV Act, 2005": r'pwdva|domestic violence act|section\s+12\s+of\s+the\s+protection',
    "Hindu Succession Act, 1956 S.6":        r'section\s+6\s+of\s+the\s+hindu succession',
    "Indian Evidence Act, 1872":             r'section\s+65b|indian evidence act|section\s+101|section\s+102',
    "Specific Relief Act, 1963":             r'specific relief act|section\s+34|section\s+38',
    "Transfer of Property Act, 1882":        r'transfer of property act|section\s+54\s+tpa',
    "Registration Act, 1908":               r'registration act|section\s+17\(1\)',
    "Limitation Act, 1963":                  r'limitation act|article\s+\d+\s+of\s+the\s+limitation',
}


# ═══════════════════════════════════════════════════════════════
# EXTRACTION HELPERS
# ═══════════════════════════════════════════════════════════════

def extract_text(pdf_path: str) -> tuple:
    pages, chunks = [], []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                text = re.sub(r'http\S+', '', text)
                text = re.sub(r'Indian Kanoon.*', '', text, flags=re.IGNORECASE)
                text = re.sub(r'www\.mhc\.tn\.gov\.in\S*', '', text)
                text = re.sub(r'Uploaded on:.*?\)', '', text)
                pages.append({"page": i+1, "text": text.strip()})
                chunks.append(text.strip())
    except Exception as e:
        return [], "", str(e)
    return pages, "\n\n".join(chunks), None


def detect_domain(text: str) -> tuple:
    text_lower = text.lower()
    scores = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        scores[domain] = sum(1 for kw in keywords if kw in text_lower)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary   = ranked[0][0] if ranked[0][1] > 0 else "unknown"
    secondary = ranked[1][0] if len(ranked) > 1 and ranked[1][1] > 0 else None
    return primary, secondary, scores


def detect_court(text: str) -> str:
    text_upper = text.upper()[:3000]
    for key, name in COURT_NAMES.items():
        if key in text_upper:
            return name
    return "Unknown Court"


def detect_bench(text: str) -> str:
    text_upper = text.upper()[:3000]
    judge_count = len(re.findall(r'JUSTICE\s+[A-Z]', text_upper))
    if judge_count >= 3: return "Full Bench"
    if judge_count == 2: return "Division Bench"
    return "Single Judge"


def detect_judges(text: str) -> list:
    matches = re.findall(
        r'(?:JUSTICE|MR\.\s*JUSTICE|MRS\.\s*JUSTICE|DR\.\s*JUSTICE)\s+([A-Z][A-Z\.\s]+?)(?:\n|AND\b|,)',
        text.upper()[:3000]
    )
    judges = []
    seen = set()
    for m in matches:
        name = m.strip().title()
        if 3 < len(name) < 60 and name not in seen:
            judges.append(name + " J.")
            seen.add(name)
    return judges[:4]


def detect_dates(text: str) -> dict:
    dates = {}
    res = re.search(r'Reserved\s+on\s*[:\-]?\s*(\d{2}[\.\-/]\d{2}[\.\-/]\d{4})', text, re.IGNORECASE)
    del_ = re.search(r'Delivered\s+on\s*[:\-]?\s*(\d{2}[\.\-/]\d{2}[\.\-/]\d{4})', text, re.IGNORECASE)
    dec  = re.search(r'(?:Decided|Pronounced)\s+on\s*[:\-]?\s*(\d{2}[\.\-/]\d{2}[\.\-/]\d{4})', text, re.IGNORECASE)
    if res:  dates["reserved_on"]  = res.group(1).replace("-",".").replace("/",".")
    if del_: dates["delivered_on"] = del_.group(1).replace("-",".").replace("/",".")
    if dec and "delivered_on" not in dates: dates["delivered_on"] = dec.group(1)
    return dates


def detect_case_numbers(text: str) -> list:
    patterns = [
        r'[A-Z]\.?[A-Z]\.?(?:No|Appeal|Petition|Suit)\.?\s*\d+\s*(?:of|/)\s*\d{4}',
        r'W\.P(?:\.M\.B)?\.No\.\s*\d+\s*of\s*\d{4}',
        r'O\.S\.No\.\s*\d+\s*(?:of|/)\s*\d{4}',
        r'A\.S\.No\.\s*\d+\s*(?:of|/)\s*\d{4}',
        r'Crl\.A\.No\.\s*\d+\s*(?:of|/)\s*\d{4}',
        r'M\.A\.No\.\s*\d+\s*(?:of|/)\s*\d{4}',
        r'CMA\.No\.\s*\d+\s*(?:of|/)\s*\d{4}',
        r'RT\.No\.\s*\d+\s*(?:of|/)\s*\d{4}',
        r'HMA\.No\.\s*\d+\s*(?:of|/)\s*\d{4}',
        r'Mat\.Appeal\.No\.\s*\d+\s*(?:of|/)\s*\d{4}',
    ]
    found = []
    for pat in patterns:
        found.extend(re.findall(pat, text[:3000], re.IGNORECASE))
    return list(dict.fromkeys(m.strip() for m in found))[:8]


def detect_acts(text: str) -> list:
    text_lower = text.lower()
    found = []
    for act_name, pattern in ACT_PATTERNS.items():
        if re.search(pattern, text_lower):
            found.append(act_name)
    return found


def detect_citations(text: str) -> list:
    patterns = [
        r'\(\d{4}\)\s+\d+\s+SCC\s+\d+',
        r'\d{4}\s+\(\d+\)\s+SCC\s+\d+',
        r'AIR\s+\d{4}\s+SC\s+\d+',
        r'\d{4}\s+\[\d+\]\s+CTC\s+\d+',
        r'\d{4}\s+\[\d+\]\s+SCALE\s+\d+',
        r'AIR\s+\d{4}\s+(?:Mad|Bom|Del|Cal|Ker|Kar)\s+\d+',
        r'\d{4}\s+SCC\s+OnLine\s+\w+\s+\d+',
    ]
    found = []
    for pat in patterns:
        found.extend(re.findall(pat, text))
    return list(dict.fromkeys(m.strip() for m in found))[:25]


def detect_neutral_citation(text: str) -> str:
    m = re.search(r'\d{4}:\w{2,6}:\d+', text[:2000])
    return m.group(0) if m else None


def detect_outcome(text: str) -> str:
    patterns = [
        r'(?:the appeal is|this appeal is)\s+(allowed|dismissed|partly allowed)',
        r'(?:the petition is|this petition is)\s+(allowed|dismissed)',
        r'(?:the suit is|the suit stands)\s+(decreed|dismissed)',
        r'(?:writ petition is|writ petition stands)\s+(allowed|dismissed)',
        r'(?:in the result|as a result)[,\s]+(the\s+\w+\s+(?:is|are)\s+(?:allowed|dismissed))',
        r'(?:the order of|the judgment of)\s+.{0,50}\s+is\s+(upheld|set aside|confirmed|modified)',
    ]
    for pat in patterns:
        m = re.search(pat, text[-8000:], re.IGNORECASE)
        if m:
            return m.group(0)[:200].strip()
    return None


def detect_indian_kanoon_url(text: str) -> str:
    m = re.search(r'https?://indiankanoon\.org/doc/\d+/?', text)
    return m.group(0) if m else None


def extract_case_name_from_text(text: str, filename: str) -> str:
    # Try first line approach
    lines = [l.strip() for l in text[:1000].split('\n') if l.strip()]
    for line in lines[:5]:
        if ' vs ' in line.lower() or ' v. ' in line.lower() or ' versus ' in line.lower():
            return line[:150]
    # Fallback: use filename
    return Path(filename).stem.replace('_', ' ').replace('-', ' ')


def make_id(case_name: str, court: str, year: str) -> str:
    court_code = {
        "Madras": "MAD", "Bombay": "BOM", "Delhi": "DEL",
        "Karnataka": "KAR", "Allahabad": "ALL", "Kerala": "KER",
        "Supreme Court": "SC"
    }
    cc = next((v for k, v in court_code.items() if k in court), "HC")
    # Clean case name
    name_clean = re.sub(r'[^a-zA-Z\s]', '', case_name)
    words = name_clean.split()[:4]
    name_part = "_".join(w.capitalize() for w in words if len(w) > 2)[:40]
    return f"{cc}_{year}_{name_part}"


# ═══════════════════════════════════════════════════════════════
# SHELL RECORD BUILDER
# ═══════════════════════════════════════════════════════════════

def build_shell_record(pdf_path: str, pages: list, full_text: str) -> dict:
    filename = Path(pdf_path).name
    dates    = detect_dates(full_text)
    year     = dates.get("delivered_on", "0000")[-4:] or "0000"
    court    = detect_court(full_text)
    judges   = detect_judges(full_text)
    bench    = detect_bench(full_text)
    primary, secondary, domain_scores = detect_domain(full_text)
    case_numbers = detect_case_numbers(full_text)
    acts     = detect_acts(full_text)
    citations= detect_citations(full_text)
    outcome  = detect_outcome(full_text)
    neutral  = detect_neutral_citation(full_text)
    ik_url   = detect_indian_kanoon_url(full_text)
    case_name= extract_case_name_from_text(full_text, filename)
    rec_id   = make_id(case_name, court, year)

    record = {
        # ── IDENTITY ────────────────────────────────────────────────────────
        "id":               rec_id,
        "neutral_citation": neutral,
        "source":           "Indian Kanoon",
        "source_url":       ik_url or "",
        "pdf_filename":     filename,
        "total_pages":      len(pages),
        "extracted_at":     datetime.now().isoformat(),

        # ── DOMAIN ──────────────────────────────────────────────────────────
        "domain":           primary,
        "sub_domain":       secondary or "",
        "domain_scores":    {k:v for k,v in domain_scores.items() if v > 0},

        # ── COURT ───────────────────────────────────────────────────────────
        "court":            court,
        "bench":            bench,
        "judges":           judges,
        "case_numbers":     case_numbers,
        "trial_court":      "",
        "reserved_on":      dates.get("reserved_on", ""),
        "delivered_on":     dates.get("delivered_on", ""),

        # ── PARTIES (manual fill) ────────────────────────────────────────────
        "case_name":        case_name,
        "parties": {
            "petitioner_plaintiff": "TODO — fill manually",
            "respondent_defendant": "TODO — fill manually",
            "other_parties":        []
        },

        # ── AUTO-EXTRACTED ───────────────────────────────────────────────────
        "acts_cited_auto":  acts,
        "case_citations":   citations,
        "outcome_detected": outcome or "",

        # ── MANUAL ANNOTATION REQUIRED ───────────────────────────────────────
        "acts_cited": [
            {"act": act, "sections": ["TODO — add relevant sections"]}
            for act in acts[:6]
        ],
        "facts_of_case":   "TODO — 3-5 sentence summary",
        "issues_decided":  [
            {"issue_no": 1, "question": "TODO", "answer": "TODO"}
        ],

        # ── LEGAL PRINCIPLES (most important — fill carefully) ───────────────
        "legal_principles": [
            {
                "principle_id": "LP_001",
                "principle":    "TODO — one line reusable rule",
                "held":         "TODO — what court actually said (2-4 sentences)",
                "applicable_acts_sections": ["TODO"],
                "cited_cases":  [],
                "keywords":     ["TODO"],
                "favours":      "plaintiff / defendant / neutral",
                "use_in":       ["TODO — case types"],
                "significance": "HIGH / MEDIUM / LOW — one reason"
            }
        ],

        # ── OUTCOME ──────────────────────────────────────────────────────────
        "outcome": {
            "result":        outcome or "TODO",
            "final_order":   "TODO — 2-3 sentence summary",
            "relief_granted":"TODO",
            "costs":         "TODO"
        },

        # ── KEYWORDS ─────────────────────────────────────────────────────────
        "keywords": ["TODO — add 15+ keywords after reading"],

        # ── METADATA ─────────────────────────────────────────────────────────
        "relevance_score":      0,
        "precedent_value":      "TODO",
        "use_for_drafting":     ["TODO"],
        "annotation_verified":  False,
        "annotation_status":    "pending",
        "annotated_by":         None,
        "dataset_version":      "1.0",
    }
    return record


# ═══════════════════════════════════════════════════════════════
# BATCH PROCESSOR
# ═══════════════════════════════════════════════════════════════

def process_batch(input_dir: str, output_dir: str):
    input_path  = Path(input_dir)
    output_path = Path(output_dir)

    # Create output folder structure
    for sub in ["pending_annotation", "verified", "principles_only", "faiss_index", "logs"]:
        (output_path / sub).mkdir(parents=True, exist_ok=True)

    # Find all PDFs
    pdfs = list(input_path.glob("*.pdf")) + list(input_path.glob("*.PDF"))
    if not pdfs:
        print(f"No PDFs found in {input_dir}")
        return

    print(f"\nFound {len(pdfs)} PDFs in {input_dir}")
    print("="*60)

    batch_index  = []
    errors       = []
    domain_count = {}

    for pdf_path in tqdm(pdfs, desc="Processing", unit="pdf"):
        try:
            pages, full_text, error = extract_text(str(pdf_path))

            if error or not full_text.strip():
                errors.append({"file": pdf_path.name, "error": error or "Empty text"})
                continue

            record = build_shell_record(str(pdf_path), pages, full_text)

            # Save individual JSON
            out_file = output_path / "pending_annotation" / (pdf_path.stem + ".json")
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False, indent=2)

            # Track in index
            domain = record["domain"]
            domain_count[domain] = domain_count.get(domain, 0) + 1

            batch_index.append({
                "pdf_filename":   pdf_path.name,
                "json_filename":  out_file.name,
                "id":             record["id"],
                "case_name":      record["case_name"],
                "court":          record["court"],
                "domain":         record["domain"],
                "sub_domain":     record["sub_domain"],
                "delivered_on":   record["delivered_on"],
                "acts_detected":  len(record["acts_cited_auto"]),
                "citations_found":len(record["case_citations"]),
                "pages":          record["total_pages"],
                "annotation_status": "pending",
            })

        except Exception as e:
            errors.append({"file": pdf_path.name, "error": str(e)})

    # Save batch index
    index_path = output_path / "batch_index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump({
            "created_at":   datetime.now().isoformat(),
            "total_pdfs":   len(pdfs),
            "processed":    len(batch_index),
            "errors":        len(errors),
            "domain_breakdown": domain_count,
            "judgments":    batch_index
        }, f, ensure_ascii=False, indent=2)

    # Save error log
    if errors:
        with open(output_path / "logs" / "errors.json", "w") as f:
            json.dump(errors, f, indent=2)

    # Print summary
    print("\n" + "="*60)
    print(f"  BATCH COMPLETE")
    print("="*60)
    print(f"  Total PDFs       : {len(pdfs)}")
    print(f"  Processed        : {len(batch_index)}")
    print(f"  Errors           : {len(errors)}")
    print(f"\n  Domain Breakdown:")
    for domain, count in sorted(domain_count.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * count
        print(f"    {domain:<25} {bar} {count}")
    print(f"\n  Output folder    : {output_path}")
    print(f"  Batch index      : {index_path}")
    print(f"\n  Next step: Run annotator.py to fill TODO fields")
    print("="*60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LegalOne Batch PDF Processor")
    parser.add_argument("--input",  default="./pdfs",    help="Folder containing judgment PDFs")
    parser.add_argument("--output", default="./dataset", help="Output folder for JSON files")
    args = parser.parse_args()
    process_batch(args.input, args.output)
