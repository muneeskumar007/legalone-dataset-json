# LEGALONE DATASET PIPELINE — COMPLETE GUIDE
# Answers all your questions clearly

---

## QUESTION 1: Is annotation manual only? Any way to automate?

### SHORT ANSWER: YES — you can fully automate using Ollama

### 3 MODES available:

| Mode | What it does | Accuracy | Speed | When to use |
|---|---|---|---|---|
| `template` | Rule-based only, no LLM | 40-50% | Instant | When Ollama not running |
| `hybrid` | Template + 1 Ollama call for principles | 70-80% | ~1 min/case | Recommended for most cases |
| `ollama` | Full 3 Ollama calls per case | 80-90% | ~3 min/case | Best quality |

### Run automation (all 30 cases in one command):

```bash
# RECOMMENDED — hybrid mode (fast + good quality)
python3 auto_annotator.py --mode hybrid --input ./dataset/pending_annotation

# For divorce cases only
python3 auto_annotator.py --mode hybrid --input ./dataset/pending_annotation --domain divorce

# Best quality (slower, 3 Ollama calls per case)
python3 auto_annotator.py --mode ollama --input ./dataset/pending_annotation

# No LLM at all (instant, lower quality)
python3 auto_annotator.py --mode template --input ./dataset/pending_annotation
```

### Why manual was originally recommended:
- LLMs can hallucinate section numbers
- Legal principles need precise language
- A wrong principle misleads advocates

### What you should actually do:
1. Run automation first (hybrid mode) — gets 70-80% accuracy
2. Spot-check 5-6 records manually — verify principles look correct
3. Mark important high-value cases (relevance score 5) for human review
4. Use auto for everything else

---

## QUESTION 2: Why only 2 judgments per day?

### SHORT ANSWER: That was manual-only estimate. There is NO limit.

- Manual mode: 2/day (reading + typing = 45 min each)
- Template mode: ALL 30 in under 1 minute
- Hybrid mode: ALL 30 in about 30-45 minutes
- Ollama mode: ALL 30 in about 1.5 hours

With automation, do all 30 in one sitting today.

---

## QUESTION 3: I add 60 more PDFs later. Do I need to delete the first 30?

### SHORT ANSWER: NO. Never delete. Just add and run one command.

### What happens step by step:

```
BEFORE:  pdfs/ folder has 30 files
         database has 30 records

ACTION:  Copy 60 new PDFs into pdfs/ folder (now 90 total)
         Run: python3 add_more_pdfs.py --input ./pdfs --mode hybrid

INSIDE THE SCRIPT:
  - Reads existing database → finds 30 already processed filenames
  - Scans pdfs/ folder → finds 90 PDFs
  - Computes difference → 60 are NEW
  - Processes ONLY the 60 new ones
  - First 30 are SKIPPED completely
  - Result: database now has 90 records

AFTER:   pdfs/ folder still has 90 files (nothing deleted)
         database has 90 records (30 old + 60 new)
```

### The one command for adding more PDFs:

```bash
# Add new PDFs (auto-detects what's new, skips what's already done)
python3 add_more_pdfs.py --input ./pdfs --mode hybrid
```

---

## FULL WORKFLOW — Start to finish

### FIRST TIME (30 PDFs):

```bash
# 1. Put all 30 PDFs in ./pdfs folder

# 2. Install once
pip install pdfplumber tqdm sentence-transformers faiss-cpu numpy

# 3. Extract PDFs to JSON shells (automatic, 5 min)
python3 run_pipeline.py --step 1 --input ./pdfs

# 4. Store in database (automatic, 1 min)
python3 run_pipeline.py --step 2

# 5. Auto-annotate ALL 30 at once (30-45 min, Ollama must be running)
python auto_annotator.py --mode ollama --input ./dataset/pending_annotation

# 6. Store annotations in database
python run_pipeline.py --step 2

# 7. Export divorce dataset + validate
python run_pipeline.py --step 4

# 8. Build FAISS search index
python run_pipeline.py --step 5

# 9. Test search
python run_pipeline.py --step search --query "divorce mental cruelty"
```

### ADDING 60 MORE PDFs LATER:

