"""
run_pipeline.py
──────────────────────────────────────────────────────────────────
MASTER RUNNER — ties all steps together for 30 judgment PDFs.

FULL WORKFLOW:
  Step 1: batch_processor.py  → PDF → shell JSON files
  Step 2: dataset_store.py    → JSON → SQLite DB
  Step 3: annotator.py        → fill TODO fields interactively
  Step 4: divorce_schema.py   → validate + export divorce cases
  Step 5: build_faiss_pipeline.py → embed → FAISS index

Usage:
  python3 run_pipeline.py --step all    --input ./pdfs --output ./dataset
  python3 run_pipeline.py --step 1      --input ./pdfs --output ./dataset
  python3 run_pipeline.py --step 2      --output ./dataset
  python3 run_pipeline.py --step 3      --domain divorce
  python3 run_pipeline.py --step 4
  python3 run_pipeline.py --step 5
  python3 run_pipeline.py --step status
"""

import argparse, json, sys, subprocess
from pathlib import Path
from datetime import datetime


DATASET_DIR  = Path("./dataset")
DB_PATH      = "./legalone_dataset.db"
PDF_DIR      = Path("./pdfs")


# ═══════════════════════════════════════════════════════════════
# STATUS CHECKER
# ═══════════════════════════════════════════════════════════════

def show_status():
    print("\n" + "═"*60)
    print("  LEGALONE DATASET PIPELINE — STATUS")
    print("═"*60)

    # PDFs
    pdf_count = len(list(PDF_DIR.glob("*.pdf")) + list(PDF_DIR.glob("*.PDF"))) if PDF_DIR.exists() else 0
    print(f"\n  📁 Input PDFs           : {pdf_count} in {PDF_DIR}")

    # Shell JSONs
    shell_dir = DATASET_DIR / "pending_annotation"
    shell_count = len(list(shell_dir.glob("*.json"))) if shell_dir.exists() else 0
    print(f"  📄 Shell JSONs created  : {shell_count} in {shell_dir}")

    # Database
    if Path(DB_PATH).exists():
        try:
            import sqlite3
            conn = sqlite3.connect(DB_PATH)
            cur  = conn.cursor()
            total    = cur.execute("SELECT COUNT(*) FROM judgments").fetchone()[0]
            verified = cur.execute("SELECT COUNT(*) FROM judgments WHERE annotation_verified=1").fetchone()[0]
            pending  = cur.execute("SELECT COUNT(*) FROM judgments WHERE annotation_status='pending'").fetchone()[0]
            princips = cur.execute("SELECT COUNT(*) FROM legal_principles WHERE length(principle)>20").fetchone()[0]
            domains  = cur.execute("SELECT domain,COUNT(*) FROM judgments GROUP BY domain ORDER BY 2 DESC").fetchall()
            conn.close()
            print(f"\n  🗄  Database             : {DB_PATH}")
            print(f"     Total judgments      : {total}")
            print(f"     Verified             : {verified}")
            print(f"     Pending annotation   : {pending}")
            print(f"     Legal principles     : {princips}")
            print(f"\n     Domain breakdown:")
            for d, c in domains:
                bar = "█" * c
                print(f"       {d:<25} {bar} {c}")
        except Exception as e:
            print(f"  ⚠  Database error: {e}")
    else:
        print(f"  🗄  Database             : NOT CREATED YET")

    # FAISS index
    faiss_file = DATASET_DIR / "faiss_index" / "legal_rag.faiss"
    if faiss_file.exists():
        size_kb = faiss_file.stat().st_size // 1024
        print(f"\n  🔍 FAISS index          : ✓ {size_kb} KB")
    else:
        print(f"\n  🔍 FAISS index          : NOT BUILT YET")

    # Divorce dataset
    divorce_file = Path("./divorce_dataset.json")
    if divorce_file.exists():
        with open(divorce_file) as f:
            dd = json.load(f)
        print(f"\n  💍 Divorce dataset      : {dd.get('total',0)} cases in {divorce_file}")
    else:
        print(f"\n  💍 Divorce dataset      : NOT CREATED YET")

    print("\n" + "═"*60)
    print("  NEXT STEPS:")
    if pdf_count > 0 and shell_count == 0:
        print("  → Run: python3 run_pipeline.py --step 1 --input ./pdfs")
    elif shell_count > 0 and not Path(DB_PATH).exists():
        print("  → Run: python3 run_pipeline.py --step 2")
    elif Path(DB_PATH).exists():
        if pending > 0 if 'pending' in dir() else False:
            print(f"  → Annotate {pending} pending cases: python3 run_pipeline.py --step 3")
        if not faiss_file.exists():
            print("  → Build FAISS: python3 run_pipeline.py --step 5")
    print("═"*60 + "\n")


# ═══════════════════════════════════════════════════════════════
# STEP 1 — BATCH EXTRACT PDFs
# ═══════════════════════════════════════════════════════════════

