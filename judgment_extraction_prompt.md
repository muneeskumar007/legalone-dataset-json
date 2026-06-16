# LEGALONE — JUDGMENT EXTRACTION MASTER PROMPT

Use this prompt with any LLM (Claude, GPT-4, Llama 3) to extract a judgment into the LegalOne dataset JSON format.

---

## PROMPT (copy this exactly, paste judgment text after it)

```
You are a senior Indian legal researcher building a structured dataset for a Legal AI system called LegalOne.

Your task is to read the Indian court judgment provided below and extract it into a STRICT JSON format.

CRITICAL RULES:
1. Extract ONLY what is actually in the judgment — do NOT hallucinate or assume anything
2. If a field is not found, write null or empty [] — never invent content
3. For legal_principles — extract the ACTUAL legal rule the court APPLIED or ESTABLISHED, not just what was argued
4. For keywords — think about what an advocate would search for when they need this case
5. For favours field — write "plaintiff" / "defendant" / "neutral" only
6. Dates must be in DD.MM.YYYY format
7. Every legal_principle must have a one-line principle (the rule), the actual held (what court said), applicable sections, and keywords

OUTPUT ONLY the JSON — no explanation, no preamble, no markdown fences.

Use this exact structure:

{
  "id": "HC_[COURT_CODE]_[YEAR]_[SHORT_CASE_NAME]_[CASE_NO]",
  "neutral_citation": "[neutral citation if available, else null]",
  "source": "Indian Kanoon",
  "source_url": "[URL if known, else null]",
  "domain": "[civil / criminal / family / constitutional / labour / consumer / tax]",
  "sub_domain": "[e.g. property_partition / divorce_cruelty / cheque_bounce / murder / maintenance]",

  "court": "[Full court name]",
  "bench": "[Single Judge / Division Bench / Full Bench / Supreme Court Bench]",
  "judges": ["Judge 1 name", "Judge 2 name"],
  "case_numbers": ["Case number 1", "Case number 2"],
  "trial_court": "[Trial court name and case number if mentioned, else null]",
  "reserved_on": "[DD.MM.YYYY or null]",
  "delivered_on": "[DD.MM.YYYY]",

  "case_name": "[Petitioner/Plaintiff v. Respondent/Defendant — full case name]",
  "parties": {
    "petitioner_plaintiff": "[Name and brief role]",
    "respondent_defendant": "[Name and brief role]",
    "other_parties": []
  },

  "acts_cited": [
    {
      "act": "[Full Act name with year]",
      "sections": ["Section X — title/purpose", "Section Y — title/purpose"]
    }
  ],

  "facts_of_case": "[3-5 sentence factual summary covering: who, what happened, what relief claimed, what trial court decided, why appealed]",

  "issues_decided": [
    {
      "issue_no": 1,
      "question": "[Exact legal question the court framed]",
      "answer": "[One sentence answer — what court decided on this issue and brief reasoning]"
    }
  ],

  "legal_principles": [
    {
      "principle_id": "LP_001",
      "principle": "[One-line statement of the legal rule — must be reusable across other cases]",
      "held": "[What the court ACTUALLY said — 2-4 sentences from the judgment reasoning]",
      "applicable_acts_sections": ["Act — Section X", "Act — Section Y"],
      "cited_cases": ["Case name, citation"],
      "keywords": ["keyword1", "keyword2", "keyword3"],
      "favours": "plaintiff / defendant / neutral",
      "use_in": ["case type 1", "case type 2"],
      "significance": "HIGH / MEDIUM / LOW — one sentence why"
    }
  ],

  "outcome": {
    "result": "[Appeal allowed/dismissed / Suit decreed/dismissed]",
    "final_order": "[2-3 sentence summary of the final order]",
    "relief_granted": "[What specific relief was granted]",
    "costs": "[Cost order if any]"
  },

  "keywords": [
    "keyword1", "keyword2", "keyword3"
  ],

  "relevance_score": [1-5 integer — 5 = Supreme Court / landmark, 4 = HC Division Bench, 3 = HC Single, 2 = District Court, 1 = low value],
  "precedent_value": "[High / Medium / Low — one sentence why]",
  "use_for_drafting": [
    "Use case 1 — e.g. Partition suit petition involving ancestral property",
    "Use case 2 — e.g. Will challenge / probate"
  ],

  "annotation_verified": false,
  "dataset_version": "1.0"
}

JUDGMENT TEXT:
[PASTE JUDGMENT HERE]
```

