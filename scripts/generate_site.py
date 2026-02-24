#!/usr/bin/env python3
"""Generate interactive HTML course-skill browser.

Reads course profiles, skill mappings, and taxonomy, then generates
a single self-contained HTML file with all data embedded as JSON.
"""

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

CATEGORY_ORDER = [
    "AI Product Development",
    "AI Technical Skills",
    "PM Leadership",
    "Design",
]

CATEGORY_LABELS = {
    "AI Product Development": "A. AI Product Development",
    "AI Technical Skills": "B. AI Technical Skills",
    "PM Leadership": "D. PM Leadership",
    "Design": "E. Design",
}


def _leading_number(title: str):
    """Extract leading number from a title like '04 – FigJam' or 'Module 3: ...'."""
    m = re.match(r"^(\d+)\s*[–\-:.\s]", title)
    if m:
        return int(m.group(1))
    m = re.match(r"^(?:module|week|lesson|session|class|part|chapter)\s+(\d+)", title, re.I)
    if m:
        return int(m.group(1))
    return None


SKIP_PATTERNS = [
    "where to get support", "homework", "video recording",
    "recording", "password", "zoom", "dropbox", "welcome",
    "onboarding", "how to", "click on", "enter the password",
    "support@maven", "platform", "instructions", "three things to do",
    "what makes cohort-based", "live discussion", "weekly recap",
    "template:", "setting up", "class resources",
]


def extract_syllabus_summary(syllabus_text: str) -> str:
    """Extract section headers (### lines) from syllabus_text as a summary."""
    if not syllabus_text:
        return ""
    headers = []
    for line in syllabus_text.split("\n"):
        line = line.strip()
        if line.startswith("### "):
            title = line[4:].strip()
            if any(p in title.lower() for p in SKIP_PATTERNS):
                continue
            if len(title) > 3:
                headers.append(title)

    seen = set()
    unique = []
    for h in headers:
        if h.lower() not in seen:
            seen.add(h.lower())
            unique.append(h)

    numbered = [(i, _leading_number(h), h) for i, h in enumerate(unique)]
    num_with_number = sum(1 for _, n, _ in numbered if n is not None)
    if num_with_number > len(unique) * 0.4:
        numbered.sort(key=lambda x: (x[1] if x[1] is not None else 9999, x[0]))
        unique = [h for _, _, h in numbered]

    return ", ".join(unique[:15])


def main():
    with open(DATA_DIR / "course_profiles.json") as f:
        profiles = json.load(f)
    with open(DATA_DIR / "course_skill_mappings.json") as f:
        mappings = json.load(f)
    with open(DATA_DIR / "taxonomy.json") as f:
        taxonomy = json.load(f)
    with open(DATA_DIR / "raw_courses.json") as f:
        raw = json.load(f)

    revenue_by_id = {}
    for row in raw:
        cid = row["COURSE_ID"]
        if cid not in revenue_by_id:
            revenue_by_id[cid] = row.get("LIFETIME_NET_EARNINGS_USD") or 0

    profile_by_id = {p["course_id"]: p for p in profiles}

    # Build skill lookup
    skill_lookup = {}
    for s in taxonomy:
        if not s.get("is_tool_category"):
            skill_lookup[s["skill_code"]] = f"{s['skill_code']}: {s['skill_name']}"

    # Build courses for JS
    courses = []
    for m in mappings:
        cid = m["course_id"]
        profile = profile_by_id.get(cid, {})
        syllabus = extract_syllabus_summary(profile.get("syllabus_text", ""))

        courses.append({
            "id": cid,
            "name": m["course_name"],
            "url": profile.get("course_url", ""),
            "topics": profile.get("topics", ""),
            "skills": m.get("skills", []),       # [{code, weight}]
            "tools": m.get("tools", []),          # [tool names]
            "toolWeight": m.get("tool_weight", 0),
            "syllabus": syllabus,
            "_rev": revenue_by_id.get(cid, 0),   # will be converted to rank
        })

    # Convert revenue to rank ordinal (1=highest) so actual $ aren't exposed
    courses.sort(key=lambda c: -c["_rev"])
    for i, c in enumerate(courses):
        c["_r"] = len(courses) - i  # higher = better
        del c["_rev"]

    # Build category filters (A, B, D, E — no C)
    all_tools = sorted(set(t for c in courses for t in c["tools"]))
    category_filters = []
    for cat in CATEGORY_ORDER:
        label = CATEGORY_LABELS.get(cat, cat)
        skills = [s for s in taxonomy if s["category"] == cat]
        letter = label.split(".")[0].strip()  # "A" from "A. AI Product Development"
        sub_skills = [{"code": s["skill_code"], "name": f"{s['skill_code']}: {s['skill_name']}"} for s in skills]
        category_filters.append({
            "letter": letter,
            "label": label,
            "subSkills": sub_skills,
        })

    # Build taxonomy reference for "View Taxonomy" panel
    taxonomy_ref = []
    for cat in CATEGORY_ORDER:
        skills_in_cat = [s for s in taxonomy if s["category"] == cat]
        label = CATEGORY_LABELS.get(cat, cat)
        entry = {"label": label, "skills": [{
            "code": s["skill_code"],
            "name": s["skill_name"],
            "description": s["description"],
        } for s in skills_in_cat]}
        taxonomy_ref.append(entry)

    js_data = {
        "courses": courses,
        "categories": category_filters,
        "skillLookup": skill_lookup,
        "taxonomy": taxonomy_ref,
        "allTools": all_tools,
    }

    html = generate_html(js_data)
    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / "index.html"
    output_path.write_text(html)
    print(f"Generated {output_path}")
    print(f"  {len(courses)} courses, {len(skill_lookup)} skills")


