"""
add_more_pdfs.py
─────────────────────────────────────────────────────────────────
Handles adding NEW PDFs to an existing dataset without touching
already-processed files.

Solves your exact question:
  "I have 30 done. Now I add 60 more. What happens?"

Answer: Only the NEW 60 are processed. The first 30 are untouched.

Usage:
  python3 add_more_pdfs.py --input ./pdfs --mode hybrid
  python3 add_more_pdfs.py --input ./new_pdfs_folder --mode ollama
  python3 add_more_pdfs.py --input ./pdfs --mode template --domain divorce
"""

import argparse, json, sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH     = "./legalone_dataset.db"
DATASET_DIR = Path("./dataset")


def get_already_processed() -> set:
    """
    Return set of PDF filenames already in the database.
    These will be skipped when running on new PDFs.
    """
    processed = set()

    # Check from database
    if Path(DB_PATH).exists():
        conn = sqlite3.connect(DB_PATH)
        cur  = conn.cursor()
        rows = cur.execute("SELECT pdf_filename FROM judgments").fetchall()
        conn.close()
        for row in rows:
            if row[0]:
                processed.add(row[0].lower())

    # Also check from existing JSON files
    json_dir = DATASET_DIR / "pending_annotation"
    if json_dir.exists():
        for jf in json_dir.glob("*.json"):
            if jf.name == "batch_index.json":
                continue
            try:
                with open(jf) as f:
                    rec = json.load(f)
                pdf_name = rec.get("pdf_filename","")
                if pdf_name:
                    processed.add(pdf_name.lower())
            except:
                pass

    return processed


def find_new_pdfs(input_dir: str, already_processed: set) -> list:
    """Find PDFs in input_dir that are NOT yet in the dataset."""
    input_path = Path(input_dir)
    all_pdfs   = list(input_path.glob("*.pdf")) + list(input_path.glob("*.PDF"))
    new_pdfs   = []
    skipped    = []

    for pdf in all_pdfs:
        if pdf.name.lower() in already_processed:
            skipped.append(pdf.name)
        else:
            new_pdfs.append(pdf)

    return new_pdfs, skipped


def run_incremental(input_dir: str, mode: str = "hybrid", domain_filter: str = None):
    print("\n" + "═"*60)
    print("  LegalOne — Add New PDFs to Existing Dataset")
    print("═"*60)

    # Step 1: Find what's already done
    print("\n[1/4] Checking existing dataset…")
    already_done = get_already_processed()
    print(f"  Already processed: {len(already_done)} files")

    # Step 2: Find new PDFs only
    print("\n[2/4] Finding new PDFs…")
    new_pdfs, skipped = find_new_pdfs(input_dir, already_done)
    print(f"  New PDFs found   : {len(new_pdfs)}")
    print(f"  Already done     : {len(skipped)} (will be SKIPPED)")

    if not new_pdfs:
        print("\n  ✓ No new PDFs to process. Dataset is up to date.")
        return

    print("\n  New files to process:")
    for pdf in new_pdfs[:10]:
        print(f"    + {pdf.name}")
    if len(new_pdfs) > 10:
        print(f"    ... and {len(new_pdfs)-10} more")

    # Step 3: Extract new PDFs only
    print("\n[3/4] Extracting new PDFs to JSON shells…")
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from batch_processor import extract_text, build_shell_record, detect_domain

    output_dir = DATASET_DIR / "pending_annotation"
    output_dir.mkdir(parents=True, exist_ok=True)

    new_records = []
    for pdf_path in new_pdfs:
        try:
            pages, full_text, error = extract_text(str(pdf_path))
            if error or not full_text.strip():
                print(f"  [skip] {pdf_path.name}: {error or 'empty'}")
                continue

            record = build_shell_record(str(pdf_path), pages, full_text)

            # Apply domain filter
            if domain_filter and domain_filter.lower() not in record.get("domain","").lower():
                # Still save but mark
                record["domain_filter_note"] = f"domain={record.get('domain')} — filter was {domain_filter}"

            out_file = output_dir / (pdf_path.stem + ".json")
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False, indent=2)

            new_records.append(record)
            print(f"  ✓ {pdf_path.name} → {record.get('domain','?')}")

        except Exception as e:
            print(f"  ✗ {pdf_path.name}: {e}")

    print(f"\n  Extracted {len(new_records)} new records")

    # Step 4: Auto-annotate new records
    print(f"\n[4/4] Auto-annotating with mode={mode}…")
    from auto_annotator import run_auto_annotate
    run_auto_annotate(
        folder        = str(output_dir),
        mode          = mode,
        domain_filter = domain_filter,
        skip_done     = True,   # skip already-annotated ones
        verbose       = True,
    )

    # Step 5: Store in database
    print("\n[5/5] Storing in database…")
    from dataset_store import init_db, store_folder, _print_stats
    conn = init_db(DB_PATH)
    store_folder(conn, str(output_dir))
    conn.close()

    print("\n" + "═"*60)
    print("  DONE")
    print(f"  New records added : {len(new_records)}")
    print(f"  First 30 untouched: {len(skipped)} files skipped")
    print(f"  Total in dataset  : {len(already_done) + len(new_records)}")
    print("═"*60)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Add new PDFs to existing LegalOne dataset")
    p.add_argument("--input",  default="./pdfs",
                   help="Folder containing ALL PDFs (old + new). Old ones auto-skipped.")
    p.add_argument("--mode",   default="hybrid",
                   choices=["ollama","template","hybrid"],
                   help="Annotation mode for new files only")
    p.add_argument("--domain", default=None, help="Optional domain filter")
    args = p.parse_args()
    run_incremental(args.input, args.mode, args.domain)
