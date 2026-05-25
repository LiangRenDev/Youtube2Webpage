import re
import os
import sys
import json
import anthropic

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

# ── AI summarisation ──────────────────────────────────────────────────────────

def summarize_section(client: anthropic.Anthropic, section_label: str, raw_text: str) -> str:
    """Call Claude to turn a raw transcript chunk into a coherent summary paragraph."""
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        system=(
            "You are a technical content editor writing magazine-style summaries of "
            "conference talks. Write clear, engaging prose — no bullet points, no headers."
        ),
        messages=[{
            "role": "user",
            "content": (
                f"Below is the raw transcript from the '{section_label}' section of a talk "
                f"by Tesla VP Ashok Elluswamy at ICCV 2025. Write a 3-5 sentence summary "
                f"that captures the key technical ideas and insights. Use a journalistic "
                f"tone suitable for a magazine article.\n\nTRANSCRIPT:\n{raw_text}"
            ),
        }],
    )
    return response.content[0].text.strip()


# ── Section builder ────────────────────────────────────────────────────────────

def build_sections(vtt_entries: list, video_id: str, summaries_file: str = "") -> list:
    """
    Group VTT text by chapter and build section dicts.

    If summaries_file is provided (or a summaries.json exists in project_dir),
    those pre-written summaries are used and no API call is made.
    Otherwise, each section is summarised via the Claude API.
    """
    # Load pre-written summaries when available (slug → text mapping)
    pre = {}
    if summaries_file and os.path.exists(summaries_file):
        with open(summaries_file, encoding="utf-8") as f:
            pre = json.load(f)
        print(f"Using pre-written summaries from {summaries_file}")

    ai = None if pre else anthropic.Anthropic()
    sections = []
    for ch in CHAPTERS:
        texts = [e["text"] for e in vtt_entries if ch["start"] <= e["secs"] < ch["end"]]
        raw_text = " ".join(texts)
        if ch["slug"] in pre:
            summary = pre[ch["slug"]]
            print(f"  Using pre-written summary for '{ch['label']}'")
        else:
            print(f"  Summarising '{ch['label']}' via API ({len(texts)} entries)…")
            summary = summarize_section(ai, ch["label"], raw_text)
        yt_url = f"https://www.youtube.com/watch?v={video_id}&t={int(ch['start'])}"
        sections.append({
            "slug":       ch["slug"],
            "label":      ch["label"],
            "summary":    summary,
            "raw_text":   raw_text,   # kept so skill can read it
            "display_ts": format_display_ts(ch["start"]),
            "yt_url":     yt_url,
        })
    return sections

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

META_DESCRIPTION = (
    "Tesla VP Ashok Elluswamy reveals Tesla's end-to-end neural network approach, "
    "world simulator, fleet data strategy, and Optimus robot transfer at ICCV 2025."
)

VIDEO_YT_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"

def render_html_head(first_image: str = "") -> str:
    og_image = f"images/{first_image}" if first_image else ""
    structured_data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": VIDEO_TITLE,
        "description": META_DESCRIPTION,
        "author": {"@type": "Person", "name": "Ashok Elluswamy"},
        "publisher": {"@type": "Organization", "name": "Tesla AI"},
        "isBasedOn": VIDEO_YT_URL,
        "keywords": "Tesla, autonomous driving, neural network, ICCV 2025, self-driving, world simulator",
    }
    import json
    ld = json.dumps(structured_data, indent=2)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{VIDEO_TITLE}</title>
  <meta name="description" content="{META_DESCRIPTION}">
  <meta name="robots" content="index, follow">

  <!-- Open Graph -->
  <meta property="og:type" content="article">
  <meta property="og:title" content="{VIDEO_TITLE}">
  <meta property="og:description" content="{META_DESCRIPTION}">
  <meta property="og:image" content="{og_image}">

  <!-- Twitter Card -->
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{VIDEO_TITLE}">
  <meta name="twitter:description" content="{META_DESCRIPTION}">
  <meta name="twitter:image" content="{og_image}">

  <!-- Structured data -->
  <script type="application/ld+json">
{ld}
  </script>

  <link rel="stylesheet" href="../styles.css">