def generate_html(data):
    data_json = json.dumps(data, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Maven Courses - PM Skills Map</title>
<style>
*{{ margin:0; padding:0; box-sizing:border-box; }}
body{{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; background:#f9fafb; color:#303145; padding:20px 28px; }}
h1{{ font-size:1.4rem; font-weight:700; margin-bottom:3px; }}
.subtitle{{ color:#696e7b; font-size:0.84rem; margin-bottom:14px; }}

/* Filters */
.filters{{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px; align-items:flex-start; }}
.filter-wrap{{ position:relative; }}
.filter-btn{{
  display:inline-flex; align-items:center; gap:5px;
  padding:4px 10px; border:1px solid #dfe1e6; border-radius:5px;
  background:#fff; font-size:0.8rem; color:#303145; cursor:pointer;
  user-select:none;
}}
.filter-btn:hover{{ background:#f1f3f5; }}
.filter-btn.active{{ border-color:#509ee3; color:#509ee3; }}
.filter-btn svg{{ width:11px; height:11px; fill:currentColor; opacity:0.5; }}
.dropdown-panel{{
  display:none; position:absolute; top:calc(100% + 3px); left:0;
  background:#fff; border:1px solid #dfe1e6; border-radius:7px;
  box-shadow:0 4px 14px rgba(0,0,0,0.12); z-index:100;
  min-width:240px; max-height:320px; overflow-y:auto; padding:3px 0;
}}
.dropdown-panel.open{{ display:block; }}
.dropdown-panel label{{
  display:flex; align-items:center; gap:6px;
  padding:3px 10px; font-size:0.78rem; cursor:pointer;
}}
.dropdown-panel label:hover{{ background:#f1f5f9; }}
.dropdown-panel input[type=checkbox]{{ accent-color:#509ee3; width:13px; height:13px; }}
.dropdown-actions{{
  display:flex; justify-content:space-between; padding:4px 10px;
  border-top:1px solid #eee; margin-top:2px;
}}
.dropdown-actions button{{
  font-size:0.72rem; color:#509ee3; background:none; border:none;
  cursor:pointer; padding:2px 0;
}}
.dropdown-actions button:hover{{ text-decoration:underline; }}
.filter-hint{{
  font-size:0.72rem; color:#8c8fa3; padding:6px 10px 2px;
  font-style:italic;
}}

/* Count */
.count-card{{
  border:1px solid #dfe1e6; border-radius:7px; padding:12px 18px;
  margin-bottom:14px; background:#fff;
}}
.count-card .label{{ font-size:0.8rem; color:#509ee3; font-weight:500; margin-bottom:1px; }}
.count-card .number{{ font-size:2rem; font-weight:700; color:#509ee3; line-height:1.1; }}

/* Table */
.table-card{{
  border:1px solid #dfe1e6; border-radius:7px; background:#fff; overflow:hidden;
}}
.table-card .card-title{{
  padding:10px 14px 6px; font-size:0.9rem; font-weight:600;
}}
table{{ width:100%; border-collapse:collapse; table-layout:fixed; }}
colgroup .col-name{{ width:22%; }}
colgroup .col-topics{{ width:12%; }}
colgroup .col-skills{{ width:22%; }}
colgroup .col-tools{{ width:16%; }}
colgroup .col-syl{{ width:28%; }}
th{{
  text-align:left; padding:4px 8px; font-size:0.7rem; font-weight:500;
  color:#8c8fa3; border-bottom:1px solid #eee; cursor:pointer; white-space:nowrap;
  user-select:none;
}}
th:hover{{ color:#303145; }}
th .sort-arrow{{ font-size:0.55rem; margin-left:2px; opacity:0.35; }}
th.sorted .sort-arrow{{ opacity:1; color:#509ee3; }}
td{{
  padding:6px 8px; border-bottom:1px solid #f0f0f2;
  font-size:0.78rem; vertical-align:middle;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}}
tr{{ cursor:pointer; }}
tr:hover td{{ background:#f4f6f8; }}
a{{ color:#509ee3; text-decoration:none; }}
a:hover{{ text-decoration:underline; }}
.dim{{ color:#b0b3c0; }}

/* Pills */
.pill{{
  display:inline; padding:1px 7px 1px 6px; border-radius:3px;
  font-size:0.68rem; font-weight:500; white-space:nowrap;
  background:#f3f4f6; color:#4b5563;
  border-left:2.5px solid transparent;
}}
.pill-topic{{ border-left-color:#509ee3; }}
.pill-A{{ border-left-color:#d97706; }}
.pill-B{{ border-left-color:#7c3aed; }}
.pill-D{{ border-left-color:#4f46e5; }}
.pill-E{{ border-left-color:#db2777; }}
.pill-tool{{ border-left-color:#059669; }}

/* Match bar */
.match-bar{{
  display:inline-block; height:3px; border-radius:1px; background:#509ee3;
  margin-right:4px; vertical-align:middle; opacity:0.5;
}}

/* Detail panel */
.overlay{{ display:none; position:fixed; inset:0; background:rgba(0,0,0,0.25); z-index:200; }}
.overlay.open{{ display:block; }}
.detail-panel{{
  position:fixed; top:0; right:0; bottom:0; width:540px; max-width:90vw;
  background:#fff; box-shadow:-4px 0 20px rgba(0,0,0,0.12); z-index:201;
  transform:translateX(100%); transition:transform 0.2s ease;
  overflow-y:auto; padding:28px 32px;
}}
.detail-panel.open{{ transform:translateX(0); }}
.detail-close{{
  position:absolute; top:16px; right:20px; background:none; border:none;
  font-size:1.2rem; cursor:pointer; color:#8c8fa3; padding:4px;
}}
.detail-close:hover{{ color:#303145; }}
.detail-panel h2{{ font-size:1.15rem; font-weight:600; margin-bottom:4px; padding-right:32px; }}
.detail-panel .detail-link{{ font-size:0.82rem; color:#509ee3; margin-bottom:16px; display:inline-block; }}
.detail-section{{ margin-bottom:16px; }}
.detail-section .detail-label{{
  font-size:0.7rem; font-weight:600; color:#8c8fa3; text-transform:uppercase;
  letter-spacing:0.04em; margin-bottom:4px;
}}
.detail-section .detail-value{{ font-size:0.85rem; line-height:1.5; }}
.detail-section .pill{{ font-size:0.75rem; margin:2px 4px 2px 0; display:inline-block; padding:3px 9px 3px 7px; }}
.detail-match{{ display:inline-block; width:40px; height:6px; background:#e5e7eb; border-radius:3px; margin-left:6px; vertical-align:middle; overflow:hidden; }}
.detail-match-fill{{ display:block; height:100%; border-radius:3px; background:#509ee3; }}

/* Dropdown separator */
.dropdown-sep{{
  font-size:0.68rem; font-weight:600; color:#8c8fa3; text-transform:uppercase;
  letter-spacing:0.04em; padding:6px 10px 3px; border-top:1px solid #eee; margin-top:2px;
}}

/* Active filter chips */
.active-chips{{
  display:flex; flex-wrap:wrap; gap:6px; align-items:center;
  margin-bottom:12px; min-height:0;
}}
.active-chips:empty{{ display:none; }}
.chip{{
  display:inline-flex; align-items:center; gap:4px;
  padding:3px 8px; border-radius:12px; font-size:0.72rem; font-weight:500;
  background:#eef2ff; color:#3b4ebc; border:1px solid #c7d2fe;
}}
.chip-topics{{ background:#eff6ff; color:#1d4ed8; border-color:#bfdbfe; }}
.chip-A{{ background:#fffbeb; color:#b45309; border-color:#fde68a; }}
.chip-B{{ background:#f5f3ff; color:#6d28d9; border-color:#ddd6fe; }}
.chip-D{{ background:#eef2ff; color:#4338ca; border-color:#c7d2fe; }}
.chip-E{{ background:#fdf2f8; color:#be185d; border-color:#fbcfe8; }}
.chip-tools{{ background:#ecfdf5; color:#047857; border-color:#a7f3d0; }}
.chip-x{{
  background:none; border:none; cursor:pointer; font-size:0.85rem;
  line-height:1; color:inherit; opacity:0.6; padding:0 0 0 2px;
}}
.chip-x:hover{{ opacity:1; }}
.clear-all{{
  font-size:0.72rem; color:#509ee3; cursor:pointer; background:none;
  border:none; padding:2px 4px; margin-left:4px;
}}
.clear-all:hover{{ text-decoration:underline; }}

/* Taxonomy button */
.tax-btn{{
  display:inline-flex; align-items:center; gap:4px;
  padding:4px 12px; border:1px solid #dfe1e6; border-radius:5px;
  background:#fff; font-size:0.78rem; color:#509ee3; cursor:pointer;
  margin-left:10px; vertical-align:middle;
}}
.tax-btn:hover{{ background:#f1f5f9; }}
</style>
</head>
<body>

<h1>Maven Courses - PM Skills Map</h1>
<p class="subtitle">Browse and filter the list of AI/PM Maven courses, organized by topic and skills. <button class="tax-btn" id="taxBtn">View Taxonomy</button></p>

<div class="filters" id="filterBar">
  <div class="filter-wrap">
    <button class="filter-btn" id="btn-topics">Topics
      <svg viewBox="0 0 16 16"><path d="M4.5 6l3.5 4 3.5-4z"/></svg>
    </button>
    <div class="dropdown-panel" id="dd-topics"></div>
  </div>
  <div class="filter-wrap">
    <button class="filter-btn" id="btn-category">Skill Category
      <svg viewBox="0 0 16 16"><path d="M4.5 6l3.5 4 3.5-4z"/></svg>
    </button>
    <div class="dropdown-panel" id="dd-category"></div>
  </div>
  <div class="filter-wrap" id="wrap-sub" style="display:none">
    <button class="filter-btn" id="btn-sub">Sub-skills
      <svg viewBox="0 0 16 16"><path d="M4.5 6l3.5 4 3.5-4z"/></svg>
    </button>
    <div class="dropdown-panel" id="dd-sub"></div>
  </div>
  <div class="filter-wrap">
    <button class="filter-btn" id="btn-tools">Tools
      <svg viewBox="0 0 16 16"><path d="M4.5 6l3.5 4 3.5-4z"/></svg>
    </button>
    <div class="dropdown-panel" id="dd-tools"></div>
  </div>
</div>

<div class="active-chips" id="activeChips"></div>

<div class="count-card">
  <div class="label">Total Courses Matching Current View</div>
  <div class="number" id="courseCount">208</div>
</div>

<div class="table-card">
  <div class="card-title">Courses by Topic and Skill</div>
  <table>
    <colgroup>
      <col class="col-name"><col class="col-topics"><col class="col-skills"><col class="col-tools"><col class="col-syl">
    </colgroup>
    <thead>
      <tr>
        <th data-col="name">course_name <span class="sort-arrow">&#x2195;</span></th>
        <th data-col="topics">topics <span class="sort-arrow">&#x2195;</span></th>
        <th data-col="skills">skills <span class="sort-arrow">&#x2195;</span></th>
        <th data-col="tools">tools <span class="sort-arrow">&#x2195;</span></th>
        <th data-col="syllabus">syllabus_summary</th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>
</div>

<!-- Detail -->
<div class="overlay" id="overlay"></div>
<div class="detail-panel" id="detailPanel">
  <button class="detail-close" id="detailClose">&times;</button>
  <div id="detailContent"></div>
</div>

<!-- Taxonomy panel -->
<div class="overlay" id="taxOverlay"></div>
<div class="detail-panel" id="taxPanel">
  <button class="detail-close" id="taxClose">&times;</button>
  <div id="taxContent"></div>
</div>

<script>
const DATA = {data_json};
const SL = DATA.skillLookup;
const CATS = DATA.categories;

// State
let filters = {{ topics: new Set(), categories: new Set(), subs: new Set(), tools: new Set() }};
let sortCol = '_default', sortAsc = false;

// --- Topics dropdown ---
const allTopics = [...new Set(
  DATA.courses.flatMap(c => c.topics ? c.topics.split(',').map(t=>t.trim()).filter(Boolean) : [])
)].sort();

function buildDropdown(panelId, items, filterKey) {{
  const panel = document.getElementById(panelId);
  panel.innerHTML = '';
  items.forEach(item => {{
    const lbl = document.createElement('label');
    const cb = document.createElement('input');
    cb.type='checkbox'; cb.value=item.value;
    if (filters[filterKey].has(item.value)) cb.checked = true;
    cb.addEventListener('change', () => {{
      cb.checked ? filters[filterKey].add(item.value) : filters[filterKey].delete(item.value);
      if (filterKey === 'categories') rebuildSubFilter();
      render();
      updateBtn(filterKey);
    }});
    lbl.appendChild(cb);
    lbl.appendChild(document.createTextNode(' ' + item.label));
    panel.appendChild(lbl);
  }});
  const d = document.createElement('div'); d.className='dropdown-actions';
  d.innerHTML='<button class="sa">Select all</button><button class="ca">Clear</button>';
  panel.appendChild(d);
  d.querySelector('.sa').onclick = e => {{
    e.stopPropagation();
    panel.querySelectorAll('input[type=checkbox]').forEach(cb => {{ cb.checked=true; filters[filterKey].add(cb.value); }});
    if (filterKey === 'categories') rebuildSubFilter();
    render(); updateBtn(filterKey);
  }};
  d.querySelector('.ca').onclick = e => {{
    e.stopPropagation();
    panel.querySelectorAll('input[type=checkbox]').forEach(cb => cb.checked=false);
    filters[filterKey].clear();
    if (filterKey === 'categories') rebuildSubFilter();
    render(); updateBtn(filterKey);
  }};
}}

// Build topics
buildDropdown('dd-topics', allTopics.map(t => ({{value:t, label:t}})), 'topics');

// Build categories
buildDropdown('dd-category', CATS.map(c => ({{value:c.letter, label:c.label}})), 'categories');

// Build standalone tools dropdown
buildDropdown('dd-tools', DATA.allTools.map(t => ({{value:t, label:t}})), 'tools');

// Dynamic sub-filter based on selected categories (skills only, no tools)
function rebuildSubFilter() {{
  filters.subs.clear();
  const wrap = document.getElementById('wrap-sub');
  const panel = document.getElementById('dd-sub');
  panel.innerHTML = '';

  if (filters.categories.size === 0) {{
    wrap.style.display = 'none';
    updateBtn('subs');
    return;
  }}

  wrap.style.display = '';
  const skillItems = [];

  CATS.forEach(cat => {{
    if (!filters.categories.has(cat.letter)) return;
    cat.subSkills.forEach(s => skillItems.push({{value: s.code, label: s.name}}));
  }});

  if (skillItems.length === 0) {{
    wrap.style.display = 'none';
    return;
  }}

  skillItems.forEach(item => {{
    const lbl = document.createElement('label');
    const cb = document.createElement('input');
    cb.type='checkbox'; cb.value=item.value;
    if (filters.subs.has(item.value)) cb.checked = true;
    cb.addEventListener('change', () => {{
      cb.checked ? filters.subs.add(item.value) : filters.subs.delete(item.value);
      render(); updateBtn('subs');
    }});
    lbl.appendChild(cb);
    lbl.appendChild(document.createTextNode(' ' + item.label));
    panel.appendChild(lbl);
  }});

  // Actions
  const d = document.createElement('div'); d.className='dropdown-actions';
  d.innerHTML='<button class="sa">Select all</button><button class="ca">Clear</button>';
  panel.appendChild(d);
  d.querySelector('.sa').onclick = e => {{
    e.stopPropagation();
    panel.querySelectorAll('input[type=checkbox]').forEach(cb => {{ cb.checked=true; filters.subs.add(cb.value); }});
    render(); updateBtn('subs');
  }};
  d.querySelector('.ca').onclick = e => {{
    e.stopPropagation();
    panel.querySelectorAll('input[type=checkbox]').forEach(cb => cb.checked=false);
    filters.subs.clear();
    render(); updateBtn('subs');
  }};
}}

// Dropdown toggles
document.querySelectorAll('.filter-btn').forEach(btn => {{
  btn.addEventListener('click', e => {{
    e.stopPropagation();
    const id = btn.id.replace('btn-','');
    const ddId = 'dd-' + id;
    const p = document.getElementById(ddId);
    const open = p.classList.contains('open');
    document.querySelectorAll('.dropdown-panel').forEach(x => x.classList.remove('open'));
    if (!open) p.classList.add('open');
  }});
}});
document.addEventListener('click', () => document.querySelectorAll('.dropdown-panel').forEach(p => p.classList.remove('open')));
document.querySelectorAll('.dropdown-panel').forEach(p => p.addEventListener('click', e => e.stopPropagation()));

function updateBtn(fk) {{
  const btnMap = {{ topics:'btn-topics', categories:'btn-category', subs:'btn-sub', tools:'btn-tools' }};
  const labelMap = {{ topics:'Topics', categories:'Skill Category', subs:'Sub-skills', tools:'Tools' }};
  const btn = document.getElementById(btnMap[fk]);
  if (!btn) return;
  const n = filters[fk].size;
  const base = labelMap[fk];
  btn.textContent = n > 0 ? `${{base}} (${{n}})` : base;
  const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('viewBox','0 0 16 16');
  svg.style.cssText='width:11px;height:11px;fill:currentColor;opacity:0.5';
  const path = document.createElementNS('http://www.w3.org/2000/svg','path');
  path.setAttribute('d','M4.5 6l3.5 4 3.5-4z');
  svg.appendChild(path); btn.appendChild(svg);
  btn.classList.toggle('active', n > 0);
}}

// Sort
document.querySelectorAll('th[data-col]').forEach(th => {{
  th.addEventListener('click', () => {{
    const col = th.dataset.col;
    if (col === sortCol) sortAsc = !sortAsc;
    else {{ sortCol = col; sortAsc = true; }}
    document.querySelectorAll('th').forEach(t => t.classList.remove('sorted'));
    th.classList.add('sorted');
    render();
  }});
}});

function pc(code) {{ return 'pill-' + code.charAt(0); }}

// Course match score for current filters
function matchScore(c) {{
  let score = 0;
  // Skill match (>50% weight only)
  if (filters.subs.size > 0) {{
    for (const s of c.skills) {{
      if (filters.subs.has(s.code) && s.weight > 0.5) score += s.weight;
    }}
  }} else if (filters.categories.size > 0) {{
    for (const s of c.skills) {{
      if (filters.categories.has(s.code.charAt(0)) && s.weight > 0.5) score += s.weight;
    }}
  }}
  // Tool match (independent)
  if (filters.tools.size > 0) {{
    for (const t of c.tools) {{
      if (filters.tools.has(t)) score += c.toolWeight || 0.3;
    }}
  }}
  return score;
}}

// Detail panel
const overlay = document.getElementById('overlay');
const panel = document.getElementById('detailPanel');
const detailContent = document.getElementById('detailContent');

function openDetail(c) {{
  const topicPills = c.topics
    ? c.topics.split(',').map(t=>t.trim()).filter(Boolean).map(t=>`<span class="pill pill-topic">${{esc(t)}}</span>`).join(' ')
    : '<span class="dim">None</span>';

  const skillRows = c.skills.length > 0
    ? c.skills.map(s => `<div style="margin:3px 0"><span class="pill ${{pc(s.code)}}">${{esc(SL[s.code]||s.code)}}</span><span class="detail-match"><span class="detail-match-fill" style="width:${{Math.round(s.weight*100)}}%"></span></span> <span style="font-size:0.75rem;color:#8c8fa3">${{Math.round(s.weight*100)}}%</span></div>`).join('')
    : '<span class="dim">None</span>';

  const toolPills = c.tools.length > 0
    ? c.tools.map(t => `<span class="pill pill-tool">${{esc(t)}}</span>`).join(' ')
    : '<span class="dim">None</span>';

  const syllabus = c.syllabus
    ? c.syllabus.split(', ').map(s => `<li>${{esc(s)}}</li>`).join('')
    : '<li class="dim">No syllabus data</li>';

  detailContent.innerHTML = `
    <h2>${{esc(c.name)}}</h2>
    ${{c.url ? `<a class="detail-link" href="${{c.url}}" target="_blank">${{esc(c.url)}}</a>` : ''}}
    <div class="detail-section"><div class="detail-label">Topics</div><div class="detail-value">${{topicPills}}</div></div>
    <div class="detail-section"><div class="detail-label">Skills (with match strength)</div><div class="detail-value">${{skillRows}}</div></div>
    <div class="detail-section"><div class="detail-label">Tools</div><div class="detail-value">${{toolPills}}</div></div>
    <div class="detail-section"><div class="detail-label">Syllabus Modules</div><div class="detail-value"><ul style="margin:0;padding-left:18px;line-height:1.7">${{syllabus}}</ul></div></div>
  `;
  overlay.classList.add('open'); panel.classList.add('open');
}}
function closeDetail() {{ overlay.classList.remove('open'); panel.classList.remove('open'); }}
document.getElementById('detailClose').addEventListener('click', closeDetail);
overlay.addEventListener('click', closeDetail);
document.addEventListener('keydown', e => {{ if (e.key==='Escape') {{ closeDetail(); closeTaxonomy(); }} }});

// Taxonomy panel
const taxOverlay = document.getElementById('taxOverlay');
const taxPanel = document.getElementById('taxPanel');
const taxContent = document.getElementById('taxContent');

function openTaxonomy() {{
  let html = '<h2 style="margin-bottom:2px">Skills Taxonomy</h2>';
  html += '<p style="color:#696e7b;font-size:0.82rem;margin-bottom:18px">Categories and skills used to classify Maven courses.</p>';
  DATA.taxonomy.forEach(cat => {{
    html += '<div style="margin-bottom:18px">';
    html += '<div style="font-size:0.95rem;font-weight:600;margin-bottom:6px">' + esc(cat.label) + '</div>';
    if (cat.skills) {{
      cat.skills.forEach(s => {{
        html += '<div style="margin:6px 0 6px 12px"><span style="font-weight:600;font-size:0.84rem">' + esc(s.code + ': ' + s.name) + '</span>';
        html += '<div style="font-size:0.78rem;color:#696e7b;margin-top:1px">' + esc(s.description) + '</div></div>';
      }});
    }}
    html += '</div>';
  }});
  // Show tools section
  html += '<div style="margin-bottom:18px">';
  html += '<div style="font-size:0.95rem;font-weight:600;margin-bottom:6px">Tools</div>';
  html += '<div style="font-size:0.82rem;color:#696e7b;margin-bottom:6px">Specific AI tools taught in courses. Use the Tools filter to find courses by tool.</div>';
  html += '<div>' + DATA.allTools.map(t => '<span class="pill pill-tool" style="display:inline-block;margin:2px 3px">' + esc(t) + '</span>').join('') + '</div>';
  html += '</div>';
  taxContent.innerHTML = html;
  taxOverlay.classList.add('open');
  taxPanel.classList.add('open');
}}

function closeTaxonomy() {{ taxOverlay.classList.remove('open'); taxPanel.classList.remove('open'); }}
document.getElementById('taxBtn').addEventListener('click', openTaxonomy);
document.getElementById('taxClose').addEventListener('click', closeTaxonomy);
taxOverlay.addEventListener('click', closeTaxonomy);

// Active filter chips
function renderChips() {{
  const container = document.getElementById('activeChips');
  container.innerHTML = '';
  const anyActive = filters.topics.size + filters.categories.size + filters.subs.size + filters.tools.size > 0;
  if (!anyActive) return;

  // Topic chips
  filters.topics.forEach(val => {{
    container.appendChild(makeChip(val, val, 'topics', 'chip-topics'));
  }});
  // Category chips
  filters.categories.forEach(letter => {{
    const cat = CATS.find(c => c.letter === letter);
    container.appendChild(makeChip(cat ? cat.label : letter, letter, 'categories', 'chip-' + letter));
  }});
  // Sub-skill chips
  filters.subs.forEach(code => {{
    container.appendChild(makeChip(SL[code] || code, code, 'subs', 'chip-' + code.charAt(0)));
  }});
  // Tool chips
  filters.tools.forEach(val => {{
    container.appendChild(makeChip(val, val, 'tools', 'chip-tools'));
  }});
  // Clear all
  const btn = document.createElement('button');
  btn.className = 'clear-all';
  btn.textContent = 'Clear all';
  btn.addEventListener('click', () => {{
    filters.topics.clear(); filters.categories.clear(); filters.subs.clear(); filters.tools.clear();
    rebuildSubFilter();
    ['topics','categories','subs','tools'].forEach(fk => {{
      updateBtn(fk);
      const panelMap = {{ topics:'dd-topics', categories:'dd-category', subs:'dd-sub', tools:'dd-tools' }};
      const p = document.getElementById(panelMap[fk]);
      if (p) p.querySelectorAll('input[type=checkbox]').forEach(cb => cb.checked = false);
    }});
    render();
  }});
  container.appendChild(btn);
}}

function makeChip(label, value, filterKey, colorClass) {{
  const chip = document.createElement('span');
  chip.className = 'chip ' + colorClass;
  chip.innerHTML = esc(label) + ' ';
  const x = document.createElement('button');
  x.className = 'chip-x';
  x.innerHTML = '&times;';
  x.addEventListener('click', e => {{
    e.stopPropagation();
    filters[filterKey].delete(value);
    if (filterKey === 'categories') rebuildSubFilter();
    // Uncheck the corresponding checkbox
    const panelMap = {{ topics:'dd-topics', categories:'dd-category', subs:'dd-sub', tools:'dd-tools' }};
    const panel = document.getElementById(panelMap[filterKey]);
    if (panel) {{
      panel.querySelectorAll('input[type=checkbox]').forEach(cb => {{
        if (cb.value === value) cb.checked = false;
      }});
    }}
    updateBtn(filterKey);
    render();
  }});
  chip.appendChild(x);
  return chip;
}}

// Render
function render() {{
  renderChips();
  let rows = DATA.courses;

  // Filter: topics
  if (filters.topics.size > 0)
    rows = rows.filter(c => {{
      const ct = c.topics ? c.topics.split(',').map(t=>t.trim()) : [];
      return ct.some(t => filters.topics.has(t));
    }});

  // Filter: categories (>50% weight only)
  if (filters.categories.size > 0)
    rows = rows.filter(c => c.skills.some(s => filters.categories.has(s.code.charAt(0)) && s.weight > 0.5));

  // Filter: sub-skills (>50% weight only)
  if (filters.subs.size > 0)
    rows = rows.filter(c => c.skills.some(s => filters.subs.has(s.code) && s.weight > 0.5));

  // Filter: tools (independent AND filter)
  if (filters.tools.size > 0)
    rows = rows.filter(c => c.tools.some(t => filters.tools.has(t)));

  // Sort: if filters active, sort by match score desc (then revenue). Otherwise revenue.
  const hasFilters = filters.categories.size > 0 || filters.subs.size > 0 || filters.tools.size > 0;

  rows = [...rows];
  if (sortCol === '_default') {{
    if (hasFilters) {{
      rows.sort((a, b) => {{
        const sa = matchScore(a), sb = matchScore(b);
        if (sb !== sa) return sb - sa;
        return b._r - a._r;
      }});
    }} else {{
      rows.sort((a, b) => b._r - a._r);
    }}
  }} else {{
    rows.sort((a, b) => {{
      let va, vb;
      if (sortCol === 'name') {{ va = a.name.toLowerCase(); vb = b.name.toLowerCase(); }}
      else if (sortCol === 'topics') {{ va = a.topics||''; vb = b.topics||''; }}
      else if (sortCol === 'skills') {{ va = a.skills.map(s=>s.code).join(','); vb = b.skills.map(s=>s.code).join(','); }}
      else if (sortCol === 'tools') {{ va = a.tools.join(','); vb = b.tools.join(','); }}
      else {{ va = a.syllabus||''; vb = b.syllabus||''; }}
      if (va < vb) return sortAsc ? -1 : 1;
      if (va > vb) return sortAsc ? 1 : -1;
      return 0;
    }});
  }}

  document.getElementById('courseCount').textContent = rows.length;
  const tbody = document.getElementById('tbody');
  tbody.innerHTML = '';

  rows.forEach(c => {{
    const tr = document.createElement('tr');
    tr.addEventListener('click', e => {{ if (e.target.tagName==='A') return; openDetail(c); }});

    const topicPills = c.topics
      ? c.topics.split(',').map(t=>t.trim()).filter(Boolean).map(t=>`<span class="pill pill-topic">${{esc(t)}}</span>`).join(' ')
      : '<span class="dim">&ndash;</span>';

    const skillPills = c.skills.length > 0
      ? c.skills.map(s=>`<span class="pill ${{pc(s.code)}}">${{esc(SL[s.code]||s.code)}}</span>`).join(' ')
      : '<span class="dim">&ndash;</span>';

    const toolPills = c.tools.length > 0
      ? c.tools.map(t=>`<span class="pill pill-tool">${{esc(t)}}</span>`).join(' ')
      : '<span class="dim">&ndash;</span>';

    const syl = c.syllabus ? esc(c.syllabus) : '<span class="dim">&ndash;</span>';

    tr.innerHTML = `<td>${{esc(c.name)}}</td><td>${{topicPills}}</td><td>${{skillPills}}</td><td>${{toolPills}}</td><td style="color:#696e7b">${{syl}}</td>`;
    tbody.appendChild(tr);
  }});
}}

function esc(s) {{
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}}

render();
</script>
</body>
</html>"""


if __name__ == "__main__":
    main()
