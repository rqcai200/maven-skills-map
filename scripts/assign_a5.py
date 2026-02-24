#!/usr/bin/env python3
"""Assign A5 (Prototyping & Vibe Coding) skill to courses.

Rule-based assignment using existing signals — no API call needed.
Reads course_profiles.json and course_skill_mappings.json, then assigns A5.
"""

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

VIBE_TOOLS = {"Cursor", "Lovable", "Bolt", "v0", "Replit", "Windsurf", "Devin"}

# Course name patterns that indicate prototyping/vibe coding focus
NAME_PATTERNS = [
    r"prototype",
    r"prototyping",
    r"vibe\s*cod",
    r"builder\s+bootcamp",
    r"build\s+and\s+ship",
    r"build\s*&\s*ship",
]
NAME_RE = re.compile("|".join(NAME_PATTERNS), re.I)

# Topics that indicate primary A5
PRIMARY_TOPICS = {"Prototyping", "Coding with AI"}


def count_vibe_tools(course_mapping: dict) -> int:
    """Count how many vibe-coding tools are assigned to this course."""
    return sum(1 for t in course_mapping.get("tools", []) if t in VIBE_TOOLS)


def has_a5(course_mapping: dict) -> bool:
    """Check if A5 is already assigned."""
    return any(s["code"] == "A5" for s in course_mapping.get("skills", []))


def get_topics(profile: dict) -> set[str]:
    """Parse topics string into a set."""
    return {t.strip() for t in (profile.get("topics", "") or "").split(",") if t.strip()}


def main():
    with open(DATA_DIR / "course_skill_mappings.json") as f:
        mappings = json.load(f)
    with open(DATA_DIR / "course_profiles.json") as f:
        profiles = json.load(f)

    profile_by_id = {p["course_id"]: p for p in profiles}
    mapping_by_id = {m["course_id"]: m for m in mappings}

    primary_assignments = []
    secondary_assignments = []

    for m in mappings:
        if has_a5(m):
            continue

        cid = m["course_id"]
        profile = profile_by_id.get(cid, {})
        topics = get_topics(profile)
        name = m.get("course_name", "")
        vibe_count = count_vibe_tools(m)
        tool_weight = m.get("tool_weight", 0)

        is_primary = False

        # Primary: topic is Prototyping or Coding with AI
        if topics & PRIMARY_TOPICS:
            is_primary = True

        # Primary: course name contains prototyping/vibe coding patterns
        if NAME_RE.search(name):
            is_primary = True

        # Primary: 3+ vibe tools with tool_weight=0.8
        if vibe_count >= 3 and tool_weight >= 0.8:
            is_primary = True

        if is_primary:
            m["skills"].append({"code": "A5", "weight": 0.8})
            primary_assignments.append((cid, name, topics, vibe_count))
        elif vibe_count >= 1:
            # Secondary: has 1+ vibe tools but doesn't qualify for primary
            m["skills"].append({"code": "A5", "weight": 0.3})
            secondary_assignments.append((cid, name, topics, vibe_count))

    # Save
    with open(DATA_DIR / "course_skill_mappings.json", "w") as f:
        json.dump(mappings, f, indent=2)

    print("=== A5 Primary Assignments (0.8) ===")
    for cid, name, topics, vc in primary_assignments:
        print(f"  [{cid}] {name[:70]}  topics={topics}  vibe_tools={vc}")
    print(f"\nTotal primary: {len(primary_assignments)}")

    print(f"\n=== A5 Secondary Assignments (0.3) ===")
    for cid, name, topics, vc in secondary_assignments:
        print(f"  [{cid}] {name[:70]}  topics={topics}  vibe_tools={vc}")
    print(f"\nTotal secondary: {len(secondary_assignments)}")
    print(f"\nTotal A5 assignments: {len(primary_assignments) + len(secondary_assignments)}")


if __name__ == "__main__":
    main()
