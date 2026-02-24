#!/usr/bin/env python3
"""Step 2: AI-powered skill mapping using Claude API.

For each course, sends its syllabus + taxonomy to Claude and gets back
primary_skills, secondary_skills, and reasoning.

Uses claude-sonnet-4-6 for cost efficiency.
Requires ANTHROPIC_API_KEY environment variable.
"""

import json
import os
import sys
import time
from pathlib import Path

import anthropic
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

SKILL_CODES = [
    "A1", "A2", "A3", "A4", "A5",
    "B1", "B2", "B3", "B4", "B5",
    "C1", "C2", "C3", "C4", "C5",
    "D1", "D2", "D3", "D4", "D5",
]


class SkillMapping(BaseModel):
    primary_skills: list[str]
    secondary_skills: list[str]
    reasoning: str


def build_taxonomy_reference(taxonomy: list[dict]) -> str:
    """Build a compact taxonomy reference for the prompt."""
    lines = []
    for s in taxonomy:
        topics = "; ".join(s["example_topics"][:5]) if s["example_topics"] else ""
        lines.append(f"**{s['skill_code']}. {s['skill_name']}** — {s['description']}")
        if topics:
            lines.append(f"  Topics: {topics}")
    return "\n".join(lines)


def map_course(client: anthropic.Anthropic, course: dict, taxonomy_ref: str) -> dict:
    """Map a single course to taxonomy skills."""
    # Truncate syllabus to avoid excessive tokens
    syllabus = course["syllabus_text"][:15000]

    prompt = f"""You are an expert at analyzing course curricula and mapping them to a skills taxonomy.

## Taxonomy
{taxonomy_ref}

## Course: {course['course_name']}
Topics: {course['topics']}

### Syllabus Content
{syllabus}

## Task
Analyze the course syllabus above and map it to the taxonomy skills.

Return a JSON object with:
- "primary_skills": list of skill codes (e.g., ["A1", "B3"]) that are clearly and substantially covered in the course
- "secondary_skills": list of skill codes that are touched on but not a primary focus
- "reasoning": brief explanation (2-3 sentences) of why you assigned these skills

Rules:
- Only use valid skill codes: {', '.join(SKILL_CODES)}
- A skill should be "primary" only if the course dedicates significant content to it
- A skill should be "secondary" if it's mentioned or lightly covered
- It's fine for a course to have 0 primary or 0 secondary skills if the content doesn't match
- Be conservative — only assign skills where there's clear evidence in the syllabus"""

    response = client.messages.parse(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
        output_format=SkillMapping,
    )

    result = response.parsed_output
    return {
        "course_id": course["course_id"],
        "course_name": course["course_name"],
        "primary_skills": [s for s in result.primary_skills if s in SKILL_CODES],
        "secondary_skills": [s for s in result.secondary_skills if s in SKILL_CODES],
        "reasoning": result.reasoning,
    }


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.")
        sys.exit(1)

    profiles_path = DATA_DIR / "course_profiles.json"
    taxonomy_path = DATA_DIR / "taxonomy.json"

    with open(profiles_path) as f:
        courses = json.load(f)
    with open(taxonomy_path) as f:
        taxonomy = json.load(f)

    taxonomy_ref = build_taxonomy_reference(taxonomy)
    client = anthropic.Anthropic()

    # Load existing mappings to support resume
    mappings_path = DATA_DIR / "course_skill_mappings.json"
    existing_mappings = {}
    if mappings_path.exists():
        with open(mappings_path) as f:
            for m in json.load(f):
                existing_mappings[m["course_id"]] = m

    mappings = list(existing_mappings.values())
    mapped_ids = set(existing_mappings.keys())

    remaining = [c for c in courses if c["course_id"] not in mapped_ids]
    total = len(courses)
    done = len(mapped_ids)

    print(f"Total courses: {total}, already mapped: {done}, remaining: {len(remaining)}")

    for i, course in enumerate(remaining):
        print(f"[{done + i + 1}/{total}] Mapping: {course['course_name'][:60]}...")
        try:
            result = map_course(client, course, taxonomy_ref)
            mappings.append(result)
            print(f"  Primary: {result['primary_skills']}, Secondary: {result['secondary_skills']}")

            # Save after each course for resume support
            with open(mappings_path, "w") as f:
                json.dump(mappings, f, indent=2)

        except anthropic.RateLimitError:
            print("  Rate limited, waiting 60s...")
            time.sleep(60)
            # Retry
            result = map_course(client, course, taxonomy_ref)
            mappings.append(result)
            with open(mappings_path, "w") as f:
                json.dump(mappings, f, indent=2)

        except Exception as e:
            print(f"  ERROR: {e}")
            mappings.append({
                "course_id": course["course_id"],
                "course_name": course["course_name"],
                "primary_skills": [],
                "secondary_skills": [],
                "reasoning": f"Error: {e}",
            })

    # Final save
    with open(mappings_path, "w") as f:
        json.dump(mappings, f, indent=2)
    print(f"\nDone! {len(mappings)} course mappings saved to {mappings_path}")


if __name__ == "__main__":
    main()
