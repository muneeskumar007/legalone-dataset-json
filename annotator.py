"""
annotator.py
──────────────────────────────────────────────────────────────────
STEP 3 — Interactive CLI Annotator
Opens each pending JSON one-by-one and guides you to fill TODO fields.
Saves progress after each judgment so you can stop and resume.

Usage:
    python3 annotator.py --folder ./dataset/pending_annotation
    python3 annotator.py --folder ./dataset/pending_annotation --domain divorce
    python3 annotator.py --file ./dataset/pending_annotation/MyCase.json
"""

import argparse, json, os, sys
from pathlib import Path
from datetime import datetime


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def banner(text: str):
    print("\n" + "═"*60)
    print(f"  {text}")
    print("═"*60)


def ask(prompt: str, default: str = "", multiline: bool = False) -> str:
    """Ask for input, showing default. Returns default if empty Enter."""
    if multiline:
        print(f"\n{prompt}")
        print("  (Type your answer. Enter blank line when done.)")
        lines = []
        while True:
            line = input("  > ").strip()
            if not line and lines:
                break
            if line:
                lines.append(line)
        return " ".join(lines) or default
    else:
        val = input(f"\n{prompt} [{default or 'skip'}]: ").strip()
        return val if val else default


def ask_list(prompt: str, current: list) -> list:
    """Ask for comma-separated list."""
    print(f"\n{prompt}")
    if current:
        print(f"  Current: {', '.join(str(x) for x in current)}")
    val = input("  Enter (comma-separated, or Enter to keep): ").strip()
    if not val:
        return current
    return [v.strip() for v in val.split(",") if v.strip()]


def ask_choice(prompt: str, choices: list, default: str = "") -> str:
    print(f"\n{prompt}")
    for i, c in enumerate(choices, 1):
        marker = " ◀" if c == default else ""
        print(f"  {i}. {c}{marker}")
    while True:
        val = input(f"  Choose [1-{len(choices)}] or Enter for default: ").strip()
        if not val and default:
            return default
        if val.isdigit() and 1 <= int(val) <= len(choices):
            return choices[int(val)-1]
        print("  Invalid choice, try again.")


