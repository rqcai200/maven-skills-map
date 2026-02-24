#!/usr/bin/env python3
"""Validate tool assignments against course syllabus text.

For each course with tools, checks each tool name against the syllabus_text
from course_profiles.json using tiered keyword matching. Removes tools not
actually mentioned in the syllabus.
"""

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Vibe-coding tools referenced by assign_a5.py
VIBE_TOOLS = {"Cursor", "Lovable", "Bolt", "v0", "Replit", "Windsurf", "Devin"}


def _has_nearby(text: str, anchor: str, context_words: list[str], window: int = 200) -> bool:
    """Check if any context_word appears within `window` chars of `anchor` in text."""
    for m in re.finditer(re.escape(anchor), text):
        start = max(0, m.start() - window)
        end = min(len(text), m.end() + window)
        snippet = text[start:end].lower()
        if any(w.lower() in snippet for w in context_words):
            return True
    return False


# --- Tier 1: safe case-insensitive match ---
TIER1_TOOLS = {
    "ChatGPT", "OpenAI API", "Claude Code", "Lovable", "Figma",
    "LangChain", "LangGraph", "n8n", "Replit", "Zapier",
    "Custom GPTs", "NotebookLM", "DALL-E", "Hugging Face",
    "Pinecone", "Google Colab", "Notion AI", "Stable Diffusion",
    "Midjourney", "GPT-4",
}


def tool_found_in(tool: str, text: str) -> bool:
    """Return True if the tool is genuinely referenced in the syllabus text."""
    if not text:
        return False

    # --- Tier 1: simple case-insensitive ---
    if tool in TIER1_TOOLS:
        return tool.lower() in text.lower()

    # --- Tier 2: ambiguous tools with stricter patterns ---

    if tool == "Claude":
        # Skip if "Claude Code" already covers it
        if "claude code" in text.lower():
            return True
        # Capitalized "Claude" near AI context words
        if re.search(r'\bClaude\b', text):
            ai_context = ["Anthropic", "Sonnet", "Opus", "Haiku", "API", "model", "AI", "LLM", "chatbot"]
            if _has_nearby(text, "Claude", ai_context, window=150):
                return True
        return False

    if tool == "Cursor":
        # Must be capitalized, exclude UI cursor references
        if not re.search(r'\bCursor\b', text):
            return False
        # Exclude "cursor position", "text cursor", "mouse cursor"
        if re.search(r'(?:cursor\s+position|text\s+cursor|mouse\s+cursor)', text, re.I):
            # Check if there's ALSO a capitalized standalone usage
            cleaned = re.sub(r'(?:cursor\s+position|text\s+cursor|mouse\s+cursor)', '', text, flags=re.I)
            return bool(re.search(r'\bCursor\b', cleaned))
        return True

    if tool == "Bolt":
        if not re.search(r'\bBolt\b', text):
            return False
        # Exclude "bolt on", "nuts and bolts"
        if re.search(r'(?:bolt\s+on|nuts\s+and\s+bolts)', text, re.I):
            cleaned = re.sub(r'(?:bolt\s+on|nuts\s+and\s+bolts)', '', text, flags=re.I)
            return bool(re.search(r'\bBolt\b', cleaned))
        return True

    if tool == "v0":
        # Strict: word boundary before, space/punctuation after. Not inside version strings.
        # Match "v0" but not "v0.2", "v0.1", etc.
        if re.search(r'(?:^|\s)v0(?:\s|[,;.!?)]|$)', text):
            # Exclude if only appears as version strings
            all_v0 = list(re.finditer(r'v0', text))
            for m in all_v0:
                after = text[m.end():m.end() + 2]
                if not re.match(r'\.\d', after):
                    return True
        return False

    if tool == "Make":
        # Only match specific patterns
        patterns = [
            r'Make\.com',
            r'Make\s+automation',
            r'Make\s+scenario',
            r'Make\s+integration',
        ]
        for p in patterns:
            if re.search(p, text, re.I):
                return True
        # "Make" in an explicit tool list context
        if re.search(r'(?:tools?|platform|software|app)\b.{0,30}\bMake\b', text, re.I):
            return True
        return False

    if tool == "Gemini":
        return bool(re.search(r'\bGemini\b', text))

    if tool == "Copilot":
        return bool(re.search(r'(?:GitHub|Microsoft)?\s*Copilot\b', text))

    if tool == "Perplexity":
        return bool(re.search(r'\bPerplexity\b', text))

    if tool == "Windsurf":
        if not re.search(r'\bWindsurf\b', text):
            return False
        # Exclude "windsurfing"
        if re.search(r'\bwindsurfing\b', text, re.I):
            cleaned = re.sub(r'\bwindsurfing\b', '', text, flags=re.I)
            return bool(re.search(r'\bWindsurf\b', cleaned))
        return True

    if tool == "Devin":
        if not re.search(r'\bDevin\b', text):
            return False
        context = ["AI", "agent", "coding", "engineer", "tool", "software"]
        return _has_nearby(text, "Devin", context, window=150)

    if tool == "Relay":
        if re.search(r'Relay\.app', text):
            return True
        if re.search(r'\bRelay\b', text):
            context = ["app", "automation", "workflow"]
            return _has_nearby(text, "Relay", context, window=150)
        return False

    # Fallback: case-insensitive substring match
    return tool.lower() in text.lower()


def main():
    mappings_path = DATA_DIR / "course_skill_mappings.json"
    profiles_path = DATA_DIR / "course_profiles.json"

    with open(mappings_path) as f:
        mappings = json.load(f)
    with open(profiles_path) as f:
        profiles = json.load(f)

    profile_by_id = {p["course_id"]: p for p in profiles}

    total_removed = 0
    tool_removal_counts: dict[str, int] = {}
    courses_modified = 0

    for course in mappings:
        if not course.get("tools"):
            continue

        cid = course["course_id"]
        profile = profile_by_id.get(cid, {})
        syllabus = profile.get("syllabus_text", "")

        kept = []
        removed = []
        for tool in course["tools"]:
            if tool_found_in(tool, syllabus):
                kept.append(tool)
            else:
                removed.append(tool)
                tool_removal_counts[tool] = tool_removal_counts.get(tool, 0) + 1

        if removed:
            courses_modified += 1
            total_removed += len(removed)
            print(f"  [{cid}] {course['course_name'][:60]}")
            print(f"    Removed: {removed}")
            if kept:
                print(f"    Kept:    {kept}")

        course["tools"] = kept
        if not kept:
            course["tool_weight"] = 0

    # Save
    with open(mappings_path, "w") as f:
        json.dump(mappings, f, indent=2)

    print(f"\n--- Tool Validation Summary ---")
    print(f"Courses modified: {courses_modified}")
    print(f"Total tools removed: {total_removed}")
    print(f"\nRemovals by tool:")
    for tool, count in sorted(tool_removal_counts.items(), key=lambda x: -x[1]):
        print(f"  {tool}: {count}")


if __name__ == "__main__":
    main()
