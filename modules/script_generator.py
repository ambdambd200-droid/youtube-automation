"""
Professional script generator for Depths channel.
Generates viral English scripts using free Groq API (Llama 3 70B).
"""

import argparse
import json
import sys
import requests
import random
from datetime import datetime

sys.path.insert(0, ".")
from config import GROQ_API_KEY, GROQ_API_URL, GROQ_MODEL

HISTORICAL_EVENTS_CACHE = {}


SYSTEM_PROMPT = """You are a top-tier scriptwriter for "Depths" — a YouTube channel about dark history, mystery, and psychology.

CORE PRINCIPLES:
1. THE HOOK (first 3 seconds): A shocking, curiosity-grabbing opener that stops the scroll. Start with "Imagine...", "What if I told you...", "Something was happening in...", "They never told you about..."
2. TONE: Conversational, urgent, storytelling. Like a friend telling you something wild at 2am
3. PACING: Short punchy sentences. One idea per line. Every sentence builds tension
4. RETENTION: Use "but here's the thing...", "this is where it gets crazy...", "and then everything changed..."
5. STRUCTURE: Shock → Build curiosity → Reveal information → Twist → Interactive ending
6. EMOTION: Make the viewer feel something — dread, wonder, shock, fascination
7. ENDING: End with an open question like "What would you have done?" or "Doesn't that make you think?"
8. LENGTH: 150-300 words for shorts, 1500-2500 words for long-form
9. VOICE CUES: Add delivery instructions in {curly braces} — {build tension} {pause} {emphasize} {whisper} {slow down}
10. THUMBNAIL: Last line must be 🎬 followed by specific thumbnail description

First line: [Suggested video title]
Last line: 🎬 [thumbnail — scene, colors, text overlay, facial expression if any]"""

LONG_SYSTEM = SYSTEM_PROMPT.replace("150-300 words for shorts", "1500-2500 words for long-form")
LONG_SYSTEM += "\n\nDivide into 5-6 sections with subheadings. Each section reveals a new angle. End sections with mini-cliffhangers."


def generate_script(prompt, is_short=True):
    """Send prompt to Groq's free Llama 3 70B API."""
    system_msg = SYSTEM_PROMPT if is_short else LONG_SYSTEM

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
        "temperature": 0.8
    }

    try:
        resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content.strip()
    except Exception as ex:
        return f"Error generating script: {ex}"


def get_on_this_day_events(month, day):
    """Fetch historical events from Wikipedia for a given date."""
    url = f"https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/events/{month}/{day}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            events = data.get("events", [])
            results = []
            for e in events:
                results.append({
                    "year": e.get("year", ""),
                    "text": e.get("text", ""),
                    "pages": e.get("pages", [])
                })
            return results
    except:
        return []
    return []


def build_short_prompt(event):
    """Build a prompt for a short video about a historical event."""
    event_year = event.get("year", "")
    event_text = event.get("text", "")
    pages = event.get("pages", [])
    extract = ""
    if pages and len(pages) > 0:
        extract = pages[0].get("extract", "")
    if not extract and pages:
        extract = pages[0].get("title", "")

    return f"""Write a gripping short script for "Depths" channel about THIS DAY IN HISTORY.

Event: {event_text}
Year: {event_year}
Context: {(extract or '')[:800]}

Requirements:
- Killer hook in first 3 seconds
- Build curiosity every sentence
- End with a question
- Add voice delivery cues in {{curly braces}}
- End with 🎬 thumbnail description

Write the complete script now."""


def build_long_prompt(topic=None):
    """Build a prompt for a long-form video."""
    if not topic:
        topic = "one of the most disturbing psychological experiments in history"

    return f"""Write a long-form script for "Depths" about: {topic}

Requirements:
- Hook in first 3 seconds
- 5-6 sections with subheadings
- Voice cues in {{curly braces}}
- Deep psychological analysis
- Interactive ending with question
- End with 🎬 thumbnail description

Write the complete script now."""


def extract_title(script):
    """Extract title from [brackets] at start of script."""
    if script and "[" in script and "]" in script:
        return script.split("[")[1].split("]")[0].strip()
    return ""


def extract_thumbnail_note(script):
    """Extract thumbnail description from last line starting with 🎬."""
    if not script:
        return ""
    lines = script.strip().split("\n")
    for line in reversed(lines):
        if "🎬" in line:
            return line.strip()
    return ""


def clean_script_for_tts(script):
    """Remove production instructions from script for clean TTS."""
    import re
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
        now = datetime.now()
        month = str(now.month)
        day = str(now.day)

    events = get_on_this_day_events(month, day)
    if events and len(events) > 0:
        event = random.choice(events[:20])
    else:
        event = {"year": "Unknown", "text": "A mysterious historical event that defies explanation", "pages": []}

    prompt = build_short_prompt(event)
    script = generate_script(prompt, is_short=True)
    title = extract_title(script) or event.get("text", "Mysterious Historical Event")
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
    prompt = build_long_prompt(topic)
    script = generate_script(prompt, is_short=False)
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

    if args.type == "short":
        result = generate_on_this_day_script(args.date)
    else:
        result = generate_long_script(args.topic)

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