---
---

## DOMAIN-SPECIFIC EXTRACTION GUIDES

Different case types need different extraction focus. Use these guides for each domain.

---

### GUIDE 1 — FAMILY / MATRIMONIAL (Hindu Marriage Act, Muslim Personal Law)

**Extra fields to extract:**

```json
"matrimonial_data": {
  "marriage_date": "DD.MM.YYYY or null",
  "marriage_place": "temple / registrar / null",
  "marriage_type": "Hindu / Muslim / Christian / Special Marriage Act",
  "grounds_claimed": ["cruelty", "desertion", "adultery", "irretrievable breakdown"],
  "ground_established": true / false,
  "incidents_mentioned": [
    {"date": "approximate", "nature": "description of incident", "evidence": "witness/document"}
  ],
  "children": [{"name": "if mentioned", "age_at_filing": "if mentioned"}],
  "maintenance_ordered": "amount or null",
  "custody_ordered": "mother/father/joint or null",
  "cohabitation_period": "from date to date",
  "last_cohabitation_place": "city/district"
}
```

**Acts to watch for:**
- Hindu Marriage Act 1955: S.9 (RCR), S.10 (Judicial Separation), S.13 (Divorce grounds), S.13B (MCD), S.16 (Legitimacy), S.24 (Maintenance pendente lite), S.25 (Alimony), S.26 (Custody)
- Hindu Succession Act 1956: S.6, S.8, S.15, S.16
- Hindu Minority and Guardianship Act 1956: S.6, S.13
- Protection of Women from DV Act 2005: S.3, S.12, S.17, S.18, S.19, S.20, S.22, S.23
- Muslim Women (Protection of Rights on Marriage) Act 2019
- Indian Divorce Act 1869 (for Christians)

**Key principles to extract for HMA cases:**
- What acts constitute cruelty (physical / mental)
- Standard of proof for cruelty
- Desertion — animus deserendi + factum of desertion both needed
- Irretrievable breakdown — whether applicable
- Condonation — effect of resumption of cohabitation
- Limitation period for divorce petition

---

### GUIDE 2 — PROPERTY / PARTITION (Hindu Succession, TPA)

**Extra fields to extract:**

```json
"property_data": {
  "property_type": "ancestral / self-acquired / joint family / separate",
  "property_description": "brief description of each item",
  "partition_mode": "preliminary decree / final decree / by metes and bounds",
  "shares_declared": [
    {"party": "name", "share": "fraction", "basis": "how computed"}
  ],
  "documents_in_dispute": [
    {"type": "will/sale deed/partition deed", "date": "DD.MM.YYYY", "validity": "valid/void/partial"}
  ]
}
```

**Acts to watch for:**
- Hindu Succession Act 1956: S.6 (coparcenary after 2005 amendment), S.8, S.14, S.15, S.16, S.30
- Hindu Minority and Guardianship Act
- Transfer of Property Act 1882: S.8, S.54, S.58, S.122
- Registration Act 1908: S.17, S.49
- Specific Relief Act 1963: S.34, S.38
- Benami Transactions (Prohibition) Act

---

### GUIDE 3 — CHEQUE BOUNCE (NI Act Section 138)

**Extra fields to extract:**

```json
"cheque_bounce_data": {
  "cheque_amount": "Rs. amount",
  "cheque_date": "DD.MM.YYYY",
  "bank": "name of bank and branch",
  "dishonour_date": "DD.MM.YYYY",
  "dishonour_reason": "insufficient funds / account closed / stop payment",
  "demand_notice_date": "DD.MM.YYYY",
  "notice_served_by": "RPAD / courier / in person",
  "reply_given": true / false,
  "complaint_filed_within_30_days": true / false,
  "legally_enforceable_debt": true / false,
  "presumption_rebutted": true / false,
  "sentence": "imprisonment period and/or fine amount"
}
```

