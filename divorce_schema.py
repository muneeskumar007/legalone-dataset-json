"""
divorce_schema.py
──────────────────────────────────────────────────────────────────
DIVORCE-SPECIFIC dataset schema + validator + template generator.
Covers:
  - Hindu Marriage Act 1955 (all grounds)
  - Muslim Personal Law
  - Special Marriage Act 1954
  - Christian Divorce (Indian Divorce Act 1869)
"""

import json
from pathlib import Path
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
# DIVORCE GROUNDS REFERENCE
# ═══════════════════════════════════════════════════════════════

HMA_GROUNDS = {
    "S13_1_i":    {"ground":"Adultery",              "section":"HMA S.13(1)(i)"},
    "S13_1_ia":   {"ground":"Cruelty",               "section":"HMA S.13(1)(ia)"},
    "S13_1_ib":   {"ground":"Desertion",             "section":"HMA S.13(1)(ib)"},
    "S13_1_ii":   {"ground":"Conversion",            "section":"HMA S.13(1)(ii)"},
    "S13_1_iii":  {"ground":"Unsound mind",          "section":"HMA S.13(1)(iii)"},
    "S13_1_iv":   {"ground":"Leprosy",               "section":"HMA S.13(1)(iv)"},
    "S13_1_v":    {"ground":"Venereal disease",      "section":"HMA S.13(1)(v)"},
    "S13_1_vi":   {"ground":"Renunciation",          "section":"HMA S.13(1)(vi)"},
    "S13_1_vii":  {"ground":"Presumption of death",  "section":"HMA S.13(1)(vii)"},
    "S13_1A_i":   {"ground":"Judicial sep 1yr+",     "section":"HMA S.13(1A)(i)"},
    "S13_1A_ii":  {"ground":"RCR not complied",      "section":"HMA S.13(1A)(ii)"},
    "S13B":       {"ground":"Mutual Consent Divorce","section":"HMA S.13B"},
    "S13A":       {"ground":"Judicial Separation",   "section":"HMA S.10"},
    "S9":         {"ground":"Restitution of Conjugal Rights","section":"HMA S.9"},
    "S12":        {"ground":"Nullity of Marriage",   "section":"HMA S.12"},
    "S11":        {"ground":"Void Marriage",         "section":"HMA S.11"},
}

CRUELTY_TYPES = [
    "physical_violence",
    "mental_cruelty",
    "verbal_abuse",
    "emotional_abuse",
    "dowry_harassment",
    "false_criminal_complaint",
    "refusal_of_consortium",
    "extra_marital_affair_allegation",
    "non_consummation",
    "sustained_abusive_behavior",
    "wilful_neglect",
    "conduct_causing_apprehension_of_injury",
]

EVIDENCE_TYPES = [
    "medical_reports",
    "police_complaint",
    "witness_testimony",
    "photographs",
    "messages_whatsapp_sms",
    "emails",
    "audio_video_recording",
    "bank_statements",
    "fir_chargesheet",
    "hospital_records",
    "call_detail_records",
    "neighbours_testimony",
    "relatives_testimony",
]


# ═══════════════════════════════════════════════════════════════
# DIVORCE CASE SCHEMA
# ═══════════════════════════════════════════════════════════════