def annotate_judgment(record: dict) -> dict:
    """Interactive annotation of one judgment. Returns updated record."""

    clear()
    banner(f"ANNOTATING: {record.get('case_name','?')[:50]}")
    print(f"  Domain    : {record.get('domain')}")
    print(f"  Court     : {record.get('court')}")
    print(f"  Date      : {record.get('delivered_on')}")
    print(f"  Acts auto : {', '.join(record.get('acts_cited_auto',[])[:4])}")
    print(f"  Citations : {len(record.get('case_citations',[]))} found")
    print(f"  Outcome   : {record.get('outcome_detected','?')[:80]}")

    print("\n  Press ENTER at each prompt to skip / keep current value.")
    print("  Type 'done' at any time to save and move to next file.")

    # ── 1. Case name fix ────────────────────────────────────────
    print("\n── STEP 1: CASE DETAILS ──────────────────────────────")
    name = ask("Case name (Petitioner v. Respondent)", record.get("case_name",""))
    if name: record["case_name"] = name

    plaintiff = ask("Plaintiff/Petitioner name + role",
                    record.get("parties",{}).get("petitioner_plaintiff",""))
    defendant = ask("Defendant/Respondent name + role",
                    record.get("parties",{}).get("respondent_defendant",""))
    if plaintiff:
        record.setdefault("parties",{})["petitioner_plaintiff"] = plaintiff
    if defendant:
        record.setdefault("parties",{})["respondent_defendant"] = defendant

    trial = ask("Trial court (name + case number)", record.get("trial_court",""))
    if trial: record["trial_court"] = trial

    # ── 2. Facts ─────────────────────────────────────────────────
    print("\n── STEP 2: FACTS OF CASE ─────────────────────────────")
    current_facts = record.get("facts_of_case","")
    if current_facts == "TODO — 3-5 sentence summary" or not current_facts:
        facts = ask(
            "Facts (3-5 sentences: who, what happened, relief claimed, trial court held, why appealed)",
            multiline=True
        )
        if facts: record["facts_of_case"] = facts
    else:
        print(f"  Current: {current_facts[:120]}…")
        if input("  Edit? (y/N): ").strip().lower() == "y":
            facts = ask("New facts", multiline=True)
            if facts: record["facts_of_case"] = facts

    # ── 3. Issues ────────────────────────────────────────────────
    print("\n── STEP 3: ISSUES DECIDED ────────────────────────────")
    issues = record.get("issues_decided", [])
    if issues and issues[0].get("question") == "TODO":
        add_issues = input("  Add issues? (y/N): ").strip().lower() == "y"
        if add_issues:
            new_issues = []
            i = 1
            while True:
                q = ask(f"Issue {i} question (or Enter to stop)")
                if not q: break
                a = ask(f"Issue {i} answer/held")
                new_issues.append({"issue_no": i, "question": q, "answer": a})
                i += 1
            if new_issues: record["issues_decided"] = new_issues

    # ── 4. Legal Principles (most important) ─────────────────────
    print("\n── STEP 4: LEGAL PRINCIPLES ──────────────────────────")
    print("  This is the MOST IMPORTANT step.")
    print("  Extract reusable legal rules the court applied.")

    principles = record.get("legal_principles", [])
    is_placeholder = (
        not principles or
        principles[0].get("principle") == "TODO — one line reusable rule"
    )

    if is_placeholder:
        record["legal_principles"] = []

    add_more = input(
        f"\n  Current principles: {len([p for p in record.get('legal_principles',[]) if p.get('principle','').lower()[:4] != 'todo'])}"
        f"\n  Add/edit principles? (y/N): "
    ).strip().lower() == "y"

    if add_more:
        current_count = len(record["legal_principles"])
        while True:
            print(f"\n  Principle #{current_count + 1}")
            principle = ask("  Principle (one-line reusable rule)")
            if not principle: break

            held     = ask("  Held (what court actually said, 2-4 sentences)", multiline=True)
            secs     = ask("  Applicable sections (comma-separated, e.g. HMA S.13, IEA S.101)")
            secs_list= [s.strip() for s in secs.split(",")] if secs else []
            cites    = ask("  Cited cases (comma-separated citations)")
            cites_list=[c.strip() for c in cites.split(",")] if cites else []
            kws      = ask("  Keywords (comma-separated, 5-8 terms)")
            kws_list = [k.strip() for k in kws.split(",")] if kws else []
            favours  = ask_choice("  Favours", ["plaintiff","defendant","neutral"], "neutral")
            use_in   = ask("  Use in (comma-separated case types)")
            use_list = [u.strip() for u in use_in.split(",")] if use_in else []
            sig      = ask_choice("  Significance", ["HIGH","MEDIUM","LOW"], "MEDIUM")

            record["legal_principles"].append({
                "principle_id": f"LP_{current_count+1:03d}",
                "principle":    principle,
                "held":         held,
                "applicable_acts_sections": secs_list,
                "cited_cases":  cites_list,
                "keywords":     kws_list,
                "favours":      favours,
                "use_in":       use_list,
                "significance": sig
            })
            current_count += 1

            if input("\n  Add another principle? (y/N): ").strip().lower() != "y":
                break

    # ── 5. Outcome ───────────────────────────────────────────────
    print("\n── STEP 5: OUTCOME ───────────────────────────────────")
    print(f"  Auto-detected: {record.get('outcome_detected','none')[:100]}")
    current_outcome = record.get("outcome", {})

    result = ask("Result (e.g. Appeal allowed / Suit decreed)",
                 current_outcome.get("result","") if isinstance(current_outcome,dict) else "")
    order  = ask("Final order summary (2-3 sentences)", multiline=True)
    relief = ask("Relief granted")

    if result or order or relief:
        record["outcome"] = {
            "result":        result or current_outcome.get("result",""),
            "final_order":   order  or current_outcome.get("final_order",""),
            "relief_granted":relief or current_outcome.get("relief_granted",""),
            "costs":         current_outcome.get("costs","")
                             if isinstance(current_outcome,dict) else ""
        }

    # ── 6. Keywords ──────────────────────────────────────────────
    print("\n── STEP 6: KEYWORDS ──────────────────────────────────")
    current_kws = record.get("keywords", [])
    valid_kws   = [k for k in current_kws if k.lower() != "todo"]
    if not valid_kws or len(valid_kws) < 5:
        kws_input = ask("Keywords (comma-separated, 15+ terms covering legal concepts, facts, sections)")
        if kws_input:
            record["keywords"] = [k.strip() for k in kws_input.split(",") if k.strip()]
    else:
        print(f"  Current ({len(valid_kws)}): {', '.join(valid_kws[:6])}…")
        if input("  Add more? (y/N): ").strip().lower() == "y":
            more = ask("Additional keywords (comma-separated)")
            if more:
                record["keywords"] = valid_kws + [k.strip() for k in more.split(",") if k.strip()]

    # ── 7. Metadata ──────────────────────────────────────────────
    print("\n── STEP 7: METADATA ──────────────────────────────────")
    score_input = ask("Relevance score 1-5 (5=SC/landmark, 4=HC Division, 3=HC Single, 2=District)",
                      str(record.get("relevance_score", 0)))
    if score_input.isdigit():
        record["relevance_score"] = int(score_input)

    use_draft = ask("Use for drafting (comma-separated, e.g. 'Divorce petition mental cruelty, Will challenge')")
    if use_draft:
        record["use_for_drafting"] = [u.strip() for u in use_draft.split(",") if u.strip()]

    # ── 8. Mark annotation status ────────────────────────────────
    print("\n── STEP 8: MARK STATUS ───────────────────────────────")
    status = ask_choice(
        "Annotation status",
        ["partial", "complete", "pending"],
        record.get("annotation_status","pending")
    )
    record["annotation_status"]  = status
    record["annotation_verified"] = status == "complete"
    record["annotated_by"]        = ask("Your name (annotator)", record.get("annotated_by",""))
    record["updated_at"]          = datetime.now().isoformat()

    return record