**Acts to watch for:**
- Negotiable Instruments Act 1881: S.118 (presumptions), S.138 (offence), S.139 (presumption in favour), S.140 (defence), S.141 (company liability), S.142 (procedure), S.143A (interim compensation), S.148 (deposit on appeal)
- CrPC / BNSS: S.200, S.204, S.357

**Key principles:**
- Presumption under S.139 is rebuttable — standard is preponderance of probability
- Time limits — 30 days from dishonour for notice, 15 days from notice for payment, 30 days from cause of action for complaint
- Legally enforceable debt — must exist at time of cheque issuance

---

### GUIDE 4 — CRIMINAL (IPC/BNS, CrPC/BNSS)

**Extra fields to extract:**

```json
"criminal_data": {
  "offences_charged": ["IPC S.X", "IPC S.Y"],
  "offences_convicted": ["IPC S.X"],
  "offences_acquitted": ["IPC S.Y"],
  "sentence_awarded": {
    "imprisonment": "X years / rigorous / simple",
    "fine": "Rs. amount",
    "type": "death / life / rigorous / simple"
  },
  "death_sentence_reference": true / false,
  "type_of_evidence": ["eyewitness", "CCTV", "CDR", "confession", "forensic", "medical"],
  "conviction_basis": "direct evidence / circumstantial / both",
  "last_seen_theory": true / false,
  "dying_declaration": true / false,
  "approver_evidence": true / false
}
```

---

### GUIDE 5 — LAND ACQUISITION / COMPENSATION

**Extra fields to extract:**

```json
"land_acquisition_data": {
  "act_under": "Land Acquisition Act 1894 / RFCTLARR Act 2013",
  "notification_date": "DD.MM.YYYY",
  "purpose": "road / project / industrial",
  "compensation_awarded_by_LAO": "Rs. amount",
  "reference_court_enhanced_to": "Rs. amount",
  "high_court_enhanced_to": "Rs. amount",
  "market_value_basis": "comparable sales / capitalisation / both",
  "solatium_percentage": "30% standard",
  "interest_rate": "12% / 9%",
  "deduction_applied": "percentage if any"
}
```

---

## QUALITY CHECKLIST — Before saving any record

Run through this list for every judgment you extract:

```
IDENTITY
[ ] id follows naming convention HC_[COURT]_[YEAR]_[NAME]_[NO]
[ ] neutral_citation filled if available
[ ] source_url filled if from Indian Kanoon

ACCURACY
[ ] case_name matches exactly what is in the judgment
[ ] delivered_on date is correct
[ ] all judges listed correctly
[ ] acts_cited sections are the ones ACTUALLY cited in the judgment (not assumed)

LEGAL PRINCIPLES
[ ] Each principle is a REUSABLE RULE — could apply to other cases
[ ] held field quotes or closely paraphrases actual court language
[ ] applicable_sections are specific (Act + Section number)
[ ] favours field is honest — not biased
[ ] keywords cover what an advocate would search

OUTCOME
[ ] result field matches what the court actually ordered
[ ] shares/reliefs match exactly what the order says

KEYWORDS
[ ] At least 15 keywords
[ ] Mix of: legal terms + factual terms + section numbers + Latin maxims if any
[ ] Covers both the winning and losing side's arguments

METADATA
[ ] relevance_score is honest (5 = SC/landmark only)
[ ] use_for_drafting is specific and practical
[ ] annotation_verified = true only after a lawyer has reviewed
```

---

## BATCH EXTRACTION WORKFLOW

When processing a large batch of judgments (50-100), follow this order:

### Step 1 — Triage (5 minutes per judgment)
Read only: case name, court, year, sections cited, final order.
Assign domain and relevance_score. Skip scores 1-2 for now.

### Step 2 — Fast extraction (15 minutes per judgment)
Use the prompt above with the judgment text.
Fill all auto-fillable fields. Mark manual fields as "TODO".

### Step 3 — Manual annotation (20 minutes per judgment)
A law student or junior advocate fills:
- facts_of_case (summarise in own words)
- legal_principles (most important step)
- issues_decided answers
- keywords refinement