```bash
# Just copy 60 new PDFs into ./pdfs folder
# Then run ONE command — it handles everything:
python3 add_more_pdfs.py --input ./pdfs --mode hybrid

# Then rebuild FAISS index with new data
python3 run_pipeline.py --step 5
```

That's it. One command adds 60 more, skips the first 30, updates the database, and you rebuild the FAISS index.

---

## HOW AUTO-ANNOTATION WORKS INTERNALLY

### Template mode (no Ollama needed):

```
For each JSON shell:
  1. Reads domain (already detected in Step 1)
  2. Applies pre-written legal principles for that domain
     (2 principles per domain stored as templates)
  3. Auto-generates facts from available metadata
  4. Generates keywords from act names + domain + case name
  5. Sets relevance score from court type (SC=5, HC Div=4, etc.)
  6. Saves as annotation_status: "auto_template"
```

### Ollama/Hybrid mode:

```
For each JSON shell:
  1. Reloads the original PDF text
  2. Makes structured JSON prompts to Ollama
     Prompt 1 → facts, parties, outcome
     Prompt 2 → legal principles (the key one)
     Prompt 3 → keywords, relevance score
  3. Parses Ollama JSON responses
  4. Merges into record
  5. Saves as annotation_status: "auto_llm" or "auto_hybrid"
```

---

## QUALITY LEVELS EXPLAINED

After auto-annotation, your records will have different quality levels:

| Status | Meaning | Use for RAG? |
|---|---|---|
| `auto_template` | Rule-based only, generic principles | Yes, but weak |
| `auto_hybrid` | Template + LLM principles | Yes, good |
| `auto_llm` | Full LLM 3-call annotation | Yes, good |
| `complete` | Human verified, best quality | Yes, excellent |
| `partial` | Human started but not finished | Maybe |

### For production LegalOne:
- Use `auto_hybrid` or `auto_llm` for bulk dataset
- Add `complete` (human-verified) for the top 20 most-cited cases
- Even `auto_template` is better than the original hardcoded 20 items

---

## COMMANDS CHEAT SHEET

```bash
# CHECK STATUS
python run_pipeline.py --step status

# PROCESS NEW PDFs (first time or adding more)
python3 run_pipeline.py --step 1 --input ./pdfs     # extract
python3 run_pipeline.py --step 2                     # store in DB

# AUTO ANNOTATE
python3 auto_annotator.py --mode hybrid              # all cases
python3 auto_annotator.py --mode hybrid --domain divorce   # divorce only
python3 auto_annotator.py --mode template            # no Ollama needed
python3 auto_annotator.py --mode ollama --model phi3 # smaller model

# ADD MORE PDFs LATER (handles duplicates automatically)
python3 add_more_pdfs.py --input ./pdfs --mode hybrid

# EXPORT
python3 dataset_store.py --action export --domain divorce --output divorce.json
python3 dataset_store.py --action stats

# SEARCH
python run_pipeline.py --step search --query "divorce cruelty"
python dataset_store.py --action search --keyword "mental cruelty"
python dataset_store.py --action search --act "Hindu Marriage Act"

# BUILD FAISS (run after annotation)
python run_pipeline.py --step 5

# VALIDATE DIVORCE CASES
python3 run_pipeline.py --step 4
```

---

## WHAT IF OLLAMA IS SLOW?

Use a smaller model:
```bash
ollama pull phi3          # 2.3 GB — faster
python3 auto_annotator.py --mode hybrid --model phi3
```

Or use template only (instant):
```bash
python3 auto_annotator.py --mode template
```

---

## FILES IN THIS PIPELINE

| File | Purpose |
|---|---|
| `batch_processor.py` | Step 1: PDF → JSON shells (automatic) |
| `dataset_store.py` | Step 2: JSON → SQLite database + search |
| `auto_annotator.py` | Step 3: Fill TODO fields using Ollama or templates |
| `annotator.py` | Step 3 manual: Interactive CLI for human annotation |
| `divorce_schema.py` | Step 4: Divorce-specific validation + export |
| `build_faiss_pipeline.py` | Step 5: Build FAISS vector search index |
| `add_more_pdfs.py` | Add new PDFs without touching existing ones |
| `run_pipeline.py` | Master runner for all steps |

LegalOne by TLC | www.legalone.cc
