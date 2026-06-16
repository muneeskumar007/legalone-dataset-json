# LEGALONE DATASET PIPELINE — COMPLETE GUIDE
# For 30 Judgment PDFs → Searchable RAG Database

---

## FOLDER SETUP (do this first)

```
legalone_pipeline/
├── pdfs/                    ← PUT ALL 30 PDFs HERE
├── dataset/                 ← auto-created by Step 1
├── batch_processor.py
├── dataset_store.py
├── annotator.py
├── divorce_schema.py
├── build_faiss_pipeline.py
├── run_pipeline.py
└── HOW_TO_USE.md
```

---

## INSTALL (one time)

```bash
pip install pdfplumber tqdm sentence-transformers faiss-cpu numpy
```

---

## STEP 1 — Extract all 30 PDFs to JSON shells (5 minutes)

```bash
# Put all PDFs in ./pdfs folder, then run:
python3 run_pipeline.py --step 1 --input ./pdfs --output ./dataset

# What it does:
# - Reads every PDF
# - Extracts text, detects domain, court, dates, acts, citations
# - Creates one JSON file per judgment in ./dataset/pending_annotation/
# - Creates batch_index.json showing all cases and their domains
```

Output example:
```
Found 30 PDFs
Processing: 100%|████████████| 30/30
Domain Breakdown:
  divorce          ████████████ 12
  partition        ████████ 8
  cheque_bounce    █████ 5
  maintenance      ███ 3
  will_succession  ██ 2
```

---

## STEP 2 — Store in database (1 minute)

```bash
python3 run_pipeline.py --step 2

# What it does:
# - Reads all JSON files from ./dataset/pending_annotation/
# - Stores in SQLite database (legalone_dataset.db)
# - Indexes keywords, acts, domains for fast search
```

---

## STEP 3 — Annotate cases (30-45 min per case)

```bash
# Annotate only divorce cases first:
python3 run_pipeline.py --step 3 --domain divorce

# Or annotate all:
python3 run_pipeline.py --step 3

# What it does:
# - Opens each JSON one by one
# - Asks you to fill: facts, legal principles, outcome, keywords
# - Saves after each case (you can stop and resume)
# - AUTO-SAVES progress — safe to Ctrl+C
```

### WHAT TO FILL FOR EACH CASE:

For each judgment, you fill ONLY these fields (auto-fields are already done):

1. **Case name** — confirm/correct "Petitioner v. Respondent"
2. **Parties** — who is plaintiff, who is defendant
3. **Facts** — 3-5 sentences: what happened, what relief claimed, what trial court held
4. **Legal principles** — THE MOST IMPORTANT PART:
   - What legal rule did the court apply?
   - What did the court actually say?
   - Which sections / which prior cases cited?
   - Who does it favour?
5. **Outcome** — appeal allowed/dismissed, what relief granted
6. **Keywords** — 15+ search terms

### TIME ESTIMATE:
- Simple judgment (10-20 pages): 20 minutes
- Complex judgment (40+ pages): 45 minutes
- At 2 per day = 15 days for 30 judgments

---

## STEP 4 — Export Divorce Dataset (1 minute)

```bash
python3 run_pipeline.py --step 4

# What it does:
# - Validates all divorce records (grades A/B/C/D)
# - Exports divorce_all_cases.json (all divorce records in one file)
# - Exports divorce_principles_rag.json (flat principles for FAISS)
# - Shows quality report
```

---

## STEP 5 — Build FAISS Search Index (5-10 minutes)

```bash
python3 run_pipeline.py --step 5

# What it does:
# - Embeds all legal principles using SentenceTransformers (free, local)
# - Builds FAISS vector index
# - Tests retrieval with sample queries
```

---

## CHECK STATUS ANYTIME

```bash
python3 run_pipeline.py --step status
```

Output:
```
LEGALONE DATASET PIPELINE — STATUS
  📁 Input PDFs           : 30 in ./pdfs
  📄 Shell JSONs created  : 30 in ./dataset/pending_annotation
  🗄  Database             : legalone_dataset.db
     Total judgments      : 30
     Verified             : 12
     Pending annotation   : 18
     Legal principles     : 67
     Domain breakdown:
       divorce              ████████████ 12
       partition            ████████ 8
  🔍 FAISS index          : ✓ 142 KB
  💍 Divorce dataset      : 12 cases
```

---

## SEARCH THE INDEX

```bash
# After Step 5:
python3 run_pipeline.py --step search --query "divorce mental cruelty husband"

# Output:
# Query: "divorce mental cruelty husband"
# #1 [0.821] Samar Ghosh v. Jaya Ghosh
#    Mental cruelty includes sustained abusive behavior without physical violence
#    Court: Supreme Court of India | 01.03.2007
#
# #2 [0.791] V. Bhagat v. D. Bhagat
#    False criminal complaints constitute mental cruelty
#    Court: Supreme Court of India | 1994
```

