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