### Step 4 — Quality check (5 minutes per judgment)
Run through checklist above.
Mark annotation_verified: true.

### Step 5 — Embed into FAISS
Run the embedding pipeline on legal_principles + keywords + facts_of_case.
Store vector with full record ID as metadata.

**Time estimate:** 1 judgment = ~45 minutes total.
At 2 per day = 60 judgments per month = solid RAG corpus in 2 months.

---

## FOLDER STRUCTURE FOR YOUR DATASET

```
legalone_dataset/
├── raw_pdfs/
│   ├── civil/
│   │   ├── partition/
│   │   ├── will/
│   │   └── property/
│   ├── criminal/
│   ├── family/
│   │   ├── divorce/
│   │   ├── maintenance/
│   │   └── custody/
│   ├── cheque_bounce/
│   └── land_acquisition/
│
├── extracted_json/
│   ├── civil/
│   ├── criminal/
│   ├── family/
│   ├── cheque_bounce/
│   └── land_acquisition/
│
├── principles_only/          ← for RAG embedding
│   └── all_principles.json   ← merged file for FAISS
│
├── verified/                 ← annotation_verified: true
└── pending_review/           ← annotation_verified: false
```

---

## MERGE SCRIPT — Combine all principles into one FAISS-ready file

```python
import json
from pathlib import Path

def merge_principles(dataset_dir: str, output_path: str):
    """
    Merge all legal_principles from all JSON files into
    one flat list ready for embedding into FAISS.
    Each entry gets the case citation appended.
    """
    all_principles = []
    
    for json_file in Path(dataset_dir).rglob("*.json"):
        with open(json_file, encoding="utf-8") as f:
            record = json.load(f)
        
        case_ref = {
            "case_id":         record.get("id"),
            "case_name":       record.get("case_name"),
            "court":           record.get("court"),
            "delivered_on":    record.get("delivered_on"),
            "neutral_citation":record.get("neutral_citation"),
            "domain":          record.get("domain"),
        }
        
        for principle in record.get("legal_principles", []):
            entry = {
                **case_ref,
                "principle_id":  principle.get("principle_id"),
                "principle":     principle.get("principle"),
                "held":          principle.get("held"),
                "sections":      principle.get("applicable_acts_sections", []),
                "keywords":      principle.get("keywords", []),
                "favours":       principle.get("favours"),
                "significance":  principle.get("significance"),
                # Text for embedding — combine all searchable text
                "embed_text": (
                    f"{principle.get('principle', '')} "
                    f"{principle.get('held', '')} "
                    f"{' '.join(principle.get('keywords', []))} "
                    f"{' '.join(principle.get('applicable_acts_sections', []))}"
                )
            }
            all_principles.append(entry)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_principles, f, ensure_ascii=False, indent=2)
    
    print(f"Merged {len(all_principles)} principles from "
          f"{sum(1 for _ in Path(dataset_dir).rglob('*.json'))} files")
    return all_principles


# Usage:
# principles = merge_principles("legalone_dataset/extracted_json", 
#                               "legalone_dataset/principles_only/all_principles.json")
```

---

## EMBED INTO FAISS — Complete pipeline

