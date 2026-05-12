"""
Internal script engine for Depths channel.
Implements the full 7-layer production system.
Zero external dependencies — pure Groq + internal prompt engineering.
"""

import argparse
import json
import sys
import requests
import random
import re
from datetime import datetime

sys.path.insert(0, ".")
from config import GROQ_API_KEY, GROQ_API_URL, GROQ_MODEL

HISTORICAL_EVENTS_CACHE = {}


# ═══════════════════════════════════════════════════════════════
# 7-LAYER SYSTEM PROMPT — Full production manifesto encoded
# ═══════════════════════════════════════════════════════════════

SHORT_SYSTEM = """You are a top scriptwriter for "Depths" — a YouTube channel about dark history, mystery, and psychology. You write scripts that keep viewers watching.

RULES — Internalize them, do NOT output them:
- Hook in first 3 seconds: number shock, hidden secret, or coming loss
- Short punchy sentences. 8 words or less for killer lines.
- Build curiosity every sentence. Use "but wait..." / "here's where it gets weird"
- Key information at 50-65% of script
- Open promise in first 30 seconds: "By the end I'll reveal..."
- Rhythm: 3 short rapid sentences → 1 long → 1 short punch
- End with a question or challenge
- Delete any sentence that stumbles when spoken aloud
- Voice delivery cues in {curly braces} like {pause} {emphasize} {whisper}

HOOK OPTIONS (pick one, don't list them):
1. Number shock — "[number]% of people get [X] wrong"
2. Hidden secret — "Nobody talks about this — here's why"
3. Coming loss — "If you don't know this, you'll regret it"

FORBIDDEN: "Welcome" "Today we have" "Subscribe before" "As I mentioned" "Hey guys"

OUTPUT FORMAT — ONLY THIS, NOTHING ELSE:
Line 1: [Video title]
Then the script
Last line: 🎬 [thumbnail description]

Length: 150-300 words. Conversational English."""

LONG_SYSTEM = SHORT_SYSTEM.replace("150-300 words for shorts", "1500-2500 words for long-form")
LONG_SYSTEM += "\n\nDivide into 5-6 sections with subheadings. End each section with a mini-cliffhanger."


def generate_script(prompt, is_short=True):
    """Send prompt to Groq's free Llama 3 70B API."""
    system_msg = SHORT_SYSTEM if is_short else LONG_SYSTEM

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 2000 if is_short else 6000,
        "temperature": 0.75
    }

    try:
        resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()

        # Strip any planning/thinking before the script starts
        # Script always starts with [title]
        if "[" in content:
            content = content[content.index("["):]

        return content
    except Exception as ex:
        return f"Error: {ex}"


def get_on_this_day_events(month, day):
    """Fetch historical events from Wikipedia for a given date."""
    url = f"https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/events/{month}/{day}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            events = resp.json().get("events", [])
            return [{
                "year": e.get("year", ""),
                "text": e.get("text", ""),
                "pages": e.get("pages", [])
            } for e in events]
    except:
        pass
    return []


def build_short_prompt(event):
    """Build a prompt for a short video about a historical event."""
    event_year = event.get("year", "")
    event_text = event.get("text", "")
    pages = event.get("pages", [])
    extract = ""
    if pages and len(pages) > 0:
        extract = pages[0].get("extract", "") or pages[0].get("title", "")

    return f"""Write a script for "Depths" about THIS DAY IN HISTORY.

Event: {event_text}
Year: {event_year}
Context: {(extract or '')[:800]}

Follow the 7-layer system exactly.
Choose the best hook type for this event.
End with 🎬 thumbnail description.

Write the complete script now."""


def build_long_prompt(topic=None):
    """Build a prompt for a long-form video."""
    if not topic:
        topic = "the most disturbing psychological event in human history"
    return f"""Write a long-form script for "Depths" about: {topic}

Follow the 7-layer system exactly.
5-6 sections with subheadings.
End with 🎬 thumbnail description.

Write the complete script now."""


def extract_title(script):
    """Extract title from [brackets] at start of script."""
    if script and "[" in script and "]" in script:
        return script.split("[")[1].split("]")[0].strip()
    return ""


def extract_thumbnail_note(script):
    if not script:
        return ""
    for line in reversed(script.strip().split("\n")):
        if "🎬" in line:
            return line.strip()
    return ""


def clean_script_for_tts(script):
    """Remove production instructions from script for clean TTS."""
    lines = []
    for line in script.split("\n"):
        if "🎬" in line:
            continue
        cleaned = re.sub(r'\{[^}]*\}', '', line)
        if cleaned.strip():
            lines.append(cleaned.strip())
    return "\n".join(lines)


def generate_on_this_day_script(date_str=None):
    """Generate a professional short script about an event on this day."""
    if date_str:
        parts = date_str.split("-")
        month = parts[1].lstrip("0") if len(parts) >= 2 else str(datetime.now().month)
        day = parts[2].lstrip("0") if len(parts) >= 3 else str(datetime.now().day)
    else:
        month = str(datetime.now().month)
        day = str(datetime.now().day)

    events = get_on_this_day_events(month, day)
    event = random.choice(events[:20]) if events else {
        "year": "Unknown", "text": "A mysterious historical event", "pages": []
    }

    script = generate_script(build_short_prompt(event), is_short=True)
    title = extract_title(script) or event.get("text", "Historical Event")
    thumb_note = extract_thumbnail_note(script)

    return {
        "type": "short",
        "date": f"{month}-{day}",
        "script": script,
        "script_clean": clean_script_for_tts(script),
        "event": event,
        "topic": title,
        "thumbnail_hint": thumb_note
    }


def generate_long_script(topic=None):
    """Generate a professional long-form script."""
    script = generate_script(build_long_prompt(topic), is_short=False)
    title = extract_title(script) or topic or "Dark History Deep Dive"
    thumb_note = extract_thumbnail_note(script)

    return {
        "type": "long",
        "script": script,
        "script_clean": clean_script_for_tts(script),
        "topic": title,
        "thumbnail_hint": thumb_note
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["short", "long"], default="short")
    parser.add_argument("--date", default=None)
    parser.add_argument("--topic", default=None)
    args = parser.parse_args()

    result = (generate_on_this_day_script if args.type == "short" else generate_long_script)(
        args.date if args.type == "short" else args.topic
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
