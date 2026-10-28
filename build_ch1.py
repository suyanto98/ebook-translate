# -*- coding: utf-8 -*-
import json
import pymupdf
from translations import TRANSLATIONS

SRC = "/home/jacky/Downloads/roadmap bigtech/grokking-algorithms-2nd-edition-2nd_compress.pdf"
OUT = "/home/jacky/ebook-translate/grokking-algorithms-bab1-id.pdf"

doc = pymupdf.open(SRC)
extract = json.load(open("ch1_extract.json"))

LINE_SPACING = 1.24

_SANITIZE = {
    "•": "-",
    "‘": "'", "’": "'",
    "“": '"', "”": '"',
    "–": "-", "—": "--",
    "…": "...",
}


def sanitize(text):
    for k, v in _SANITIZE.items():
        text = text.replace(k, v)
    text = text.replace("\t\n", "\t ")
    return text


def color_tuple(c):
    r = ((c >> 16) & 255) / 255.0
    g = ((c >> 8) & 255) / 255.0
    b = (c & 255) / 255.0
    return (r, g, b)


def base14_for(font):
    is_bold = "Bold" in font or "Semibold" in font
    is_italic = "It" in font or "Italic" in font
    if font.startswith("MinionPro"):
        if is_bold and is_italic:
            return "tibi"
        if is_bold:
            return "tibo"
        if is_italic:
            return "tiit"
        return "tiro"
    if is_bold and is_italic:
        return "hebi"
    if is_bold:
        return "hebo"
    if is_italic:
        return "heit"
    return "helv"


_font_cache = {}


def get_font(fam):
    if fam not in _font_cache:
        _font_cache[fam] = pymupdf.Font(fam)
    return _font_cache[fam]


def estimate_lines(text, fam, size, width):
    font = get_font(fam)
    total_lines = 0
    for para in text.split("\n"):
        if para.strip() == "":
            total_lines += 1
            continue
        words = para.split(" ")
        cur = ""
        for w in words:
            trial = (cur + " " + w).strip()
            if font.text_length(trial, fontsize=size) <= width or not cur:
                cur = trial
            else:
                total_lines += 1
                cur = w
        total_lines += 1
    return max(total_lines, 1)


for page_data in extract:
    pno = page_data["pdf_index"]
    page = doc[pno]
    all_blocks = page_data["blocks"]
    non_code_blocks = [b for b in all_blocks if not b["is_code"]]
    translations = TRANSLATIONS.get(pno, [])

    # everything else on the page (code blocks + images) whose position must
    # NEVER move -- used only to find how much local whitespace exists below
    # each translated block before the next fixed element starts.
    other_tops = [b["bbox"][1] for b in all_blocks if b["is_code"]]
    other_tops += [img[1] for img in page_data["images"]]

    for b in non_code_blocks:
        rect = pymupdf.Rect(b["bbox"])
        page.add_redact_annot(rect, fill=(1, 1, 1))
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)

    page_bottom = page.rect.height - 9
    for i, (b, raw_text) in enumerate(zip(non_code_blocks, translations)):
        new_text = sanitize(raw_text)
        orig_rect = pymupdf.Rect(b["bbox"])
        font = b["font"]
        size = b["size"]
        color = color_tuple(b["color"])
        fam = base14_for(font)
        is_callout = font == "Univers-Bold"

        orig_lines = b["text"].split("\n")
        if len(orig_lines) == 2 and orig_lines[1].strip().isdigit():
            title_text = new_text.split("\n")[0]
            page_num = orig_lines[1].strip()
            line_rect = pymupdf.Rect(orig_rect.x0, orig_rect.y0, orig_rect.x1, orig_rect.y0 + size * 1.4)
            num_w = size * 0.7 * len(page_num) + 4
            num_rect = pymupdf.Rect(line_rect.x1 - num_w, line_rect.y0, line_rect.x1, line_rect.y1)
            title_rect = pymupdf.Rect(line_rect.x0, line_rect.y0, num_rect.x0 - 2, line_rect.y1)
            page.insert_textbox(title_rect, title_text, fontsize=size, fontname=fam, color=color, align=0)
            page.insert_textbox(num_rect, page_num, fontsize=size, fontname=fam, color=color, align=2)
            continue

        # how much local whitespace already exists below this block, before
        # the next fixed element (a code block, an image, or the page edge)
        next_tops = [t for t in other_tops if t > orig_rect.y1 - 1]
        # also consider the next translated block that follows this one
        for other in non_code_blocks[i + 1:]:
            next_tops.append(other["bbox"][1])
        ceiling = min(next_tops) if next_tops else page_bottom
        ceiling = min(ceiling, page_bottom)
        available_gap = max(ceiling - orig_rect.y1, 0)

        page_margin = page.rect.width - 9
        max_x1 = min(orig_rect.x0 + 45, page_margin) if is_callout else page_margin

        font_obj = get_font(fam)
        max_word_w = max(
            (font_obj.text_length(w, fontsize=size) for para in new_text.split("\n") for w in para.split(" ") if w),
            default=0,
        )
        rect = pymupdf.Rect(orig_rect)
        if max_word_w > rect.width:
            rect.x1 = min(rect.x0 + max_word_w + 2, max_x1)

        max_box_height = orig_rect.height + available_gap - 1

        rc = -1
        used_size = size
        floor = 5.0 if is_callout else 6.5
        while used_size >= floor:
            nlines = estimate_lines(new_text, fam, used_size, rect.width)
            needed_height = nlines * used_size * LINE_SPACING
            box_height = min(max(needed_height, orig_rect.height), max_box_height)
            rect.y1 = rect.y0 + max(box_height, used_size * LINE_SPACING)
            rc = page.insert_textbox(rect, new_text, fontsize=used_size, fontname=fam, color=color, align=0)
            if rc >= 0 and needed_height <= max_box_height + 0.5:
                break
            used_size -= 0.5
        if rc < 0 or needed_height > max_box_height + 0.5:
            print(f"WARN page {pno} (gap={available_gap:.1f}) size {used_size}: {new_text[:50]!r}")

doc.select(list(range(26, 46)))
doc.save(OUT, garbage=4, deflate=True)
print("Saved:", OUT)