---

## INDIVIDUAL COMMANDS (without run_pipeline.py)

```bash
# Process PDFs only
python3 batch_processor.py --input ./pdfs --output ./dataset

# Store in DB only
python3 dataset_store.py --action store --input ./dataset/pending_annotation

# Search by domain
python3 dataset_store.py --action search --domain divorce

# Search by keyword
python3 dataset_store.py --action search --keyword "mental cruelty"

# Search by act
python3 dataset_store.py --action search --act "Hindu Marriage Act"

# Export all divorce cases
python3 dataset_store.py --action export --domain divorce --output divorce_cases.json

# Export principles for FAISS
python3 dataset_store.py --action export-rag --domain divorce --output divorce_rag.json

# Annotate only divorce cases
python3 annotator.py --folder ./dataset/pending_annotation --domain divorce

# Annotate single file
python3 annotator.py --file ./dataset/pending_annotation/MyCase.json
```

---

## FILE STRUCTURE AFTER COMPLETION

```
legalone_pipeline/
├── pdfs/                              ← original PDFs (keep forever)
│   ├── divorce_case_1.pdf
│   └── ...
│
├── dataset/
│   ├── pending_annotation/            ← shell JSONs (auto-generated)
│   │   ├── divorce_case_1.json        ← fill TODO fields here
│   │   └── ...
│   ├── faiss_index/
│   │   ├── legal_rag.faiss            ← vector index
│   │   ├── legal_rag_metadata.pkl     ← metadata for retrieval
│   │   └── all_principles.json        ← flat merged principles
│   ├── divorce_all_cases.json         ← all divorce records
│   └── divorce_principles_rag.json    ← divorce principles for RAG
│
├── legalone_dataset.db                ← SQLite (searchable, all cases)
└── divorce_dataset.json               ← divorce-only dataset
```

---

## HOW TO ADD THE FAISS INDEX TO YOUR LEGALONE BACKEND

In your `rag_pipeline.py`, replace the hardcoded `LEGAL_CORPUS` with:

```python
import pickle, faiss, numpy as np
from sentence_transformers import SentenceTransformer

INDEX_PATH = "./dataset/faiss_index/legal_rag"

def load_real_index():
    global _index, _documents
    _index = faiss.read_index(INDEX_PATH + ".faiss")
    with open(INDEX_PATH + "_metadata.pkl", "rb") as f:
        _documents = pickle.load(f)
    print(f"[RAG] Loaded real index: {_index.ntotal} principles")

def retrieve(query: str, top_k: int = 5) -> list:
    if _index is None:
        load_real_index()
    encoder = SentenceTransformer("all-MiniLM-L6-v2")
    qvec = np.array(encoder.encode([query]), dtype=np.float32)
    D, I = _index.search(qvec, top_k)
    results = []
    for d, i in zip(D[0], I[0]):
        if i < len(_documents):
            r = dict(_documents[i])
            r["score"] = round(1/(1+float(d)), 4)
            results.append(r)
    return sorted(results, key=lambda x: x["score"], reverse=True)
```

That's it — your LegalOne system now uses real Indian court data instead of the hardcoded 20-item corpus.

---

## DIVORCE DATASET JSON FORMAT — QUICK REFERENCE

Each divorce case JSON has these key sections:

```json
{
  "id":              "DIV_MAD_2024_CaseName",
  "domain":          "divorce",
  "sub_domain":      "divorce_cruelty",
  "case_name":       "Petitioner v. Respondent",
  "court":           "High Court of Judicature at Madras",
  "delivered_on":    "DD.MM.YYYY",

  "marriage_details": {
    "date_of_marriage": "DD.MM.YYYY",
    "type":             "Hindu"
  },

  "grounds_claimed":     ["S13_1_ia"],
  "grounds_established": ["S13_1_ia"],
  "grounds_rejected":    [],

  "cruelty_incidents": [
    {
      "date": "approx 2020",
      "description": "husband physically assaulted wife",
      "type": "physical_violence",
      "proved": true
    }
  ],

  "legal_principles": [
    {
      "principle_id": "LP_001",
      "principle":    "One-line reusable rule",
      "held":         "What court actually said",
      "applicable_acts_sections": ["HMA S.13(1)(ia)"],
      "keywords":     ["mental cruelty", "divorce"],
      "favours":      "petitioner",
      "significance": "HIGH"
    }
  ],

  "reliefs_granted": {
    "divorce_granted":  true,
    "maintenance_awarded": "Rs.15,000/month"
  },

  "keywords": ["divorce", "cruelty", "mental cruelty", "..."]
}
```

---

## SUPPORT
LegalOne by TLC | www.legalone.cc | customersupport@legalone.cc
