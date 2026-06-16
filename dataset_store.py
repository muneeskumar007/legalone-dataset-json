"""
dataset_store.py
──────────────────────────────────────────────────────────────────
STEP 2 — Multi-case JSON Dataset Storage System
Handles:
  - Storing multiple divorce + all case type JSONs in one SQLite DB
  - Search by domain / keyword / case name / section
  - Export filtered records (e.g. all divorce cases)
  - Track annotation progress
  - Merge principles for FAISS

Usage:
    python3 dataset_store.py --action store  --input ./dataset/pending_annotation
    python3 dataset_store.py --action search --domain divorce
    python3 dataset_store.py --action export --domain divorce --output divorce_cases.json
    python3 dataset_store.py --action stats
"""

import argparse, json, sqlite3, os, sys
from pathlib import Path
from datetime import datetime

DB_PATH = "./legalone_dataset.db"


# ═══════════════════════════════════════════════════════════════
# DATABASE SETUP
# ═══════════════════════════════════════════════════════════════

def init_db(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Main judgments table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS judgments (
        id                  TEXT PRIMARY KEY,
        pdf_filename        TEXT,
        json_filename       TEXT,
        case_name           TEXT,
        neutral_citation    TEXT,
        court               TEXT,
        bench               TEXT,
        domain              TEXT NOT NULL,
        sub_domain          TEXT,
        delivered_on        TEXT,
        reserved_on         TEXT,
        outcome_result      TEXT,
        total_pages         INTEGER,
        relevance_score     INTEGER DEFAULT 0,
        annotation_status   TEXT DEFAULT 'pending',
        annotation_verified INTEGER DEFAULT 0,
        annotated_by        TEXT,
        source_url          TEXT,
        full_json           TEXT NOT NULL,
        created_at          TEXT,
        updated_at          TEXT
    )
    """)

    # Legal principles table (flat, for fast RAG search)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS legal_principles (
        id              TEXT PRIMARY KEY,
        judgment_id     TEXT NOT NULL,
        case_name       TEXT,
        court           TEXT,
        domain          TEXT,
        delivered_on    TEXT,
        principle_id    TEXT,
        principle       TEXT NOT NULL,
        held            TEXT,
        sections        TEXT,
        cited_cases     TEXT,
        keywords        TEXT,
        favours         TEXT,
        use_in          TEXT,
        significance    TEXT,
        embed_text      TEXT,
        FOREIGN KEY (judgment_id) REFERENCES judgments(id)
    )
    """)

    # Keywords index table (for fast keyword search)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS keyword_index (
        keyword     TEXT,
        judgment_id TEXT,
        domain      TEXT,
        PRIMARY KEY (keyword, judgment_id),
        FOREIGN KEY (judgment_id) REFERENCES judgments(id)
    )
    """)

    # Acts index table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS acts_index (
        act_name    TEXT,
        judgment_id TEXT,
        domain      TEXT,
        PRIMARY KEY (act_name, judgment_id),
        FOREIGN KEY (judgment_id) REFERENCES judgments(id)
    )
    """)

    # FTS (Full Text Search) virtual table
    cur.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS judgments_fts
    USING fts5(
        judgment_id,
        case_name,
        facts,
        principles_text,
        keywords_text
    )
    """)

    conn.commit()
    return conn


# ═══════════════════════════════════════════════════════════════
# STORE A SINGLE JUDGMENT JSON INTO DB
# ═══════════════════════════════════════════════════════════════

def store_judgment(conn: sqlite3.Connection, record: dict, json_filename: str = "") -> bool:
    cur  = conn.cursor()
    now  = datetime.now().isoformat()
    jid  = record.get("id", "")

    if not jid:
        print(f"  [skip] No id field in record")
        return False

    # Check duplicate
    existing = cur.execute("SELECT id FROM judgments WHERE id=?", (jid,)).fetchone()
    if existing:
        # Update instead
        cur.execute("""
            UPDATE judgments SET
                full_json           = ?,
                annotation_status   = ?,
                annotation_verified = ?,
                annotated_by        = ?,
                relevance_score     = ?,
                updated_at          = ?
            WHERE id = ?
        """, (
            json.dumps(record, ensure_ascii=False),
            record.get("annotation_status", "pending"),
            1 if record.get("annotation_verified") else 0,
            record.get("annotated_by", ""),
            record.get("relevance_score", 0),
            now, jid
        ))
        print(f"  [update] {jid}")
    else:
        cur.execute("""
            INSERT INTO judgments VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            jid,
            record.get("pdf_filename", ""),
            json_filename,
            record.get("case_name", ""),
            record.get("neutral_citation", ""),
            record.get("court", ""),
            record.get("bench", ""),
            record.get("domain", ""),
            record.get("sub_domain", ""),
            record.get("delivered_on", ""),
            record.get("reserved_on", ""),
            record.get("outcome", {}).get("result", "")
                if isinstance(record.get("outcome"), dict)
                else str(record.get("outcome", "")),
            record.get("total_pages", 0),
            record.get("relevance_score", 0),
            record.get("annotation_status", "pending"),
            1 if record.get("annotation_verified") else 0,
            record.get("annotated_by", ""),
            record.get("source_url", ""),
            json.dumps(record, ensure_ascii=False),
            now, now
        ))

    # ── Index keywords ───────────────────────────────────────────
    keywords = record.get("keywords", [])
    if isinstance(keywords, list):
        for kw in keywords:
            if kw and kw.lower() != "todo":
                try:
                    cur.execute(
                        "INSERT OR IGNORE INTO keyword_index VALUES (?,?,?)",
                        (kw.lower().strip(), jid, record.get("domain",""))
                    )
                except: pass

    # ── Index acts ───────────────────────────────────────────────
    for act in record.get("acts_cited_auto", []) + \
               [a.get("act","") for a in record.get("acts_cited", [])]:
        if act and act != "TODO":
            try:
                cur.execute(
                    "INSERT OR IGNORE INTO acts_index VALUES (?,?,?)",
                    (act, jid, record.get("domain",""))
                )
            except: pass

    # ── Store legal principles (flat) ────────────────────────────
    cur.execute("DELETE FROM legal_principles WHERE judgment_id=?", (jid,))

    for lp in record.get("legal_principles", []):
        pid    = lp.get("principle_id","LP_000")
        full_id = f"{jid}_{pid}"
        secs   = lp.get("applicable_acts_sections", [])
        cites  = lp.get("cited_cases", [])
        kws    = lp.get("keywords", [])
        use    = lp.get("use_in", [])

        # embed_text for FAISS later
        embed  = " ".join(filter(None, [
            lp.get("principle",""),
            lp.get("held",""),
            " ".join(kws) if isinstance(kws,list) else "",
            " ".join(secs) if isinstance(secs,list) else ""
        ]))

        try:
            cur.execute("""
                INSERT OR REPLACE INTO legal_principles VALUES
                (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                full_id, jid,
                record.get("case_name",""),
                record.get("court",""),
                record.get("domain",""),
                record.get("delivered_on",""),
                pid,
                lp.get("principle",""),
                lp.get("held",""),
                json.dumps(secs),
                json.dumps(cites),
                json.dumps(kws),
                lp.get("favours","neutral"),
                json.dumps(use),
                lp.get("significance",""),
                embed
            ))
        except Exception as e:
            print(f"    [warn] principle store failed: {e}")

    # ── FTS index ────────────────────────────────────────────────
    facts  = record.get("facts_of_case","")
    ptext  = " ".join(
        lp.get("principle","") + " " + lp.get("held","")
        for lp in record.get("legal_principles",[])
    )
    kwtext = " ".join(record.get("keywords",[]))

    cur.execute("DELETE FROM judgments_fts WHERE judgment_id=?", (jid,))
    cur.execute(
        "INSERT INTO judgments_fts VALUES (?,?,?,?,?)",
        (jid, record.get("case_name",""), facts, ptext, kwtext)
    )

    conn.commit()
    return True


def store_folder(conn: sqlite3.Connection, folder: str):
    """Store all JSON files in a folder into the database."""
    folder_path = Path(folder)
    json_files  = list(folder_path.glob("*.json"))
    print(f"\nStoring {len(json_files)} JSON files from {folder}")
    print("─"*50)

    stored = 0
    for jf in json_files:
        if jf.name == "batch_index.json":
            continue
        try:
            with open(jf, encoding="utf-8") as f:
                record = json.load(f)
            ok = store_judgment(conn, record, jf.name)
            if ok: stored += 1
        except Exception as e:
            print(f"  [error] {jf.name}: {e}")

    print(f"\n✓ Stored {stored}/{len(json_files)} records into database")
    _print_stats(conn)


# ═══════════════════════════════════════════════════════════════
# SEARCH & RETRIEVAL
# ═══════════════════════════════════════════════════════════════

def search_by_domain(conn: sqlite3.Connection, domain: str) -> list:
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT id,case_name,court,delivered_on,relevance_score,annotation_status "
        "FROM judgments WHERE domain=? ORDER BY relevance_score DESC, delivered_on DESC",
        (domain,)
    ).fetchall()
    return [dict(r) for r in rows]


def search_by_keyword(conn: sqlite3.Connection, keyword: str) -> list:
    cur = conn.cursor()
    rows = cur.execute("""
        SELECT DISTINCT j.id, j.case_name, j.court, j.domain, j.delivered_on
        FROM judgments j
        JOIN keyword_index k ON j.id = k.judgment_id
        WHERE k.keyword LIKE ?
        ORDER BY j.relevance_score DESC
    """, (f"%{keyword.lower()}%",)).fetchall()
    return [dict(r) for r in rows]


def search_by_act(conn: sqlite3.Connection, act_name: str) -> list:
    cur = conn.cursor()
    rows = cur.execute("""
        SELECT DISTINCT j.id, j.case_name, j.court, j.domain, j.delivered_on
        FROM judgments j
        JOIN acts_index a ON j.id = a.judgment_id
        WHERE a.act_name LIKE ?
        ORDER BY j.relevance_score DESC
    """, (f"%{act_name}%",)).fetchall()
    return [dict(r) for r in rows]


def fulltext_search(conn: sqlite3.Connection, query: str) -> list:
    cur = conn.cursor()
    try:
        rows = cur.execute("""
            SELECT j.id, j.case_name, j.court, j.domain, j.delivered_on
            FROM judgments j
            JOIN judgments_fts fts ON j.id = fts.judgment_id
            WHERE judgments_fts MATCH ?
            LIMIT 20
        """, (query,)).fetchall()
        return [dict(r) for r in rows]
    except:
        # FTS fallback
        rows = cur.execute("""
            SELECT id, case_name, court, domain, delivered_on
            FROM judgments
            WHERE case_name LIKE ? OR full_json LIKE ?
            LIMIT 20
        """, (f"%{query}%", f"%{query}%")).fetchall()
        return [dict(r) for r in rows]


def get_judgment(conn: sqlite3.Connection, judgment_id: str) -> dict:
    cur = conn.cursor()
    row = cur.execute(
        "SELECT full_json FROM judgments WHERE id=?", (judgment_id,)
    ).fetchone()
    if row:
        return json.loads(row["full_json"])
    return {}


def get_principles_for_rag(
    conn: sqlite3.Connection,
    domain: str = None,
    verified_only: bool = False
) -> list:
    """Get all legal principles for FAISS embedding."""
    cur  = conn.cursor()
    sql  = "SELECT lp.*, j.neutral_citation FROM legal_principles lp JOIN judgments j ON lp.judgment_id = j.id"
    args = []
    where = []

    if domain:
        where.append("lp.domain = ?")
        args.append(domain)
    if verified_only:
        where.append("j.annotation_verified = 1")

    # Exclude TODO placeholders
    where.append("lp.principle != 'TODO — one line reusable rule'")
    where.append("lp.principle IS NOT NULL")
    where.append("length(lp.principle) > 20")

    if where:
        sql += " WHERE " + " AND ".join(where)

    rows = cur.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════════

def export_domain(
    conn: sqlite3.Connection,
    domain: str,
    output_path: str,
    verified_only: bool = False
):
    """Export all records for a domain as JSON array."""
    cur   = conn.cursor()
    sql   = "SELECT full_json FROM judgments WHERE domain=?"
    args  = [domain]
    if verified_only:
        sql += " AND annotation_verified=1"
    sql += " ORDER BY relevance_score DESC"

    rows    = cur.execute(sql, args).fetchall()
    records = [json.loads(r["full_json"]) for r in rows]

    output = {
        "domain":       domain,
        "total":        len(records),
        "exported_at":  datetime.now().isoformat(),
        "verified_only":verified_only,
        "judgments":    records
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✓ Exported {len(records)} {domain} records → {output_path}")


def export_principles_for_faiss(
    conn: sqlite3.Connection,
    output_path: str,
    domain: str = None
):
    """Export flat principles list ready for FAISS embedding."""
    principles = get_principles_for_rag(conn, domain=domain)

    output = {
        "domain":       domain or "all",
        "total":        len(principles),
        "exported_at":  datetime.now().isoformat(),
        "principles":   principles
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✓ Exported {len(principles)} principles → {output_path}")
    return principles


# ═══════════════════════════════════════════════════════════════
# STATS
# ═══════════════════════════════════════════════════════════════

def _print_stats(conn: sqlite3.Connection):
    cur  = conn.cursor()
    total    = cur.execute("SELECT COUNT(*) FROM judgments").fetchone()[0]
    verified = cur.execute("SELECT COUNT(*) FROM judgments WHERE annotation_verified=1").fetchone()[0]
    pending  = cur.execute("SELECT COUNT(*) FROM judgments WHERE annotation_status='pending'").fetchone()[0]
    princips = cur.execute("SELECT COUNT(*) FROM legal_principles WHERE length(principle)>20").fetchone()[0]
    domains  = cur.execute("SELECT domain, COUNT(*) as c FROM judgments GROUP BY domain ORDER BY c DESC").fetchall()

    print("\n" + "═"*50)
    print("  DATABASE STATS")
    print("═"*50)
    print(f"  Total judgments   : {total}")
    print(f"  Verified          : {verified}")
    print(f"  Pending annotation: {pending}")
    print(f"  Legal principles  : {princips}")
    print(f"\n  By Domain:")
    for row in domains:
        bar = "█" * row[1]
        print(f"    {row[0]:<25} {bar} {row[1]}")
    print("═"*50)


# ═══════════════════════════════════════════════════════════════
# MAIN CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="LegalOne Dataset Store")
    p.add_argument("--action",  choices=["store","search","export","stats","export-rag"],
                   required=True)
    p.add_argument("--input",   default="./dataset/pending_annotation",
                   help="Folder of JSON files (for store)")
    p.add_argument("--domain",  default=None,
                   help="Domain filter: divorce, cheque_bounce, partition …")
    p.add_argument("--keyword", default=None)
    p.add_argument("--act",     default=None)
    p.add_argument("--output",  default=None)
    p.add_argument("--db",      default=DB_PATH)
    p.add_argument("--verified-only", action="store_true")
    args = p.parse_args()

    conn = init_db(args.db)

    if args.action == "store":
        store_folder(conn, args.input)

    elif args.action == "stats":
        _print_stats(conn)

    elif args.action == "search":
        results = []
        if args.domain:
            results = search_by_domain(conn, args.domain)
            print(f"\n{len(results)} judgments in domain '{args.domain}':")
        elif args.keyword:
            results = search_by_keyword(conn, args.keyword)
            print(f"\n{len(results)} judgments with keyword '{args.keyword}':")
        elif args.act:
            results = search_by_act(conn, args.act)
            print(f"\n{len(results)} judgments citing '{args.act}':")

        for r in results:
            status = "✓" if r.get("annotation_status") == "verified" else "○"
            print(f"  {status} [{r.get('delivered_on','?')}] {r.get('case_name','?')[:55]} | {r.get('court','')[:25]}")

    elif args.action == "export":
        out = args.output or f"{args.domain or 'all'}_cases.json"
        export_domain(conn, args.domain or "divorce", out, args.verified_only)

    elif args.action == "export-rag":
        out = args.output or f"{args.domain or 'all'}_principles.json"
        export_principles_for_faiss(conn, out, args.domain)

    conn.close()
