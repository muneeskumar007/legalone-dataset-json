"""
auto_annotator.py
─────────────────────────────────────────────────────────────────
AUTOMATED annotation using Ollama (Llama 3) — completely free.
Reads each judgment JSON shell, sends text to Ollama,
parses the structured response, fills all TODO fields.

Modes:
  --mode ollama   : Use local Ollama (Llama 3) — free, private
  --mode template : Rule-based only — no LLM needed at all
  --mode hybrid   : Template first, Ollama fills gaps (recommended)

Usage:
  python3 auto_annotator.py --mode ollama   --input ./dataset/pending_annotation
  python3 auto_annotator.py --mode template --input ./dataset/pending_annotation
  python3 auto_annotator.py --mode hybrid   --input ./dataset/pending_annotation
  python3 auto_annotator.py --mode ollama   --file ./dataset/pending_annotation/MyCase.json
  python3 auto_annotator.py --mode ollama   --domain divorce
"""

import argparse, json, re, time, requests
from pathlib import Path
from datetime import datetime

OLLAMA_URL   = "http://localhost:11434"
OLLAMA_MODEL = "llama3"   # change to "phi3" if low RAM
TIMEOUT      = 880        # seconds per LLM call


# ═══════════════════════════════════════════════════════════════
# OLLAMA CALLER
# ═══════════════════════════════════════════════════════════════

def ollama_available() -> bool:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return r.status_code == 200
    except:
        return False


def call_ollama(prompt: str, system: str = "", temperature: float = 0.1) -> str:
    """Call Ollama and return the text response."""
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system",  "content": system},
                    {"role": "user",    "content": prompt}
                ],
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": 2000,
                    "top_p": 0.9
                }
            },
            timeout=TIMEOUT
        )
        if resp.status_code == 200:
            return resp.json().get("message", {}).get("content", "").strip()
    except Exception as e:
        print(f"    [Ollama error] {e}")
    return ""


