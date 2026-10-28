# -*- coding: utf-8 -*-
"""Resumable, one-chapter-at-a-time pipeline for the EN->ID book translation.

Progress lives in progress.json so work can be spread across many
sessions: each session only needs to look at one chapter's extract
JSON (~15-25 pages) instead of the whole 322-page book, which keeps token
usage per session small and lets you pick up exactly where you left off.

Usage:
  python3 pipeline.py status              show progress for every chapter
  python3 pipeline.py extract             extract the next pending chapter's pages to JSON
  python3 pipeline.py build <chapter_id>  build one chapter's PDF (needs its translations module)
  python3 pipeline.py build-all           build every chapter that has a translations module but isn't built yet
  python3 pipeline.py merge [out.pdf]     stitch all built chapters into one PDF, in page order

Typical cicilan flow per session:
  1. python3 pipeline.py extract          -> writes <chapter>_extract.json, tells you the module name to create
  2. write TRANSLATIONS = {...} in that translations_<id>.py file
  3. python3 pipeline.py build <chapter_id>
  4. repeat next session with step 1 again; run `merge` once everything is built
"""
import sys
import os
import json
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
PROGRESS_FILE = os.path.join(ROOT, "progress.json")


def load():
    with open(PROGRESS_FILE) as f:
        return json.load(f)


def save(data):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def sync_status(data):
    """Advance each chapter's status based on files actually present on disk,
    so the tracker self-heals if a build was run outside the pipeline."""
    changed = False
    for ch in data["chapters"]:
        path = lambda p: os.path.join(ROOT, p)
        if ch["status"] == "pending" and os.path.exists(path(ch["extract_json"])):
            ch["status"] = "extracted"
            changed = True
        if ch["status"] == "extracted" and os.path.exists(path(ch["translations_module"] + ".py")):
            ch["status"] = "translated"
            changed = True
        if ch["status"] == "translated" and os.path.exists(path(ch["built_pdf"])):
            ch["status"] = "built"
            changed = True
    if changed:
        save(data)
    return data


def cmd_status(data):
    for ch in data["chapters"]:
        print(f"{ch['id']:<14} pages {ch['start']:>3}-{ch['end']:<3}  {ch['status']}")


def cmd_extract(data):
    for ch in data["chapters"]:
        if ch["status"] == "pending":
            print(f"Extracting {ch['id']} (pages {ch['start']}-{ch['end']}) -> {ch['extract_json']}")
            subprocess.run(
                [sys.executable, "extract_chapter.py", str(ch["start"]), str(ch["end"]), ch["extract_json"]],
                cwd=ROOT, check=True,
            )
            ch["status"] = "extracted"
            save(data)
            print(
                f"\nNext: write TRANSLATIONS in {ch['translations_module']}.py "
                f"(one Indonesian string per non-code block per page, in extraction order "
                f"-- see per-page counts printed above), then run:\n"
                f"  python3 pipeline.py build {ch['id']}"
            )
            return
    print("Nothing pending -- every chapter has already been extracted.")


def cmd_build(data, chapter_id):
    for ch in data["chapters"]:
        if ch["id"] == chapter_id:
            tmod_path = os.path.join(ROOT, ch["translations_module"] + ".py")
            if not os.path.exists(tmod_path):
                print(f"No {ch['translations_module']}.py yet -- write the translations first.")
                return
            out_dir = os.path.dirname(os.path.join(ROOT, ch["built_pdf"]))
            os.makedirs(out_dir, exist_ok=True)
            subprocess.run(
                [sys.executable, "build_chapter.py", str(ch["start"]), str(ch["end"]),
                 ch["extract_json"], ch["translations_module"], ch["built_pdf"]],
                cwd=ROOT, check=True,
            )
            ch["status"] = "built"
            save(data)
            return
    print(f"Unknown chapter id: {chapter_id}")


def cmd_build_all(data):
    did_any = False
    for ch in data["chapters"]:
        if ch["status"] == "translated":
            cmd_build(data, ch["id"])
            did_any = True
    if not did_any:
        print("Nothing ready to build.")


def cmd_merge(data, out_path):
    import pymupdf
    built = [ch for ch in data["chapters"] if ch["status"] == "built"]
    built.sort(key=lambda c: c["start"])
    missing = [ch["id"] for ch in data["chapters"] if ch["status"] != "built"]
    if missing:
        print(f"Not built yet, skipping from merge: {', '.join(missing)}")
    out = __import__("pymupdf").open()
    for ch in built:
        out.insert_pdf(pymupdf.open(os.path.join(ROOT, ch["built_pdf"])))
    out.save(out_path, garbage=4, deflate=True)
    print(f"Merged {len(built)} chapters -> {out_path}")


def main():
    data = sync_status(load())
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "status":
        cmd_status(data)
    elif cmd == "extract":
        cmd_extract(data)
    elif cmd == "build" and len(sys.argv) > 2:
        cmd_build(data, sys.argv[2])
    elif cmd == "build-all":
        cmd_build_all(data)
    elif cmd == "merge":
        cmd_merge(data, sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "grokking-algorithms-id-full.pdf"))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
