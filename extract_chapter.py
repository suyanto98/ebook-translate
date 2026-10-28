# -*- coding: utf-8 -*-
"""Extract per-block text + layout metadata for a page range (0-indexed,
inclusive) of the source PDF, for translation.

Usage: python3 extract_chapter.py <start_pdf0idx> <end_pdf0idx> <out_json>
"""
import sys
import json
import pymupdf

SRC = "/home/jacky/Downloads/roadmap bigtech/grokking-algorithms-2nd-edition-2nd_compress.pdf"


def extract(start, end, out_path):
    doc = pymupdf.open(SRC)
    pages_data = []
    for pno in range(start, end + 1):
        page = doc[pno]
        d = page.get_text("dict")
        blocks_out = []
        images_out = []
        for b in d["blocks"]:
            if b["type"] != 0:
                images_out.append(list(b["bbox"]))
                continue
            lines_text = []
            for l in b["lines"]:
                lines_text.append("".join(s["text"] for s in l["spans"]))
            full_text = "\n".join(lines_text).strip()
            if not full_text:
                continue
            span0 = b["lines"][0]["spans"][0]
            is_code = span0["font"].startswith("Courier")
            blocks_out.append({
                "bbox": list(b["bbox"]),
                "font": span0["font"],
                "size": span0["size"],
                "color": span0["color"],
                "text": full_text,
                "is_code": is_code,
            })
        pages_data.append({"pdf_index": pno, "blocks": blocks_out, "images": images_out})

    with open(out_path, "w") as f:
        json.dump(pages_data, f, indent=1, ensure_ascii=False)

    total = sum(len(p["blocks"]) for p in pages_data)
    non_code = sum(1 for p in pages_data for b in p["blocks"] if not b["is_code"])
    print(f"Extracted {len(pages_data)} pages -> {out_path}")
    print(f"Total blocks: {total}, translatable (non-code): {non_code}")
    print("Per-page non_code counts (paste this into your translations file check):")
    for p in pages_data:
        nc = sum(1 for b in p["blocks"] if not b["is_code"])
        print(f"  pdf_index {p['pdf_index']}: {nc}")


if __name__ == "__main__":
    start, end, out_path = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    extract(start, end, out_path)