</head>
<body>
"""

def render_nav() -> str:
    links = "".join(
        f'<a href="#{ch["slug"]}">{ch["label"].title()}</a>'
        for ch in CHAPTERS
    )
    mobile_links = "".join(
        f'<a class="mobile-nav-link" href="#{ch["slug"]}">{ch["label"].title()}</a>'
        for ch in CHAPTERS
    )
    return f"""<nav id="topnav">
  <span class="nav-brand">ICCV 2025</span>
  <div class="nav-chapters">{links}</div>
  <input id="search" type="search" placeholder="Search transcript…" autocomplete="off">
  <button id="burger" aria-label="Open menu" aria-expanded="false">&#9776;</button>
</nav>
<div id="mobile-menu" aria-hidden="true">
  {mobile_links}
</div>
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

def render_sections(sections: list) -> str:
    html = '<main id="transcript">\n'
    for sec in sections:
        safe_text = sec["summary"].replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
        html += f'<section class="chapter" id="{sec["slug"]}">\n'
        html += f'  <div class="chapter-divider"><span>{sec["label"]}</span></div>\n'
        html += f"""  <div class="section-summary">
    <p class="section-text">{safe_text}</p>
    <a class="section-link" href="{sec['yt_url']}" target="_blank" rel="noopener">
      Watch from {sec['display_ts']} on YouTube ↗
    </a>
  </div>
</section>
"""
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
      const text = (chapter.querySelector('.section-text') || {textContent:''}).textContent.toLowerCase();
      const match = !q || text.includes(q);
      chapter.classList.toggle('hidden', !match);
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

  // ── Mobile burger menu ───────────────────────────────────────────
  const burger = document.getElementById('burger');
  const mobileMenu = document.getElementById('mobile-menu');

  function closeMenu() {
    mobileMenu.classList.remove('open');
    burger.setAttribute('aria-expanded', 'false');
    burger.textContent = '\\u2630';
  }

  burger.addEventListener('click', () => {
    const isOpen = mobileMenu.classList.toggle('open');
    burger.setAttribute('aria-expanded', isOpen);
    burger.textContent = isOpen ? '\\u2715' : '\\u2630';
  });

  mobileMenu.querySelectorAll('.mobile-nav-link').forEach(a => {
    a.addEventListener('click', closeMenu);
  });
})();
</script>
"""

# ── Main ──────────────────────────────────────────────────────────────────────

def main(project_dir: str, output_slug: str = ""):
    import glob, shutil

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

    # Determine output directory under docs/
    slug = output_slug or os.path.basename(project_dir.rstrip("/\\"))
    out_dir = os.path.join("docs", slug)
    os.makedirs(out_dir, exist_ok=True)

    # Copy images into docs/<slug>/images/
    src_images = os.path.join(project_dir, "images")
    dst_images = os.path.join(out_dir, "images")
    if os.path.isdir(src_images):
        if os.path.exists(dst_images):
            shutil.rmtree(dst_images)
        shutil.copytree(src_images, dst_images)
        image_files = sorted(f for f in os.listdir(dst_images) if f.endswith(".jpg"))
    else:
        image_files = []
    hero_image = image_files[0] if image_files else ""

    # Build sections (use summaries.json from source dir)
    summaries_file = os.path.join(project_dir, "summaries.json")
    sections = build_sections(vtt_entries, VIDEO_ID, summaries_file)
    print(f"Built {len(sections)} sections")

    # Render HTML
    html = (
        render_html_head(hero_image)
        + render_nav()
        + render_hero(hero_image)
        + render_summary()
        + render_sections(sections)
        + render_scripts()
        + "\n</body>\n</html>\n"
    )

    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Written: {out_path}")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print(f"Usage: python3 {sys.argv[0]} <source-dir> [output-slug]", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else "")
