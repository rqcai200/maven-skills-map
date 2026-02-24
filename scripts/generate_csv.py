#!/usr/bin/env python3
"""Generate final CSV output.

Combines course profiles and skill mappings into a CSV.
"""

import csv
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

sys.path.insert(0, str(BASE_DIR / "scripts"))
from generate_site import extract_syllabus_summary

SKILL_NAMES = {
    "A1": "A1: Strategy & Feasibility",
    "A2": "A2: PRD & Specs",
    "A3": "A3: Eval & Iteration",
    "A4": "A4: Shipping & Lifecycle",
    "B1": "B1: Models & Selection",
    "B2": "B2: System Architecture",
    "B3": "B3: Agents & RAG",
    "D1": "D1: Communication & Influence",
    "D2": "D2: Management & Team Dev",
    "E1": "E1: Design",
}


def main():
    with open(DATA_DIR / "course_profiles.json") as f:
        profiles = json.load(f)
    with open(DATA_DIR / "course_skill_mappings.json") as f:
        mappings = json.load(f)

    profile_by_id = {p["course_id"]: p for p in profiles}

    OUTPUT_DIR.mkdir(exist_ok=True)
    csv_path = OUTPUT_DIR / "course_taxonomy_mapping.csv"

    fieldnames = [
        "course_name",
        "course_url",
        "topics",
        "skills",
        "tools",
        "syllabus_summary",
    ]

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for m in sorted(mappings, key=lambda x: x["course_name"]):
            cid = m["course_id"]
            profile = profile_by_id.get(cid, {})
            syllabus = extract_syllabus_summary(profile.get("syllabus_text", ""))

            skill_labels = []
            for s in m.get("skills", []):
                code = s["code"]
                weight = s["weight"]
                name = SKILL_NAMES.get(code, code)
                skill_labels.append(f"{name} ({int(weight*100)}%)")

            tools = m.get("tools", [])

            row = {
                "course_name": m["course_name"],
                "course_url": profile.get("course_url", ""),
                "topics": profile.get("topics", ""),
                "skills": ", ".join(skill_labels),
                "tools": ", ".join(tools),
                "syllabus_summary": syllabus,
            }
            writer.writerow(row)

    print(f"Generated CSV with {len(mappings)} courses -> {csv_path}")
    print(f"Columns: {', '.join(fieldnames)}")


if __name__ == "__main__":
    main()