```python
import json
import numpy as np
import faiss
import pickle
from sentence_transformers import SentenceTransformer

def build_legal_rag_index(principles_json_path: str, index_output_path: str):
    """
    Take merged principles JSON → create SentenceTransformer embeddings → 
    store in FAISS index → save index + metadata for retrieval.
    """
    
    # Load principles
    with open(principles_json_path, encoding="utf-8") as f:
        principles = json.load(f)
    
    print(f"Building index from {len(principles)} principles...")
    
    # Extract text to embed
    texts = [p["embed_text"] for p in principles]
    
    # Create embeddings
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=32)
    embeddings = np.array(embeddings, dtype=np.float32)
    
    # Build FAISS index
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)
    
    # Save index
    faiss.write_index(index, f"{index_output_path}.faiss")
    
    # Save metadata (everything except embed_text to save space)
    metadata = [{k: v for k, v in p.items() if k != "embed_text"} 
                for p in principles]
    with open(f"{index_output_path}_metadata.pkl", "wb") as f:
        pickle.dump(metadata, f)
    
    print(f"Index saved: {index_output_path}.faiss")
    print(f"Metadata saved: {index_output_path}_metadata.pkl")
    print(f"Index size: {index.ntotal} vectors, dim={dim}")


def retrieve_legal_principles(
    query: str,
    index_path: str,
    metadata_path: str,
    top_k: int = 5
) -> list:
    """
    Search legal principles by natural language query.
    Returns top_k most relevant principles with full metadata.
    """
    model    = SentenceTransformer("all-MiniLM-L6-v2")
    index    = faiss.read_index(f"{index_path}.faiss")
    with open(f"{index_path}_metadata.pkl", "rb") as f:
        metadata = pickle.load(f)
    
    query_vec = model.encode([query], show_progress_bar=False)
    query_vec = np.array(query_vec, dtype=np.float32)
    
    distances, indices = index.search(query_vec, top_k)
    
    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx < len(metadata):
            result = dict(metadata[idx])
            result["relevance_score"] = float(1 / (1 + dist))
            results.append(result)
    
    return sorted(results, key=lambda x: x["relevance_score"], reverse=True)


# Example usage:
# build_legal_rag_index(
#     "legalone_dataset/principles_only/all_principles.json",
#     "legalone_dataset/faiss_index/legal_rag"
# )
#
# results = retrieve_legal_principles(
#     "client wants divorce due to mental cruelty by husband",
#     "legalone_dataset/faiss_index/legal_rag",
#     "legalone_dataset/faiss_index/legal_rag",
#     top_k=5
# )
# for r in results:
#     print(f"[{r['relevance_score']:.2f}] {r['case_name']} — {r['principle']}")
```

---

## PRIORITY JUDGMENT LIST — Build this first

Collect these specific cases first. They cover 80% of your use cases.

### DIVORCE / MATRIMONIAL (Priority 1)
| Case | Citation | Principle |
|---|---|---|
| Samar Ghosh v. Jaya Ghosh | (2007) 4 SCC 511 | Mental cruelty — 31 examples listed |
| Naveen Kohli v. Neelu Kohli | (2006) 4 SCC 558 | Irretrievable breakdown |
| V. Bhagat v. D. Bhagat | (1994) 1 SCC 337 | Mental cruelty standard |
| Bipinchandra v. Prabhavati | AIR 1957 SC 176 | Desertion — both elements needed |
| Savitri Pandey v. Prem Chandra | (2002) 2 SCC 73 | Desertion — animus deserendi |
| Shilpa Sailesh v. Varun Sreenivasan | (2023) 12 SCC 1 | SC can dissolve under Art.142 |

### CHEQUE BOUNCE (Priority 1)
| Case | Citation | Principle |
|---|---|---|
| Rangappa v. Sri Mohan | (2010) 11 SCC 441 | S.139 presumption and rebuttal |
| Basalingappa v. Mudibasappa | (2019) 5 SCC 418 | Standard to rebut presumption |
| Meters and Instruments v. Kanchan Mehta | (2018) 1 SCC 560 | Acquittal in S.138 cases |
| MSR Leathers v. S. Palaniappan | (2013) 1 SCC 177 | Second complaint after acquittal |

### PROPERTY / PARTITION (Priority 2)
| Case | Citation | Principle |
|---|---|---|
| Uttam v. Saubhag Singh | (2016) 4 SCC 68 | Effect of 2005 HSA amendment on daughters |
| Vineeta Sharma v. Rakesh Sharma | (2020) 9 SCC 1 | Daughters as coparceners — definitive |
| Prakash v. Phulavati | (2016) 2 SCC 36 | Overruled by Vineeta Sharma — note this |
| Commissioner of Wealth Tax v. Chander Sen | (1986) 3 SCC 567 | Self-acquired vs ancestral |

### LAND ACQUISITION (Priority 3)
| Case | Citation | Principle |
|---|---|---|
| Srinivas v. Land Acquisition Officer | (2019) various | Market value determination |
| Kolkata Municipality v. Bimal Kumar | (2012) various | Comparable sales method |

