#!/usr/bin/env python3
"""Tighten skill assignments by removing catch-all tags.

This script modifies course_skill_mappings.json in place.
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

with open(DATA_DIR / "course_skill_mappings.json") as f:
    mappings = json.load(f)
with open(DATA_DIR / "course_profiles.json") as f:
    profiles = json.load(f)

prof_by_id = {p["course_id"]: p for p in profiles}

# Topics that indicate PM/AI product work
PM_AI_TOPICS = {
    "AI", "Agentic AI", "Product Strategy", "Product Management Certifications",
    "Working with LLMs", "Developing AI Models", "Machine Learning",
    "AI Evals", "RAG", "System Design", "APIs", "Prototyping",
    "Coding with AI", "A/B Testing", "Experimentation", "Security",
    "Data Analysis", "Optimization", "Project Management", "Growth", "B2B",
    "Productivity", "Strategy", "User Research",
}

# Topics that indicate design/UX
DESIGN_TOPICS = {"Design", "Design Systems", "Design Sprints", "Figma", "UX", "Healthcare"}

# Topics that indicate technical AI content
TECHNICAL_AI_TOPICS = {
    "AI", "Agentic AI", "Working with LLMs", "Developing AI Models",
    "Machine Learning", "AI Evals", "RAG", "System Design", "APIs",
    "Coding with AI", "Prototyping", "Data Analysis", "Programming",
    "Security",
}

# Keywords in course name that indicate eval/testing
EVAL_KEYWORDS = ["eval", "test", "a/b", "experiment", "measure", "metric", "quality", "forecast"]


def get_topics(course_id):
    prof = prof_by_id.get(course_id, {})
    return set(t.strip() for t in prof.get("topics", "").split(",") if t.strip())


def has_skill_at(skills, code, weight):
    return any(s["code"] == code and s["weight"] == weight for s in skills)


def has_any_skill_starting_with_at(skills, prefix, weight):
    return any(s["code"].startswith(prefix) and s["weight"] == weight for s in skills)


def remove_skill(skills, code, weight):
    return [s for s in skills if not (s["code"] == code and s["weight"] == weight)]


removals = []

for m in mappings:
    cid = m["course_id"]
    name = m["course_name"]
    name_lower = name.lower()
    skills = m.get("skills", [])
    topics = get_topics(cid)
    has_pm_topic = bool(topics & PM_AI_TOPICS)
    has_design_topic = bool(topics & DESIGN_TOPICS)
    has_technical_topic = bool(topics & TECHNICAL_AI_TOPICS)

    original_len = len(skills)

    # Rule 1: Remove A1@0.8 from courses that aren't about AI product work
    # Only if they don't have other A-skills at 0.8
    if has_skill_at(skills, "A1", 0.8):
        other_a_08 = any(
            s["code"].startswith("A") and s["code"] != "A1" and s["weight"] == 0.8
            for s in skills
        )
        # Check if name or topics suggest PM/product/AI work
        pm_name_keywords = ["product", "pm ", "ai ", "artificial intelligence", "agent", "llm",
                           "prototype", "eval", "strategy"]
        name_has_pm = any(kw in name_lower for kw in pm_name_keywords)

        if not has_pm_topic and not other_a_08 and not name_has_pm:
            removals.append((cid, name, "A1", 0.8, f"topics={topics}"))
            skills = remove_skill(skills, "A1", 0.8)

    # Rule 2: Remove A1@0.3 from courses that don't have PM/product topics
    # AND don't have any A-skill at 0.8
    if has_skill_at(skills, "A1", 0.3):
        has_a_08 = has_any_skill_starting_with_at(skills, "A", 0.8)
        if not has_pm_topic and not has_a_08:
            # Also check name for PM keywords
            pm_name_keywords = ["product", "pm ", "ai ", "artificial intelligence", "agent", "llm",
                               "prototype", "eval", "strategy", "pricing"]
            name_has_pm = any(kw in name_lower for kw in pm_name_keywords)
            if not name_has_pm:
                removals.append((cid, name, "A1", 0.3, f"topics={topics}"))
                skills = remove_skill(skills, "A1", 0.3)

    # Rule 3: Remove A3@0.3 from courses that aren't about AI evaluation
    if has_skill_at(skills, "A3", 0.3):
        has_a3_08 = has_skill_at(skills, "A3", 0.8)
        name_has_eval = any(kw in name_lower for kw in EVAL_KEYWORDS)
        has_eval_topic = "AI Evals" in topics or "A/B Testing" in topics or "Experimentation" in topics
        if not has_a3_08 and not name_has_eval and not has_eval_topic:
            # Only remove if no strong AI context either
            has_strong_ai = has_pm_topic and has_technical_topic
            if not has_strong_ai:
                removals.append((cid, name, "A3", 0.3, f"topics={topics}"))
                skills = remove_skill(skills, "A3", 0.3)

    # Rule 4: Remove E1@0.3 from courses that don't have design/UX topics
    if has_skill_at(skills, "E1", 0.3):
        has_e1_08 = has_skill_at(skills, "E1", 0.8)
        name_has_design = any(kw in name_lower for kw in ["design", "ux", "figma", "visual", "ui"])
        tools_have_figma = "Figma" in m.get("tools", [])
        if not has_e1_08 and not has_design_topic and not name_has_design and not tools_have_figma:
            removals.append((cid, name, "E1", 0.3, f"topics={topics}"))
            skills = remove_skill(skills, "E1", 0.3)

    # Rule 5: Remove B-skills@0.3 from courses that don't teach technical AI content
    for s in list(skills):
        if s["code"].startswith("B") and s["weight"] == 0.3:
            has_b_08 = has_any_skill_starting_with_at(skills, "B", 0.8)
            if not has_technical_topic and not has_b_08:
                # Check name for technical keywords
                tech_name_kw = ["engineer", "technical", "api", "code", "build", "system",
                               "architect", "rag", "agent", "llm", "model", "ml ", "data"]
                name_has_tech = any(kw in name_lower for kw in tech_name_kw)
                if not name_has_tech:
                    removals.append((cid, name, s["code"], 0.3, f"topics={topics}"))
                    skills = remove_skill(skills, s["code"], 0.3)

    m["skills"] = skills

# Print summary
print(f"Total removals: {len(removals)}")
print()
by_skill = {}
for cid, name, code, weight, reason in removals:
    key = f"{code}@{weight}"
    by_skill.setdefault(key, []).append((cid, name, reason))

for key in sorted(by_skill.keys()):
    items = by_skill[key]
    print(f"--- {key}: {len(items)} removals ---")
    for cid, name, reason in items:
        print(f"  {cid}: {name} | {reason}")
    print()

# Save
with open(DATA_DIR / "course_skill_mappings.json", "w") as f:
    json.dump(mappings, f, indent=2, ensure_ascii=False)
    f.write("\n")

print("Saved updated course_skill_mappings.json")