def create_divorce_template(
    case_id: str = None,
    case_name: str = "",
    court: str = "",
    delivered_on: str = "",
) -> dict:
    """
    Returns a fully structured empty template for a divorce case.
    Fill each TODO field after reading the judgment.
    """
    return {

        # ── IDENTITY ────────────────────────────────────────────
        "id":               case_id or f"DIV_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "neutral_citation": None,
        "source":           "Indian Kanoon",
        "source_url":       "",
        "domain":           "divorce",
        "sub_domain":       "",   # e.g. divorce_cruelty / divorce_desertion / divorce_mcd / maintenance

        # ── COURT ───────────────────────────────────────────────
        "court":            court,
        "bench":            "",   # Single Judge / Division Bench
        "judges":           [],
        "case_numbers":     [],
        "trial_court":      "",
        "reserved_on":      "",
        "delivered_on":     delivered_on,

        # ── PARTIES ─────────────────────────────────────────────
        "case_name":        case_name,
        "parties": {
            "petitioner":   {"name":"","role":"husband/wife","counsel":""},
            "respondent":   {"name":"","role":"husband/wife","counsel":""},
        },

        # ── MARRIAGE DETAILS ────────────────────────────────────
        "marriage_details": {
            "date_of_marriage":         "",   # DD.MM.YYYY
            "place_of_marriage":        "",
            "type":                     "",   # Hindu / Muslim / Christian / SMA
            "registered":               None, # true/false/null
            "registration_number":      "",
            "solemnised_by":            "",   # temple / registrar / custom
            "witnesses_at_marriage":    [],
        },

        # ── MATRIMONIAL HISTORY ──────────────────────────────────
        "matrimonial_history": {
            "cohabitation_from":        "",   # DD.MM.YYYY or approx year
            "cohabitation_to":          "",
            "last_cohabitation_place":  "",
            "separation_date":          "",
            "separation_reason":        "",
            "children": [
                # {"name":"", "dob":"", "sex":"", "custody_with":""}
            ],
            "previous_proceedings":     [],   # prior court cases between parties
            "maintenance_pendente_lite":"",   # if any interim order
        },

        # ── GROUNDS & INCIDENTS ──────────────────────────────────
        "grounds_claimed": [],          # keys from HMA_GROUNDS above
        "grounds_established": [],      # which grounds court accepted
        "grounds_rejected": [],         # which grounds court rejected

        "cruelty_incidents": [
            # {
            #   "date":        "DD.MM.YYYY or approx",
            #   "description": "what happened",
            #   "type":        "physical_violence / mental_cruelty / ...",
            #   "witness":     "who witnessed",
            #   "evidence":    "medical report / message / etc.",
            #   "proved":      true/false
            # }
        ],

        "desertion_details": {
            # Only fill if desertion is a ground
            "desertion_start_date":     "",
            "animus_deserendi_proved":  None,
            "factum_deserendi_proved":  None,
            "period_of_desertion":      "",   # must be 2+ continuous years
            "attempts_at_reunion":      "",
        },

        # ── EVIDENCE ────────────────────────────────────────────
        "evidence_relied_on": [
            # {"type":"", "exhibit":"", "description":"", "weight":"high/medium/low"}
        ],
        "evidence_rejected": [],

        # ── ACTS & SECTIONS ─────────────────────────────────────
        "acts_cited": [
            {
                "act":      "Hindu Marriage Act, 1955",
                "sections": []   # fill with relevant sections
            }
        ],

        # ── CASE LAW CITED ───────────────────────────────────────
        "case_citations": [],

        # ── FACTS OF CASE ────────────────────────────────────────
        "facts_of_case": "",   # 3-5 sentence summary

        # ── ISSUES ───────────────────────────────────────────────
        "issues_decided": [],

        # ── LEGAL PRINCIPLES ────────────────────────────────────
        "legal_principles": [],

        # ── RELIEFS ─────────────────────────────────────────────
        "reliefs_claimed": {
            "divorce":              False,
            "judicial_separation":  False,
            "rcr":                  False,
            "maintenance":          False,
            "maintenance_amount":   "",
            "permanent_alimony":    False,
            "alimony_amount":       "",
            "custody":              False,
            "custody_of":           "",
            "injunction":           False,
            "return_of_stridhan":   False,
            "other":                "",
        },

        "reliefs_granted": {
            "divorce_granted":      None,  # true/false/null
            "ground_established":   "",
            "maintenance_awarded":  "",
            "alimony_awarded":      "",
            "custody_awarded":      "",
            "costs":                "",
        },

        # ── OUTCOME ──────────────────────────────────────────────
        "outcome": {
            "result":        "",   # Petition allowed/dismissed / Appeal allowed/dismissed
            "final_order":   "",
            "relief_granted":"",
            "costs":         "",
        },

        # ── RAG KEYWORDS ─────────────────────────────────────────
        "keywords": [],

        # ── METADATA ─────────────────────────────────────────────
        "relevance_score":      0,   # 1-5
        "precedent_value":      "",
        "use_for_drafting":     [],
        "annotation_verified":  False,
        "annotation_status":    "pending",
        "annotated_by":         None,
        "dataset_version":      "1.0",
    }


