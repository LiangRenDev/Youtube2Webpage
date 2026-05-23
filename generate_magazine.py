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

# ── HTML rendering ────────────────────────────────────────────────────────────

VIDEO_ID = "IRu-cPkpiFk"
VIDEO_TITLE = "A Peek into Tesla's Autonomous Future: Core Tech Revealed by VP Ashok Elluswamy"
VIDEO_META  = "TESLA AI · ASHOK ELLUSWAMY · ICCV 2025"

SUMMARY_TEXT = (
    "Tesla VP Ashok Elluswamy reveals the full end-to-end neural network stack "
    "powering production vehicles today—from raw camera pixels to steering "
    "output—plus the world simulator used to train and evaluate it. Key topics: "
    "fleet data at scale (“the Niagara Falls of data”), 3D Gaussian splatting "
    "for scene reconstruction, closed-loop reinforcement learning, and transfer of "
    "the same architecture to Tesla's Optimus humanoid robot. Milestones covered: "
    "commercial robotaxi launch in Austin and the SF Bay Area, and production vehicles "
    "autonomously driving off the assembly line."
)

def render_html_head() -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{VIDEO_TITLE}</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
"""

def render_nav() -> str:
    links = "".join(
        f'<a href="#{ch["slug"]}">{ch["label"].title()}</a>'
        for ch in CHAPTERS
    )
    return f"""<nav id="topnav">
  <span class="nav-brand">ICCV 2025</span>
  <div class="nav-chapters">{links}</div>
  <input id="search" type="search" placeholder="Search transcript…" autocomplete="off">
</nav>
"""

def render_hero(first_image: str) -> str:
    return f"""<section class="hero" style="background-image:url('images/{first_image}')">
  <div class="hero-overlay">
    <div class="hero-meta">{VIDEO_META}</div>
    <h1>{VIDEO_TITLE}</h1>
  </div>
</section>
"""

def render_summary() -> str:
    return f"""<div class="summary-box">
  <div class="summary-label">SUMMARY</div>
  <p>{SUMMARY_TEXT}</p>
</div>
"""

def render_transcript(entries: list) -> str:
    """
    Group entries by chapter, emit a chapter section for each,
    alternating entry-img-left / entry-img-right within each chapter.
    """
    from itertools import groupby

    html = '<main id="transcript">\n'
    for chapter_slug, group in groupby(entries, key=lambda e: e["chapter_slug"]):
        group = list(group)
        chapter_label = group[0]["chapter_label"]
        html += f'<section class="chapter" id="{chapter_slug}">\n'
        html += f'  <div class="chapter-divider"><span>{chapter_label}</span></div>\n'
        for i, entry in enumerate(group):
            side_class = "entry-img-left" if i % 2 == 0 else "entry-img-right"
            safe_text = entry["text"].replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
            html += f"""  <article class="entry {side_class}">
    <a class="entry-image" href="{entry['yt_url']}" target="_blank" rel="noopener">
      <img src="images/{entry['image']}" alt="" loading="lazy">
      <span class="timestamp">{entry['display_ts']} ↗</span>
    </a>
    <p class="entry-text">{safe_text}</p>
  </article>
"""
        html += "</section>\n"
    html += "</main>\n"
    return html

def render_scripts() -> str:
    return """<script>
(function () {
  // ── Search ──────────────────────────────────────────────────────
  const searchInput = document.getElementById('search');

  searchInput.addEventListener('input', () => {
    const q = searchInput.value.toLowerCase().trim();
    document.querySelectorAll('.chapter').forEach(chapter => {
      let visibleCount = 0;
      chapter.querySelectorAll('.entry').forEach(entry => {
        const text = entry.querySelector('.entry-text').textContent.toLowerCase();
        const match = !q || text.includes(q);
        entry.classList.toggle('hidden', !match);
        if (match) visibleCount++;
      });
      const divider = chapter.querySelector('.chapter-divider');
      if (divider) divider.classList.toggle('hidden', visibleCount === 0 && !!q);
    });
  });

  // ── Chapter nav highlighting ─────────────────────────────────────
  const navLinks = document.querySelectorAll('.nav-chapters a');

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        navLinks.forEach(l => l.classList.remove('active'));
        const link = document.querySelector(`.nav-chapters a[href="#${entry.target.id}"]`);
        if (link) link.classList.add('active');
      }
    });
  }, { rootMargin: '-10% 0px -80% 0px' });

  document.querySelectorAll('.chapter').forEach(ch => observer.observe(ch));
})();
</script>
"""

# ── Main ──────────────────────────────────────────────────────────────────────

def main(project_dir: str):
    import glob

    # Locate VTT file
    vtt_files = glob.glob(os.path.join(project_dir, "*.vtt"))
    if not vtt_files:
        print(f"ERROR: no .vtt file found in {project_dir}", file=sys.stderr)
        sys.exit(1)
    vtt_path = vtt_files[0]

    # Parse VTT
    with open(vtt_path, encoding="utf-8") as f:
        vtt_text = f.read()
    vtt_entries = parse_vtt_clean_entries(vtt_text)
    print(f"Parsed {len(vtt_entries)} VTT entries from {os.path.basename(vtt_path)}")

    # List images
    images_dir = os.path.join(project_dir, "images")
    image_files = sorted(f for f in os.listdir(images_dir) if f.endswith(".jpg"))
    print(f"Found {len(image_files)} images")

    # Build entries
    entries = build_entries(vtt_entries, image_files, VIDEO_ID)

    # Render HTML
    html = (
        render_html_head()
        + render_nav()
        + render_hero(image_files[0])
        + render_summary()
        + render_transcript(entries)
        + render_scripts()
        + "\n</body>\n</html>\n"
    )

    out_path = os.path.join(project_dir, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Written: {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python3 {sys.argv[0]} <project-dir>", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
