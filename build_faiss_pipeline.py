"""
build_faiss_pipeline.py
Complete pipeline:
  extracted JSON files → merge → embed → FAISS index → test retrieval

Usage:
  python3 build_faiss_pipeline.py

Requires:
  pip install sentence-transformers faiss-cpu numpy
"""

import json, pickle, numpy as np
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
DATASET_DIR  = Path("legalone_dataset/extracted_json")
MERGED_PATH  = Path("legalone_dataset/principles_only/all_principles.json")
INDEX_PATH   = Path("legalone_dataset/faiss_index/legal_rag")
MODEL_NAME   = "all-MiniLM-L6-v2"

# ── For demo: use our two extracted judgments ─────────────────────────────────
DEMO_FILES = [
    Path("/mnt/user-data/outputs/santhosh_kumar_dataset.json"),
    Path("/mnt/user-data/outputs/chinnasamy_judgment.json"),
]


# ════════════════════════════════════════════════════════════════
# STEP 1 — MERGE PRINCIPLES
# ════════════════════════════════════════════════════════════════

def merge_principles_from_files(json_files: list, output_path: Path) -> list:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    all_principles = []

    for jf in json_files:
        if not Path(jf).exists():
            print(f"  [skip] {jf} not found")
            continue
        with open(jf, encoding="utf-8") as f:
            record = json.load(f)

        case_ref = {
            "case_id":          record.get("id"),
            "case_name":        record.get("case_name"),
            "court":            record.get("court"),
            "delivered_on":     record.get("delivered_on"),
            "neutral_citation": record.get("neutral_citation"),
            "domain":           record.get("domain"),
            "sub_domain":       record.get("sub_domain"),
        }

        for principle in record.get("legal_principles", []):
            text_parts = [
                principle.get("principle", ""),
                principle.get("held", ""),
                " ".join(principle.get("keywords", [])),
                " ".join(principle.get("applicable_acts_sections", []))
                if isinstance(principle.get("applicable_acts_sections"), list)
                else str(principle.get("applicable_acts_sections", ""))
            ]
            entry = {
                **case_ref,
                "principle_id": principle.get("principle_id"),
                "principle":    principle.get("principle"),
                "held":         principle.get("held"),
                "sections":     principle.get("applicable_acts_sections", []),
                "keywords":     principle.get("keywords", []),
                "favours":      principle.get("favours"),
                "significance": principle.get("significance"),
                "use_in":       principle.get("use_in", []),
                "embed_text":   " ".join(filter(None, text_parts))
            }
            all_principles.append(entry)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_principles, f, ensure_ascii=False, indent=2)

    print(f"[Merge] {len(all_principles)} principles from {len(json_files)} files → {output_path}")
    return all_principles


# ════════════════════════════════════════════════════════════════
# STEP 2 — BUILD FAISS INDEX
# ════════════════════════════════════════════════════════════════

def build_faiss_index(principles: list, index_path: Path):
    try:
        from sentence_transformers import SentenceTransformer
        import faiss
    except ImportError:
        print("[Error] Run: pip install sentence-transformers faiss-cpu")
        return

    index_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[Embed] Loading model {MODEL_NAME}…")
    model  = SentenceTransformer(MODEL_NAME)
    texts  = [p["embed_text"] for p in principles]

    print(f"[Embed] Encoding {len(texts)} principles…")
    embeds = model.encode(texts, show_progress_bar=True, batch_size=16)
    embeds = np.array(embeds, dtype=np.float32)

    dim   = embeds.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeds)

    # Save FAISS index
    faiss.write_index(index, str(index_path) + ".faiss")

    # Save metadata
    metadata = [{k: v for k, v in p.items() if k != "embed_text"}
                for p in principles]
    with open(str(index_path) + "_metadata.pkl", "wb") as f:
        pickle.dump(metadata, f)

    print(f"[Index] {index.ntotal} vectors (dim={dim}) → {index_path}.faiss")
    return index, metadata


# ════════════════════════════════════════════════════════════════
# STEP 3 — RETRIEVAL FUNCTION
# ════════════════════════════════════════════════════════════════

def retrieve(query: str, index_path: Path, top_k: int = 5) -> list:
    try:
        from sentence_transformers import SentenceTransformer
        import faiss
    except ImportError:
        return []

    model  = SentenceTransformer(MODEL_NAME)
    index  = faiss.read_index(str(index_path) + ".faiss")
    with open(str(index_path) + "_metadata.pkl", "rb") as f:
        metadata = pickle.load(f)

    qvec = np.array(model.encode([query], show_progress_bar=False), dtype=np.float32)
    distances, indices = index.search(qvec, top_k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx < len(metadata):
            r = dict(metadata[idx])
            r["score"] = round(float(1 / (1 + dist)), 4)
            results.append(r)
    return sorted(results, key=lambda x: x["score"], reverse=True)


# ════════════════════════════════════════════════════════════════
# STEP 4 — TEST QUERIES
# ════════════════════════════════════════════════════════════════

TEST_QUERIES = [
    "client wants divorce due to mental cruelty husband",
    "will validity attesting witness cross examination",
    "ancestral property kartha purchased from joint family income",
    "illegitimate child inherit from grandparents void marriage",
    "sale deed kartha coparcenary property extent valid",
    "CCTV evidence mobile phone 65B certificate admissibility",
    "cheque bounce presumption legally enforceable debt rebuttal",
    "partition suit daughter coparcener Hindu Succession Act",
]

def run_test_queries(index_path: Path):
    print("\n" + "═"*60)
    print("  RETRIEVAL TEST")
    print("═"*60)
    for query in TEST_QUERIES:
        print(f"\nQuery: \"{query}\"")
        results = retrieve(query, index_path, top_k=2)
        for i, r in enumerate(results):
            print(f"  [{r['score']:.3f}] {r.get('case_name','?')} | {r.get('principle','?')[:70]}…")


# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("LegalOne RAG Pipeline\n")

    # Step 1
    principles = merge_principles_from_files(DEMO_FILES, MERGED_PATH)

    # Step 2
    result = build_faiss_index(principles, INDEX_PATH)
    if result:
        # Step 3 — test
        run_test_queries(INDEX_PATH)

    print("\n✓ Pipeline complete.")
    print(f"  Principles merged : {MERGED_PATH}")
    print(f"  FAISS index       : {INDEX_PATH}.faiss")
    print(f"  Metadata          : {INDEX_PATH}_metadata.pkl")
    print("\nTo use in LegalOne backend:")
    print("  from build_faiss_pipeline import retrieve, INDEX_PATH")
    print("  results = retrieve('client wants divorce due to cruelty', INDEX_PATH)")