def run_annotation(folder: str, domain_filter: str = None, single_file: str = None):
    """Main annotation loop."""
    if single_file:
        files = [Path(single_file)]
    else:
        folder_path = Path(folder)
        files = sorted(folder_path.glob("*.json"))
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

    pending = [f for f in files if f.name != "batch_index.json"]
    print(f"\n{'═'*60}")
    print(f"  LegalOne Annotator")
    print(f"  {len(pending)} files to process")
    if domain_filter:
        print(f"  Domain filter: {domain_filter}")
    print(f"{'═'*60}")

    for i, jf in enumerate(pending, 1):
        with open(jf, encoding="utf-8") as f:
            record = json.load(f)

        # Skip already verified (unless single file)
        if record.get("annotation_verified") and not single_file:
            print(f"  [skip] {jf.name} — already verified")
            continue

        print(f"\n  File {i}/{len(pending)}: {jf.name}")
        proceed = input("  Annotate this file? (Y/n/skip): ").strip().lower()
        if proceed == "n":
            break
        if proceed == "skip":
            continue

        updated = annotate_judgment(record)

        # Save back
        with open(jf, "w", encoding="utf-8") as f:
            json.dump(updated, f, ensure_ascii=False, indent=2)

        print(f"\n  ✓ Saved: {jf.name}")

        if i < len(pending):
            if input("\n  Continue to next file? (Y/n): ").strip().lower() == "n":
                break

    print("\n✓ Annotation session complete.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="LegalOne Interactive Annotator")
    p.add_argument("--folder", default="./dataset/pending_annotation")
    p.add_argument("--domain", default=None, help="Filter by domain, e.g. divorce")
    p.add_argument("--file",   default=None, help="Annotate a single file")
    args = p.parse_args()
    run_annotation(args.folder, args.domain, args.file)