def step1_extract(input_dir: str, output_dir: str):
    print("\n" + "─"*60)
    print("  STEP 1 — Extract PDFs to Shell JSONs")
    print("─"*60)
    from batch_processor import process_batch
    process_batch(input_dir, output_dir)


# ═══════════════════════════════════════════════════════════════
# STEP 2 — STORE IN DATABASE
# ═══════════════════════════════════════════════════════════════

def step2_store(output_dir: str):
    print("\n" + "─"*60)
    print("  STEP 2 — Store JSONs in SQLite Database")
    print("─"*60)
    from dataset_store import init_db, store_folder, _print_stats
    conn = init_db(DB_PATH)
    folder = str(Path(output_dir) / "pending_annotation")
    store_folder(conn, folder)
    conn.close()


# ═══════════════════════════════════════════════════════════════
# STEP 3 — INTERACTIVE ANNOTATION
# ═══════════════════════════════════════════════════════════════

def step3_annotate(domain_filter: str = None):
    print("\n" + "─"*60)
    print("  STEP 3 — Interactive Annotation")
    print("─"*60)
    folder = str(DATASET_DIR / "pending_annotation")
    from annotator import run_annotation
    run_annotation(folder, domain_filter)
    # Re-store annotated files
    step2_store(str(DATASET_DIR))


# ═══════════════════════════════════════════════════════════════
# STEP 4 — VALIDATE + EXPORT DIVORCE CASES
# ═══════════════════════════════════════════════════════════════