# ═══════════════════════════════════════════════════════════════
# DIVORCE VALIDATOR
# ═══════════════════════════════════════════════════════════════

def validate_divorce_record(record: dict) -> dict:
    """
    Validates a divorce dataset record.
    Returns {"valid": bool, "score": 0-100, "errors": [], "warnings": []}
    """
    errors   = []
    warnings = []
    score    = 0

    # ── Critical fields (2 pts each) ────────────────────────────
    critical = {
        "id":            record.get("id"),
        "case_name":     record.get("case_name"),
        "court":         record.get("court"),
        "delivered_on":  record.get("delivered_on"),
        "facts_of_case": record.get("facts_of_case"),
        "outcome.result": record.get("outcome",{}).get("result"),
    }
    for field, val in critical.items():
        if val and val not in ("TODO","TODO — 3-5 sentence summary",""):
            score += 10
        else:
            errors.append(f"Missing critical field: {field}")

    # ── Legal principles (20 pts) ────────────────────────────────
    lps = [lp for lp in record.get("legal_principles",[])
           if lp.get("principle","").lower()[:4] != "todo"
           and len(lp.get("principle","")) > 20]
    if len(lps) >= 3:
        score += 20
    elif len(lps) >= 1:
        score += 10
        warnings.append("Add more legal principles (aim for 3+)")
    else:
        errors.append("No legal principles extracted")

    # ── Marriage details (5 pts) ─────────────────────────────────
    md = record.get("marriage_details",{})
    if md.get("date_of_marriage") and md.get("type"):
        score += 5
    else:
        warnings.append("Fill marriage_details.date_of_marriage and type")

    # ── Grounds (10 pts) ────────────────────────────────────────
    if record.get("grounds_claimed"):
        score += 5
    else:
        warnings.append("Fill grounds_claimed (use HMA_GROUNDS keys)")
    if record.get("grounds_established") or record.get("grounds_rejected"):
        score += 5
    else:
        warnings.append("Fill grounds_established and/or grounds_rejected")

    # ── Keywords (5 pts) ────────────────────────────────────────
    kws = [k for k in record.get("keywords",[]) if k.lower() != "todo"]
    if len(kws) >= 10:
        score += 5
    else:
        warnings.append(f"Add more keywords (have {len(kws)}, need 10+)")

    # ── Outcome (5 pts) ─────────────────────────────────────────
    rg = record.get("reliefs_granted",{})
    if rg.get("divorce_granted") is not None:
        score += 5
    else:
        warnings.append("Fill reliefs_granted.divorce_granted (true/false)")

    # ── Relevance score set ──────────────────────────────────────
    if record.get("relevance_score",0) > 0:
        score += 5

    valid = len(errors) == 0 and score >= 60

    return {
        "valid":    valid,
        "score":    min(score, 100),
        "grade":    "A" if score>=80 else "B" if score>=60 else "C" if score>=40 else "D",
        "errors":   errors,
        "warnings": warnings,
        "lp_count": len(lps),
        "kw_count": len(kws),
    }


# ═══════════════════════════════════════════════════════════════
# DIVORCE DATASET MANAGER
# ═══════════════════════════════════════════════════════════════

