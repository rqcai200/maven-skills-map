#!/usr/bin/env python3
"""Step 1: Ingest & structure data.

1a. Raw courses already fetched from Metabase (data/raw_courses.json)
1b. Aggregate syllabus per course → data/course_profiles.json
1c. Parse taxonomy markdown → data/taxonomy.json
"""

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def aggregate_course_profiles(raw_path: Path) -> list[dict]:
    """Group rows by COURSE_ID and concatenate syllabus text."""
    with open(raw_path) as f:
        rows = json.load(f)

    courses: dict[int, dict] = {}
    for row in rows:
        cid = row["COURSE_ID"]
        if cid not in courses:
            courses[cid] = {
                "course_id": cid,
                "course_name": row["COURSE_NAME"],
                "course_url": row["COURSE_URL"],
                "course_slug": row["COURSE_SLUG"],
                "topics": row.get("TOPICS") or "",
                "syllabus_parts": [],
            }
        title = row.get("ITEM_TITLE") or ""
        content = row.get("CONTENT_PLAINTEXT") or ""
        if title or content:
            courses[cid]["syllabus_parts"].append(f"### {title}\n{content}")

    profiles = []
    for c in courses.values():
        profiles.append({
            "course_id": c["course_id"],
            "course_name": c["course_name"],
            "course_url": c["course_url"],
            "course_slug": c["course_slug"],
            "topics": c["topics"],
            "syllabus_text": "\n\n".join(c["syllabus_parts"]),
        })

    return sorted(profiles, key=lambda x: x["course_id"])


def parse_taxonomy(md_path: Path) -> list[dict]:
    """Parse the taxonomy markdown into structured skills."""
    text = md_path.read_text()

    # Split by category headers (# A. ..., # B. ..., etc.)
    category_pattern = re.compile(r"^# ([A-D])\. (.+)$", re.MULTILINE)
    skill_pattern = re.compile(r"^## ([A-D]\d)\. (.+)$", re.MULTILINE)

    # Find all categories
    categories = {}
    for m in category_pattern.finditer(text):
        categories[m.group(1)] = m.group(2).strip()

    # Find all skills
    skills = []
    skill_matches = list(skill_pattern.finditer(text))
    for i, m in enumerate(skill_matches):
        code = m.group(1)
        name = m.group(2).strip()
        cat_letter = code[0]

        # Extract description: text between this skill header and the next
        start = m.end()
        end = skill_matches[i + 1].start() if i + 1 < len(skill_matches) else len(text)
        section = text[start:end].strip()

        # First paragraph is the description
        paragraphs = section.split("\n\n")
        description = paragraphs[0].strip() if paragraphs else ""

        # Extract example topics from bullet points
        example_topics = []
        for line in section.split("\n"):
            line = line.strip()
            if line.startswith("- ") or line.startswith("* "):
                example_topics.append(line[2:].strip())

        skills.append({
            "skill_code": code,
            "skill_name": name,
            "category": categories.get(cat_letter, ""),
            "description": description,
            "example_topics": example_topics,
        })

    return skills


def main():
    raw_path = DATA_DIR / "raw_courses.json"
    if not raw_path.exists():
        print(f"ERROR: {raw_path} not found. Fetch from Metabase first.")
        return

    # 1b. Aggregate course profiles
    profiles = aggregate_course_profiles(raw_path)
    profiles_path = DATA_DIR / "course_profiles.json"
    with open(profiles_path, "w") as f:
        json.dump(profiles, f, indent=2)
    print(f"Generated {len(profiles)} course profiles → {profiles_path}")

    # 1c. Parse taxonomy
    taxonomy_path = BASE_DIR / "ai_pm_skills_taxonomy.md"
    skills = parse_taxonomy(taxonomy_path)
    taxonomy_out = DATA_DIR / "taxonomy.json"
    with open(taxonomy_out, "w") as f:
        json.dump(skills, f, indent=2)
    print(f"Parsed {len(skills)} taxonomy skills → {taxonomy_out}")

    # Summary
    for s in skills:
        print(f"  {s['skill_code']}: {s['skill_name']}")


if __name__ == "__main__":
    main()