def step4_divorce():
    print("\n" + "─"*60)
    print("  STEP 4 — Validate & Export Divorce Dataset")
    print("─"*60)
    from divorce_schema import DivorceDataset, validate_divorce_record

    ds = DivorceDataset("./divorce_dataset.json")

    # Pull divorce records from database
    if Path(DB_PATH).exists():
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur  = conn.cursor()
        rows = cur.execute("""
            SELECT full_json FROM judgments
            WHERE domain IN ('divorce','matrimonial','family','maintenance','custody')
        """).fetchall()
        conn.close()

        added = 0
        for row in rows:
            try:
                rec = json.loads(row["full_json"])
                ds.add(rec)
                added += 1
            except: pass
        print(f"  Loaded {added} cases from database")

    # Validate all
    print("\n  Validation Report:")
    print("  " + "─"*50)
    vr = ds.validate_all()
    total = sum(len(vr[g]) for g in ["A","B","C","D"])
    for grade in ["A","B","C","D"]:
        for item in vr[grade]:
            icon = "✓" if grade in ("A","B") else "⚠"
            print(f"  {icon} Grade {grade} [{item['score']:3d}] {item['name']}")
            for issue in item["issues"][:2]:
                print(f"         → {issue}")

    # Stats
    s = ds.stats()
    print(f"\n  Summary: {s['total']} cases | {s['verified']} verified | {s['total_principles']} principles")

    # Export all divorce cases to one file
    out_all = "./dataset/divorce_all_cases.json"
    (DATASET_DIR).mkdir(exist_ok=True)
    data = {
        "domain": "divorce",
        "total": len(ds.records),
        "exported_at": datetime.now().isoformat(),
        "judgments": list(ds.records.values())
    }
    with open(out_all, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n  ✓ All divorce cases → {out_all}")

    # Export principles for RAG
    ds.export_for_rag("./dataset/divorce_principles_rag.json")
    print("  ✓ Divorce RAG principles exported")


# ═══════════════════════════════════════════════════════════════
# STEP 5 — BUILD FAISS INDEX
# ═══════════════════════════════════════════════════════════════

def step5_faiss():
    print("\n" + "─"*60)
    print("  STEP 5 — Build FAISS Vector Index")
    print("─"*60)

    # Collect all principles from database
    if not Path(DB_PATH).exists():
        print("  ✗ Database not found. Run steps 1-2 first.")
        return

    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()
    rows = cur.execute("""
        SELECT lp.*, j.neutral_citation, j.case_name, j.court, j.delivered_on, j.domain
        FROM legal_principles lp
        JOIN judgments j ON lp.judgment_id = j.id
        WHERE length(lp.principle) > 20
        AND lp.principle NOT LIKE 'TODO%'
    """).fetchall()
    conn.close()

    principles = []
    for row in rows:
        r = dict(row)
        r["embed_text"] = " ".join(filter(None, [
            r.get("principle",""),
            r.get("held",""),
            r.get("keywords",""),
            r.get("sections",""),
        ]))
        principles.append(r)

    print(f"  Principles to embed: {len(principles)}")

    if len(principles) == 0:
        print("  ✗ No annotated principles found. Complete Step 3 first.")
        return

    # Save merged principles
    (DATASET_DIR / "faiss_index").mkdir(parents=True, exist_ok=True)
    merged_path = DATASET_DIR / "faiss_index" / "all_principles.json"
    with open(merged_path, "w", encoding="utf-8") as f:
        json.dump(principles, f, ensure_ascii=False, indent=2)

    # Build FAISS index
    try:
        from sentence_transformers import SentenceTransformer
        import faiss, numpy as np, pickle

        model  = SentenceTransformer("all-MiniLM-L6-v2")
        texts  = [p["embed_text"] for p in principles]
        embeds = model.encode(texts, show_progress_bar=True, batch_size=16)
        embeds = np.array(embeds, dtype=np.float32)

        dim   = embeds.shape[1]
        index = faiss.IndexFlatL2(dim)
        index.add(embeds)

        index_path = str(DATASET_DIR / "faiss_index" / "legal_rag")
        faiss.write_index(index, index_path + ".faiss")

        meta = [{k:v for k,v in p.items() if k!="embed_text"} for p in principles]
        with open(index_path + "_metadata.pkl","wb") as f:
            pickle.dump(meta, f)

        print(f"\n  ✓ FAISS index: {index.ntotal} vectors (dim={dim})")
        print(f"  ✓ Saved → {index_path}.faiss")

        # Quick test
        print("\n  Testing retrieval…")
        test_queries = [
            "divorce mental cruelty husband wife",
            "will attestation validity execution",
            "ancestral property kartha burden of proof",
        ]
        for q in test_queries:
            qv = np.array(model.encode([q], show_progress_bar=False), dtype=np.float32)
            D, I = index.search(qv, 2)
            print(f"\n  Query: {q}")
            for d, i in zip(D[0], I[0]):
                if i < len(meta):
                    sc = round(1/(1+float(d)), 3)
                    print(f"    [{sc}] {meta[i].get('case_name','?')[:40]} | {meta[i].get('principle','?')[:60]}")

    except ImportError as e:
        print(f"  ✗ Missing library: {e}")
        print("  Install: pip install sentence-transformers faiss-cpu")


# ═══════════════════════════════════════════════════════════════
# QUICK SEARCH — test the index
# ═══════════════════════════════════════════════════════════════

def search_index(query: str):
    index_path = str(DATASET_DIR / "faiss_index" / "legal_rag")
    if not Path(index_path + ".faiss").exists():
        print("FAISS index not built yet. Run --step 5 first.")
        return

    try:
        from sentence_transformers import SentenceTransformer
        import faiss, numpy as np, pickle

        model = SentenceTransformer("all-MiniLM-L6-v2")
        index = faiss.read_index(index_path + ".faiss")
        with open(index_path + "_metadata.pkl","rb") as f:
            meta = pickle.load(f)

        qv = np.array(model.encode([query], show_progress_bar=False), dtype=np.float32)
        D, I = index.search(qv, 5)

        print(f"\nQuery: \"{query}\"")
        print("─"*60)
        for rank, (d, i) in enumerate(zip(D[0], I[0]), 1):
            if i < len(meta):
                m  = meta[i]
                sc = round(1/(1+float(d)), 3)
                print(f"#{rank} [{sc}] {m.get('case_name','?')[:45]}")
                print(f"   {m.get('principle','?')[:70]}")
                print(f"   Court: {m.get('court','?')} | {m.get('delivered_on','?')}")
                print()
    except ImportError as e:
        print(f"Missing: {e}")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="LegalOne Dataset Pipeline")
    p.add_argument("--step",   default="status",
                   choices=["all","1","2","3","4","5","status","search"])
    p.add_argument("--input",  default=str(PDF_DIR))
    p.add_argument("--output", default=str(DATASET_DIR))
    p.add_argument("--domain", default=None)
    p.add_argument("--query",  default=None)
    args = p.parse_args()

    if args.step == "status":
        show_status()
    elif args.step == "1":
        step1_extract(args.input, args.output)
    elif args.step == "2":
        step2_store(args.output)
    elif args.step == "3":
        step3_annotate(args.domain)
    elif args.step == "4":
        step4_divorce()
    elif args.step == "5":
        step5_faiss()
    elif args.step == "all":
        step1_extract(args.input, args.output)
        step2_store(args.output)
        print("\n  ⚠ Run annotation manually: python3 run_pipeline.py --step 3")
        print("  Then run: python3 run_pipeline.py --step 4")
        print("  Then run: python3 run_pipeline.py --step 5")
    elif args.step == "search":
        if not args.query:
            args.query = input("Enter search query: ")
        search_index(args.query)


# ═══════════════════════════════════════════════════════════════
# STEP 3A — AUTO ANNOTATION (add to existing run_pipeline.py)
# ═══════════════════════════════════════════════════════════════

def step3_auto(mode: str = "hybrid", domain_filter: str = None):
    print("\n" + "─"*60)
    print(f"  STEP 3A — Auto Annotation (mode: {mode})")
    print("─"*60)
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from auto_annotator import run_auto_annotate
    run_auto_annotate(
        folder        = str(DATASET_DIR / "pending_annotation"),
        mode          = mode,
        domain_filter = domain_filter,
        skip_done     = True,
        verbose       = True,
    )
    # Re-store updated annotations in DB
    step2_store(str(DATASET_DIR))