class DivorceDataset:
    """
    In-memory + file-backed store for multiple divorce case JSONs.
    Handles: add, load, save, search, export, validate_all.
    """

    def __init__(self, dataset_file: str = "divorce_dataset.json"):
        self.dataset_file = Path(dataset_file)
        self.records: dict = {}   # id → record
        self._load()

    def _load(self):
        if self.dataset_file.exists():
            with open(self.dataset_file, encoding="utf-8") as f:
                data = json.load(f)
            # Support both array and dict-of-dict formats
            if isinstance(data, list):
                self.records = {r["id"]: r for r in data if r.get("id")}
            elif isinstance(data, dict) and "judgments" in data:
                self.records = {r["id"]: r for r in data["judgments"] if r.get("id")}
            elif isinstance(data, dict):
                self.records = data
            print(f"  Loaded {len(self.records)} records from {self.dataset_file}")
        else:
            print(f"  New dataset — {self.dataset_file}")

    def save(self):
        output = {
            "domain":       "divorce",
            "total":        len(self.records),
            "updated_at":   datetime.now().isoformat(),
            "version":      "1.0",
            "judgments":    list(self.records.values())
        }
        with open(self.dataset_file, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"  ✓ Saved {len(self.records)} records → {self.dataset_file}")

    def add(self, record: dict) -> str:
        rid = record.get("id")
        if not rid:
            raise ValueError("Record must have an 'id' field")
        self.records[rid] = record
        self.save()
        return rid

    def add_from_file(self, json_path: str) -> str:
        with open(json_path, encoding="utf-8") as f:
            record = json.load(f)
        return self.add(record)

    def add_folder(self, folder: str) -> int:
        folder_path = Path(folder)
        count = 0
        for jf in sorted(folder_path.glob("*.json")):
            if jf.name in ("batch_index.json", "divorce_dataset.json"):
                continue
            try:
                with open(jf, encoding="utf-8") as f:
                    record = json.load(f)
                # Only add divorce/matrimonial cases
                dom = record.get("domain","")
                if any(d in dom for d in ["divorce","matrimonial","family","maintenance","custody"]):
                    self.add(record)
                    count += 1
                    print(f"  + {record.get('case_name','?')[:55]}")
            except Exception as e:
                print(f"  [err] {jf.name}: {e}")
        self.save()
        print(f"\n  Added {count} divorce/family records")
        return count

    def get(self, record_id: str) -> dict:
        return self.records.get(record_id, {})

    def search(
        self,
        keyword:   str  = None,
        ground:    str  = None,
        sub_domain:str  = None,
        court:     str  = None,
        year_from: int  = None,
        year_to:   int  = None,
        verified_only: bool = False,
    ) -> list:
        results = []
        for rid, rec in self.records.items():
            # Verified filter
            if verified_only and not rec.get("annotation_verified"):
                continue
            # Sub-domain
            if sub_domain and sub_domain.lower() not in rec.get("sub_domain","").lower():
                continue
            # Court
            if court and court.lower() not in rec.get("court","").lower():
                continue
            # Year range
            yr_str = rec.get("delivered_on","")[-4:]
            if yr_str.isdigit():
                yr = int(yr_str)
                if year_from and yr < year_from: continue
                if year_to   and yr > year_to:   continue
            # Grounds
            if ground:
                grounds = rec.get("grounds_claimed",[]) + rec.get("grounds_established",[])
                if ground.lower() not in " ".join(grounds).lower():
                    continue
            # Keyword search
            if keyword:
                kw = keyword.lower()
                searchable = " ".join([
                    rec.get("case_name",""),
                    rec.get("facts_of_case",""),
                    " ".join(rec.get("keywords",[])),
                    " ".join(lp.get("principle","")
                             for lp in rec.get("legal_principles",[])),
                ])
                if kw not in searchable.lower():
                    continue
            results.append(rec)
        return results

    def get_all_principles(self, verified_only: bool = False) -> list:
        principles = []
        for rid, rec in self.records.items():
            if verified_only and not rec.get("annotation_verified"):
                continue
            for lp in rec.get("legal_principles", []):
                if (lp.get("principle","").lower()[:4] == "todo"
                        or len(lp.get("principle","")) < 10):
                    continue
                secs = lp.get("applicable_acts_sections",[])
                kws  = lp.get("keywords",[])
                principles.append({
                    "judgment_id":    rid,
                    "case_name":      rec.get("case_name",""),
                    "court":          rec.get("court",""),
                    "delivered_on":   rec.get("delivered_on",""),
                    "neutral_citation":rec.get("neutral_citation",""),
                    "domain":         "divorce",
                    "principle_id":   lp.get("principle_id",""),
                    "principle":      lp.get("principle",""),
                    "held":           lp.get("held",""),
                    "sections":       secs,
                    "keywords":       kws,
                    "favours":        lp.get("favours","neutral"),
                    "cited_cases":    lp.get("cited_cases",[]),
                    "significance":   lp.get("significance",""),
                    "use_in":         lp.get("use_in",[]),
                    "embed_text": " ".join(filter(None,[
                        lp.get("principle",""),
                        lp.get("held",""),
                        " ".join(kws) if isinstance(kws,list) else "",
                        " ".join(secs) if isinstance(secs,list) else "",
                    ]))
                })
        return principles

    def validate_all(self) -> dict:
        results = {"A":[],"B":[],"C":[],"D":[],"errors":[]}
        for rid, rec in self.records.items():
            v = validate_divorce_record(rec)
            results[v["grade"]].append({
                "id":      rid,
                "name":    rec.get("case_name","?")[:50],
                "score":   v["score"],
                "issues":  v["errors"] + v["warnings"]
            })
        return results

    def stats(self) -> dict:
        total = len(self.records)
        verified = sum(1 for r in self.records.values() if r.get("annotation_verified"))
        grounds_count = {}
        for rec in self.records.values():
            for g in rec.get("grounds_established",[]):
                grounds_count[g] = grounds_count.get(g,0)+1
        principles_count = sum(
            len([lp for lp in rec.get("legal_principles",[])
                 if len(lp.get("principle","")) > 10])
            for rec in self.records.values()
        )
        return {
            "total":            total,
            "verified":         verified,
            "pending":          total - verified,
            "total_principles": principles_count,
            "grounds_breakdown":grounds_count,
        }

    def export_for_rag(self, output_path: str, verified_only: bool = False):
        principles = self.get_all_principles(verified_only)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "domain":      "divorce",
                "total":       len(principles),
                "exported_at": datetime.now().isoformat(),
                "principles":  principles
            }, f, ensure_ascii=False, indent=2)
        print(f"  ✓ {len(principles)} divorce principles → {output_path}")
        return principles