def call_ollama_json(prompt: str, system: str = "") -> dict:
    """
    Call Ollama and parse JSON from the response.
    Strips markdown fences and handles partial JSON.
    """
    raw = call_ollama(prompt, system, temperature=0.05)
    if not raw:
        return {}
    # Strip markdown code fences
    raw = re.sub(r'```(?:json)?', '', raw).strip().rstrip('`').strip()
    # Find JSON object in response
    start = raw.find('{')
    end   = raw.rfind('}')
    if start != -1 and end != -1:
        json_str = raw[start:end+1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Try to fix common issues
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            try:
                return json.loads(json_str)
            except:
                pass
    return {}


# ═══════════════════════════════════════════════════════════════
# LLM ANNOTATION PROMPTS
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are a senior Indian legal researcher with 20 years of experience.
You extract structured information from Indian court judgments.
Always respond with ONLY valid JSON — no explanation, no markdown, no preamble.
Be precise. If information is not in the text, use null or empty string.
For legal principles, extract ONLY rules the court actually applied — not arguments."""


def build_facts_prompt(record: dict, text_excerpt: str) -> str:
    return f"""Extract key information from this Indian court judgment.

JUDGMENT EXCERPT (first 3000 chars):
{text_excerpt[:3000]}

ALREADY KNOWN:
- Court: {record.get('court','')}
- Domain: {record.get('domain','')}
- Acts cited: {', '.join(record.get('acts_cited_auto',[])[:5])}
- Outcome detected: {record.get('outcome_detected','')}

Return ONLY this JSON (no other text):
{{
  "case_name": "Petitioner v. Respondent — full case name",
  "petitioner": "name and brief role (e.g. husband, wife, plaintiff)",
  "respondent": "name and brief role",
  "trial_court": "trial court name and case number if mentioned",
  "facts_of_case": "3-5 sentence summary: who the parties are, what happened, what relief claimed, what trial court decided, why this case came to appeal",
  "sub_domain": "one of: divorce_cruelty / divorce_desertion / divorce_mcd / maintenance / custody / partition / cheque_bounce / murder / property_dispute / will_succession",
  "outcome_result": "one of: Appeal allowed / Appeal dismissed / Suit decreed / Suit dismissed / Writ allowed / Writ dismissed / Modified",
  "outcome_order": "2-3 sentence description of what the final court order said",
  "year": "4-digit year of judgment"
}}"""


def build_principles_prompt(record: dict, full_text: str) -> str:
    domain = record.get("domain", "civil")
    acts   = ", ".join(record.get("acts_cited_auto", [])[:4])

    # Send the most legally rich portion of the text
    # Judgments usually have reasoning in the middle section
    text_len = len(full_text)
    excerpt  = full_text[text_len//4 : (text_len*3)//4][:4000]

    return f"""Extract legal principles from this Indian court judgment.

DOMAIN: {domain}
ACTS CITED: {acts}

JUDGMENT TEXT (middle section — where legal reasoning is):
{excerpt}

A legal principle is a REUSABLE RULE that could apply to other cases.
Look for: "it is held that", "settled law", "this court holds", "the law is clear", 
"burden lies on", "the principle is", "in view of the above".

Return ONLY this JSON array (2-5 principles, no other text):
{{
  "legal_principles": [
    {{
      "principle": "One clear sentence stating the legal rule — must be reusable across cases",
      "held": "2-3 sentences of what the court ACTUALLY said — quote or closely paraphrase",
      "applicable_acts_sections": ["Act Name — Section X", "Act Name — Section Y"],
      "cited_cases": ["Case Name, (Year) X SCC Y"],
      "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
      "favours": "plaintiff or defendant or neutral",
      "use_in": ["case type 1", "case type 2"],
      "significance": "HIGH or MEDIUM or LOW — one reason why"
    }}
  ]
}}"""


def build_keywords_prompt(record: dict, text_excerpt: str) -> str:
    existing_kws = [k for k in record.get("keywords",[]) if k.lower() != "todo"]
    return f"""Generate keywords for this Indian court judgment for legal database search.

CASE: {record.get('case_name','')}
DOMAIN: {record.get('domain','')}
ACTS: {', '.join(record.get('acts_cited_auto',[])[:4])}
EXISTING KEYWORDS: {', '.join(existing_kws[:5])}

TEXT SAMPLE:
{text_excerpt[:1500]}

Return ONLY this JSON (no other text):
{{
  "keywords": ["keyword1", "keyword2", "..."],
  "relevance_score": 3,
  "use_for_drafting": ["use case 1", "use case 2", "use case 3"]
}}

Rules:
- 15-25 keywords
- Mix of: legal terms + section numbers + factual terms + Latin maxims if any
- relevance_score: 5=Supreme Court/landmark, 4=HC Division Bench, 3=HC Single Judge, 2=District/Family Court
- use_for_drafting: specific practical use cases for advocates"""


# ═══════════════════════════════════════════════════════════════
# TEMPLATE (RULE-BASED) ANNOTATOR — no LLM needed
# ═══════════════════════════════════════════════════════════════

# Domain-specific principle templates
DOMAIN_PRINCIPLE_TEMPLATES = {
    "divorce": [
        {
            "principle": "Mental cruelty as a ground for divorce must be assessed based on the entire matrimonial life and not isolated incidents",
            "held": "The court must look at the cumulative effect of the conduct of the respondent on the petitioner's mental health. Individual acts may appear trivial but their overall impact may constitute cruelty.",
            "applicable_acts_sections": ["Hindu Marriage Act, 1955 — Section 13(1)(ia)"],
            "keywords": ["mental cruelty", "divorce", "matrimonial cruelty", "cumulative effect"],
            "favours": "neutral", "significance": "HIGH"
        },
        {
            "principle": "Desertion requires both factum deserendi and animus deserendi — physical separation alone is insufficient",
            "held": "For desertion to be proved under Section 13(1)(ib) HMA, the petitioner must establish both the factum of desertion (physical separation) and the animus deserendi (intention to permanently desert). Absence without animus is not desertion in law.",
            "applicable_acts_sections": ["Hindu Marriage Act, 1955 — Section 13(1)(ib)"],
            "keywords": ["desertion", "animus deserendi", "factum deserendi", "separation", "divorce desertion ground"],
            "favours": "neutral", "significance": "HIGH"
        }
    ],
    "cheque_bounce": [
        {
            "principle": "Presumption under Section 139 NI Act in favour of holder is rebuttable on preponderance of probabilities",
            "held": "Once the complainant establishes that the cheque was issued and dishonoured, Section 139 NI Act raises a presumption of legally enforceable debt. The accused can rebut this presumption by raising a probable defence — not proof beyond reasonable doubt.",
            "applicable_acts_sections": ["Negotiable Instruments Act, 1881 — Section 138", "Negotiable Instruments Act, 1881 — Section 139"],
            "keywords": ["cheque bounce", "section 138", "presumption", "legally enforceable debt", "rebuttal"],
            "favours": "plaintiff", "significance": "HIGH"
        }
    ],
    "partition": [
        {
            "principle": "When joint family has sufficient ancestral nucleus, burden lies on kartha to prove properties purchased from independent income",
            "held": "In partition suits, once the plaintiff establishes existence of a joint family with ancestral properties capable of yielding income, the burden shifts to the party claiming self-acquisition to prove that the purchase was made from a source other than joint family funds.",
            "applicable_acts_sections": ["Hindu Succession Act, 1956 — Section 6", "Code of Civil Procedure, 1908 — Order XX Rule 18"],
            "keywords": ["partition", "joint family nucleus", "kartha burden", "ancestral property", "self acquired property"],
            "favours": "plaintiff", "significance": "HIGH"
        }
    ],
    "maintenance": [
        {
            "principle": "Maintenance under Section 125 CrPC is a social welfare provision to prevent destitution and must be liberally construed",
            "held": "Section 125 CrPC is a measure of social justice applicable to all persons regardless of religion. Courts must adopt a liberal interpretation to prevent vagrancy and destitution. The purpose is not punitive but protective.",
            "applicable_acts_sections": ["Code of Criminal Procedure, 1973 — Section 125", "Bharatiya Nagarik Suraksha Sanhita, 2023 — Section 144"],
            "keywords": ["maintenance", "section 125 crpc", "social welfare", "wife maintenance", "child maintenance"],
            "favours": "respondent", "significance": "HIGH"
        }
    ],
    "criminal": [
        {
            "principle": "In criminal cases, prosecution must prove guilt beyond reasonable doubt — benefit of doubt goes to accused",
            "held": "The standard of proof in criminal cases is proof beyond reasonable doubt. Any doubt that arises from the evidence must be resolved in favour of the accused. This is a cardinal principle of criminal jurisprudence.",
            "applicable_acts_sections": ["Indian Evidence Act, 1872 — Section 101", "Code of Criminal Procedure, 1973 — Section 313"],
            "keywords": ["beyond reasonable doubt", "burden of proof", "benefit of doubt", "criminal standard"],
            "favours": "defendant", "significance": "HIGH"
        }
    ]
}

def get_template_principles(domain: str) -> list:
    """Get domain-specific template principles."""
    templates = DOMAIN_PRINCIPLE_TEMPLATES.get(domain, [])
    # Add principle IDs
    for i, t in enumerate(templates):
        t["principle_id"] = f"LP_{i+1:03d}"
        if "cited_cases" not in t:
            t["cited_cases"] = []
        if "use_in" not in t:
            t["use_in"] = [domain]
    return templates


def template_annotate(record: dict) -> dict:
    """
    Rule-based annotation — no LLM.
    Uses domain detection, keyword analysis, and templates.
    Fast but less accurate than LLM.
    """
    domain = record.get("domain", "")

    # Auto-generate facts from available info
    case_name    = record.get("case_name", "")
    court        = record.get("court", "")
    date         = record.get("delivered_on", "")
    acts         = ", ".join(record.get("acts_cited_auto", [])[:3])
    outcome_det  = record.get("outcome_detected", "")
    citations    = record.get("case_citations", [])

    auto_facts = (
        f"This is a {domain} case decided by {court} on {date}. "
        f"The case involves {case_name}. "
        f"Relevant statutes include {acts}. "
        + (f"The court {outcome_det}." if outcome_det else "")
    ).strip()

    # Get domain-specific template principles
    principles = get_template_principles(domain)

    # Auto-generate keywords
    acts_kws = [a.lower().replace(",","").replace(".","")
                for a in record.get("acts_cited_auto",[])[:5]]
    domain_kws = domain.replace("_", " ").split()
    citation_years = list(set(
        re.findall(r'\b(19|20)\d{2}\b', " ".join(record.get("case_citations",[])))
    ))[:3]
    auto_keywords = list(set(
        acts_kws + domain_kws +
        [case_name.lower()[:30]] +
        [court.lower().replace("high court of judicature at","").strip()[:20]] +
        citation_years
    ))
    auto_keywords = [k for k in auto_keywords if len(k) > 3][:20]

    # Relevance score from court type
    court_upper = court.upper()
    if "SUPREME COURT" in court_upper:
        relevance = 5
    elif "DIVISION BENCH" in record.get("bench","").upper():
        relevance = 4
    elif "HIGH COURT" in court_upper:
        relevance = 3
    else:
        relevance = 2

    record.update({
        "facts_of_case":    auto_facts,
        "legal_principles": principles,
        "keywords":         auto_keywords,
        "relevance_score":  relevance,
        "outcome": {
            "result":        outcome_det or f"{domain} case — see full judgment",
            "final_order":   outcome_det or "",
            "relief_granted":"",
            "costs":         "",
        },
        "use_for_drafting":  [f"{domain} petition", f"{domain} arguments", f"Citing {domain} precedents"],
        "annotation_status": "auto_template",
        "annotation_verified": False,
        "annotated_by":     "auto_template_engine",
        "updated_at":       datetime.now().isoformat(),
    })
    return record


# ═══════════════════════════════════════════════════════════════
# LLM ANNOTATOR
# ═══════════════════════════════════════════════════════════════

def llm_annotate(record: dict, full_text: str, verbose: bool = True) -> dict:
    """
    Full LLM-powered annotation using Ollama.
    Makes 3 separate calls:
      1. Extract facts, parties, outcome
      2. Extract legal principles
      3. Generate keywords and metadata
    """
    case_name = record.get("case_name", "Unknown")
    if verbose:
        print(f"    [LLM] Annotating: {case_name[:50]}")

    # ── Call 1: Facts + parties + outcome ──────────────────────
    if verbose: print("    [1/3] Extracting facts and parties…")
    facts_data = call_ollama_json(
        build_facts_prompt(record, full_text),
        SYSTEM_PROMPT
    )
    time.sleep(1)

    # ── Call 2: Legal principles ────────────────────────────────
    if verbose: print("    [2/3] Extracting legal principles…")
    principles_data = call_ollama_json(
        build_principles_prompt(record, full_text),
        SYSTEM_PROMPT
    )
    time.sleep(1)

    # ── Call 3: Keywords + metadata ─────────────────────────────
    if verbose: print("    [3/3] Generating keywords…")
    keywords_data = call_ollama_json(
        build_keywords_prompt(record, full_text),
        SYSTEM_PROMPT
    )
    time.sleep(1)

    # ── Merge results ────────────────────────────────────────────
    if facts_data:
        if facts_data.get("case_name"):
            record["case_name"] = facts_data["case_name"]
        if facts_data.get("petitioner"):
            record.setdefault("parties", {})["petitioner_plaintiff"] = facts_data["petitioner"]
        if facts_data.get("respondent"):
            record.setdefault("parties", {})["respondent_defendant"] = facts_data["respondent"]
        if facts_data.get("trial_court"):
            record["trial_court"] = facts_data["trial_court"]
        if facts_data.get("facts_of_case"):
            record["facts_of_case"] = facts_data["facts_of_case"]
        if facts_data.get("sub_domain"):
            record["sub_domain"] = facts_data["sub_domain"]
        if facts_data.get("outcome_result") or facts_data.get("outcome_order"):
            record["outcome"] = {
                "result":        facts_data.get("outcome_result", ""),
                "final_order":   facts_data.get("outcome_order", ""),
                "relief_granted":"",
                "costs":         "",
            }

    if principles_data and principles_data.get("legal_principles"):
        raw_lps = principles_data["legal_principles"]
        clean_lps = []
        for i, lp in enumerate(raw_lps):
            if not lp.get("principle") or len(lp.get("principle","")) < 15:
                continue
            lp["principle_id"] = f"LP_{i+1:03d}"
            # Ensure all required fields exist
            lp.setdefault("held",         "")
            lp.setdefault("applicable_acts_sections", [])
            lp.setdefault("cited_cases",  [])
            lp.setdefault("keywords",     [])
            lp.setdefault("favours",      "neutral")
            lp.setdefault("use_in",       [record.get("domain","")])
            lp.setdefault("significance", "MEDIUM")
            clean_lps.append(lp)
        if clean_lps:
            record["legal_principles"] = clean_lps

    if keywords_data:
        if keywords_data.get("keywords"):
            record["keywords"] = keywords_data["keywords"]
        if keywords_data.get("relevance_score"):
            record["relevance_score"] = int(keywords_data["relevance_score"])
        if keywords_data.get("use_for_drafting"):
            record["use_for_drafting"] = keywords_data["use_for_drafting"]

    record["annotation_status"]  = "auto_llm"
    record["annotation_verified"] = False
    record["annotated_by"]        = f"ollama_{OLLAMA_MODEL}"
    record["updated_at"]          = datetime.now().isoformat()

    return record


# ═══════════════════════════════════════════════════════════════
# HYBRID ANNOTATOR
# ═══════════════════════════════════════════════════════════════

def hybrid_annotate(record: dict, full_text: str, verbose: bool = True) -> dict:
    """
    Template first, then Ollama fills gaps.
    Fastest mode that still uses LLM for principles.
    """
    # Step 1: template fills basics
    record = template_annotate(record)

    # Step 2: LLM improves legal principles and facts
    if verbose: print("    [Hybrid] Running LLM on top of template…")

    # Only call LLM for principles (most valuable)
    principles_data = call_ollama_json(
        build_principles_prompt(record, full_text),
        SYSTEM_PROMPT
    )

    if principles_data and principles_data.get("legal_principles"):
        raw_lps = principles_data["legal_principles"]
        clean_lps = []
        for i, lp in enumerate(raw_lps):
            if lp.get("principle") and len(lp.get("principle","")) > 15:
                lp["principle_id"] = f"LP_{i+1:03d}"
                lp.setdefault("cited_cases", [])
                lp.setdefault("use_in", [record.get("domain","")])
                clean_lps.append(lp)
        if clean_lps:
            record["legal_principles"] = clean_lps
            record["annotation_status"] = "auto_hybrid"
            record["annotated_by"]      = f"hybrid_template+{OLLAMA_MODEL}"

    return record


# ═══════════════════════════════════════════════════════════════
# LOAD FULL TEXT FROM DATABASE / JSON
# ═══════════════════════════════════════════════════════════════

def load_full_text(record: dict) -> str:
    """Try to reload PDF text for LLM processing."""
    pdf_name = record.get("pdf_filename","")
    for search_dir in ["./pdfs", "../pdfs", "./dataset/pdfs", "."]:
        pdf_path = Path(search_dir) / pdf_name
        if pdf_path.exists():
            try:
                import pdfplumber
                with pdfplumber.open(str(pdf_path)) as pdf:
                    text = "\n\n".join(
                        (page.extract_text() or "") for page in pdf.pages
                    )
                    return text
            except: pass

    # Fallback: use whatever is already in the record
    return " ".join([
        record.get("facts_of_case",""),
        " ".join(record.get("keywords",[])),
        " ".join(str(v) for v in record.get("acts_cited_auto",[])),
    ])


# ═══════════════════════════════════════════════════════════════
# BATCH RUNNER
# ═══════════════════════════════════════════════════════════════

def run_auto_annotate(
    folder:       str,
    mode:         str  = "hybrid",
    domain_filter:str  = None,
    single_file:  str  = None,
    skip_done:    bool = True,
    verbose:      bool = True
):
    print("\n" + "═"*58)
    print(f"  Auto-Annotator — Mode: {mode.upper()}")
    print("═"*58)

    # Check Ollama if needed
    if mode in ("ollama","hybrid"):
        if not ollama_available():
            print(f"\n  ⚠ Ollama not running at {OLLAMA_URL}")
            print("  Start with: ollama serve")
            print("  Then pull:  ollama pull llama3")
            if mode == "ollama":
                print("  Falling back to template mode…")
                mode = "template"
            else:
                print("  Falling back to template-only hybrid…")

    # Collect files
    if single_file:
        files = [Path(single_file)]
    else:
        folder_path = Path(folder)
        all_files   = sorted(folder_path.glob("*.json"))
        files       = [f for f in all_files if f.name != "batch_index.json"]

        if domain_filter:
            filtered = []
            for jf in files:
                try:
                    with open(jf) as f:
                        d = json.load(f).get("domain","")
                    if domain_filter.lower() in d.lower():
                        filtered.append(jf)
                except: pass
            files = filtered

    # Skip already annotated
    if skip_done:
        pending = []
        for jf in files:
            try:
                with open(jf) as f:
                    rec = json.load(f)
                status = rec.get("annotation_status","pending")
                if status == "pending":
                    pending.append(jf)
                else:
                    if verbose:
                        print(f"  [skip] {jf.name} — already {status}")
            except:
                pending.append(jf)
        files = pending

    total = len(files)
    print(f"\n  Files to annotate : {total}")
    print(f"  Mode              : {mode}")
    if domain_filter:
        print(f"  Domain filter     : {domain_filter}")
    print(f"  Skip done         : {skip_done}")
    print(f"  Model             : {OLLAMA_MODEL}\n")

    if total == 0:
        print("  Nothing to annotate. All files already processed.")
        return

    # Estimate time
    if mode == "template":
        est = total * 2
        print(f"  Estimated time    : ~{est} seconds (template is instant)")
    elif mode == "ollama":
        est = total * 3  # 3 LLM calls × ~1 min each
        print(f"  Estimated time    : ~{est} minutes (3 Ollama calls per case)")
    else:
        est = total * 1.5
        print(f"  Estimated time    : ~{est} minutes (1 Ollama call per case)")

    print("─"*58)

    # Process
    success = 0
    failed  = 0
    start_t = time.time()

    for i, jf in enumerate(files, 1):
        print(f"\n  [{i}/{total}] {jf.name}")
        try:
            with open(jf, encoding="utf-8") as f:
                record = json.load(f)

            # Load full PDF text for LLM
            full_text = load_full_text(record) if mode != "template" else ""

            # Annotate
            if mode == "template":
                updated = template_annotate(record)
            elif mode == "ollama":
                updated = llm_annotate(record, full_text, verbose)
            else:  # hybrid
                updated = hybrid_annotate(record, full_text, verbose)

            # Save
            with open(jf, "w", encoding="utf-8") as f:
                json.dump(updated, f, ensure_ascii=False, indent=2)

            lp_count = len([
                lp for lp in updated.get("legal_principles",[])
                if len(lp.get("principle","")) > 15
            ])
            kw_count = len(updated.get("keywords",[]))
            print(f"    ✓ Saved — {lp_count} principles, {kw_count} keywords, status: {updated['annotation_status']}")
            success += 1

        except KeyboardInterrupt:
            print("\n\n  Interrupted. Progress saved.")
            break
        except Exception as e:
            print(f"    ✗ Error: {e}")
            failed += 1

    # Summary
    elapsed = round((time.time() - start_t) / 60, 1)
    print("\n" + "═"*58)
    print(f"  COMPLETE")
    print(f"  Processed : {success}/{total}")
    print(f"  Failed    : {failed}")
    print(f"  Time      : {elapsed} min")
    print(f"\n  Next step: Store updated JSONs in database")
    print(f"  Run: python3 run_pipeline.py --step 2")
    print("═"*58)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="LegalOne Auto-Annotator")
    p.add_argument("--mode",    default="hybrid",
                   choices=["ollama","template","hybrid"],
                   help="ollama=full LLM | template=rules only | hybrid=both")
    p.add_argument("--input",   default="./dataset/pending_annotation")
    p.add_argument("--domain",  default=None,  help="Filter by domain e.g. divorce")
    p.add_argument("--file",    default=None,  help="Single file to annotate")
    p.add_argument("--model",   default="llama3", help="Ollama model name")
    p.add_argument("--no-skip", action="store_true", help="Re-annotate already done files")
    p.add_argument("--quiet",   action="store_true")
    args = p.parse_args()

    OLLAMA_MODEL = args.model

    run_auto_annotate(
        folder        = args.input,
        mode          = args.mode,
        domain_filter = args.domain,
        single_file   = args.file,
        skip_done     = not args.no_skip,
        verbose       = not args.quiet,
    )
