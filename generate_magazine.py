import re
import os
import sys

# ── VTT parsing ──────────────────────────────────────────────────────────────

def vtt_ts_to_secs(ts: str) -> float:
    """'HH:MM:SS.mmm' → float seconds."""
    h, m, s = ts.strip().split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)

def _strip_inline_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()

def parse_vtt_clean_entries(vtt_text: str) -> list:
    """
    Return [{secs, text}, ...] for every clean (10ms) entry in the VTT.
    Clean entries have end_secs - start_secs <= 0.015.
    """
    blocks = re.split(r"\n{2,}", vtt_text.strip())
    entries = []
    for block in blocks:
        lines = [l for l in block.splitlines() if l.strip()]
        ts_line = next((l for l in lines if " --> " in l), None)
        if not ts_line:
            continue
        parts = ts_line.split(" --> ")
        start_secs = vtt_ts_to_secs(parts[0].strip())
        end_secs = vtt_ts_to_secs(parts[1].split()[0])  # strip align metadata
        if end_secs - start_secs > 0.015:
            continue
        text_lines = lines[lines.index(ts_line) + 1:]
        text = " ".join(_strip_inline_tags(l) for l in text_lines if _strip_inline_tags(l))
        if text:
            entries.append({"secs": start_secs, "text": text})
    return entries

# ── Image helpers ─────────────────────────────────────────────────────────────

def img_filename_to_secs(filename: str) -> float:
    """'HH-MM-SS.mmm.jpg' → float seconds."""
    name = filename.replace(".jpg", "")
    h, m, s = name.split("-")
    return int(h) * 3600 + int(m) * 60 + float(s)

def format_display_ts(secs: float) -> str:
    """83.43 → '1:23'  (no leading zero on minutes)."""
    total = int(secs)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

# ── Chapter assignment ────────────────────────────────────────────────────────

CHAPTERS = [
    {"slug": "intro",        "label": "INTRO & MILESTONES",       "start":    0, "end":  150},
    {"slug": "architecture", "label": "END-TO-END ARCHITECTURE",  "start":  150, "end":  540},
    {"slug": "data",         "label": "DATA AT SCALE",            "start":  540, "end":  960},
    {"slug": "simulator",    "label": "WORLD SIMULATOR",          "start":  960, "end": 1260},
    {"slug": "robots",       "label": "ROBOTS & OPTIMUS",         "start": 1260, "end": 99999},
]

def assign_chapter(secs: float) -> dict:
    for ch in CHAPTERS:
        if ch["start"] <= secs < ch["end"]:
            return ch
    return CHAPTERS[-1]

# ── Entry builder ─────────────────────────────────────────────────────────────

def build_entries(vtt_entries: list, image_files: list, video_id: str) -> list:
    """
    For each image file (sorted), find the nearest VTT entry by timestamp.
    Returns list of entry dicts ready for HTML rendering.
    """
    result = []
    for img in sorted(image_files):
        secs = img_filename_to_secs(img)
        nearest = min(vtt_entries, key=lambda e: abs(e["secs"] - secs))
        chapter = assign_chapter(secs)
        result.append({
            "image":        img,
            "text":         nearest["text"],
            "secs":         secs,
            "display_ts":   format_display_ts(secs),
            "yt_url":       f"https://www.youtube.com/watch?v={video_id}&t={int(secs)}",
            "chapter_slug": chapter["slug"],
            "chapter_label": chapter["label"],
        })
    return result