# ═══════════════════════════════════════════════════════════════
# DEMO — show it works with existing extracted records
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    print("\n" + "═"*55)
    print("  DivorceDataset — Demo & Test")
    print("═"*55)

    ds = DivorceDataset("./divorce_dataset.json")

    # Load existing extracted records (if they exist)
    existing = [
        "/mnt/user-data/outputs/santhosh_kumar_dataset.json",
    ]
    for path in existing:
        if Path(path).exists():
            try:
                with open(path) as f:
                    rec = json.load(f)
                # Tag as divorce/family since it has matrimonial elements
                rec["domain"] = "divorce"
                rec["sub_domain"] = "will_partition_matrimonial"
                ds.add(rec)
                print(f"  + Added: {rec.get('case_name','?')[:50]}")
            except Exception as e:
                print(f"  [skip] {path}: {e}")

    # Show stats
    s = ds.stats()
    print(f"\n  Total cases   : {s['total']}")
    print(f"  Verified      : {s['verified']}")
    print(f"  Principles    : {s['total_principles']}")

    # Show validation
    print("\n  Validation:")
    vr = ds.validate_all()
    for grade in ["A","B","C","D"]:
        for item in vr[grade]:
            print(f"    Grade {grade} [{item['score']}] {item['name']}")

    # Export template
    tmpl_path = Path("/mnt/user-data/outputs/divorce_case_template.json")
    tmpl = create_divorce_template("DIV_EXAMPLE_001", "Petitioner v. Respondent")
    with open(tmpl_path, "w") as f:
        json.dump(tmpl, f, ensure_ascii=False, indent=2)
    print(f"\n  ✓ Blank template → {tmpl_path}")

    # Export RAG
    rag_path = "/mnt/user-data/outputs/divorce_principles_rag.json"
    ds.export_for_rag(rag_path)

    print("\n  Available grounds (HMA):")
    for key, val in list(HMA_GROUNDS.items())[:6]:
        print(f"    {key:<15} → {val['ground']} ({val['section']})")

    print("\n═"*55)
