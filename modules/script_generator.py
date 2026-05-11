"""
Professional script generator for Depths channel.
Generates viral English scripts with hooks, retention, and engagement.
"""

import argparse
import json
import sys
import requests
import random
from datetime import datetime

sys.path.insert(0, ".")
from config import CLAUDE_API_KEY, CLAUDE_API_URL, CLAUDE_MODEL

HISTORICAL_EVENTS_CACHE = {}


# ─────────────────────────────────────────────
# SYSTEM PROMPT — Team of 100 Professionals
# ─────────────────────────────────────────────
SHORT_SYSTEM = """You are a full production team of 100 specialists for "Depths" — a YouTube channel specializing in dark history, mystery, and psychological content.

Script rules:
1. THE HOOK (first 3 seconds): A shocking statement that prevents closing — "Imagine...", "What if I told you...", "Something was happening in...", "They never told you about..."
2. LANGUAGE: Conversational English — short punchy sentences. Write like a narrator telling a campfire story
3. RHYTHM: Short, punchy lines. One sentence per line. Every sentence stands on its own
4. RETENTION: Use "but wait...", "here's where it gets crazy...", "and then something unexpected happened..."
5. STRUCTURE: Shock → Curiosity → Information → Twist → Interactive ending
6. ENDING: Open-ended question that makes the viewer comment or share
7. LENGTH: 150-300 words for shorts (45-60 sec), 1500-2500 words for long-form (10-15 min)
8. VOICE INSTRUCTIONS: Sprinkle delivery cues in {curly braces} — {loud} {whisper} {fast} {pause} {emphasize}
9. For shorts: topic = historical event that happened on this day
10. For long-form: topic = deep analysis of an event, person, or phenomenon

First line: [Suggested video title]
Last line: 🎬 [thumbnail description — scene, colors, text overlay]"""

LONG_SYSTEM = SHORT_SYSTEM.replace("150-300 words for shorts", "1500-2500 words for long-form (10-15 min)")
LONG_SYSTEM += "\n\nDivide the script into 5-6 sections with subheadings. Each section reveals a new angle."


def generate_script_with_claude(prompt, is_short=True):
    """Send prompt to Claude via OpenRouter with the professional system prompt."""
    system_msg = SHORT_SYSTEM if is_short else LONG_SYSTEM

    headers = {
        "Authorization": f"Bearer {CLAUDE_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5678",
        "X-Title": "Depths YouTube Automation"
    }

    payload = {
        "model": CLAUDE_MODEL,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 4000 if is_short else 8000,
        "temperature": 0.85
    }

    try:
        resp = requests.post(CLAUDE_API_URL, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content.strip()
    except Exception as ex:
        return f"Error generating script: {ex}"


def get_on_this_day_events(month, day):
    """Fetch historical events for a given date from Wikipedia API."""
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
    except Exception as ex:
        return [{"year": "Unknown", "text": f"Error fetching events: {ex}"}]
    return []


def build_short_prompt(event):
    """Build a professional prompt for a short video."""
    event_year = event.get("year", "")
    event_text = event.get("text", "")
    pages = event.get("pages", [])
    title = ""
    extract = ""
    if pages and len(pages) > 0:
        title = pages[0].get("title", "")
        extract = pages[0].get("extract", "")
    if not extract and title:
        extract = title

    return f"""Write a short video script for "Depths" channel about an event that happened on this day in history.

Event: {event_text}
Year: {event_year}
Details: {(extract or '')[:600]}

Requirements:
- Killer hook in first 3 seconds
- Curiosity in every sentence
- Ending with a question for the viewer
- Delivery instructions in {{curly braces}}
- Last line: thumbnail description

Write the complete script now."""


def build_long_prompt(topic=None):
    """Build a prompt for a long-form video."""
    if not topic:
        topic = "one of the most terrifying and psychologically impactful events in human history"

    return f"""Write a long-form video script for "Depths" channel about: {topic}

Requirements:
- Hook in first 3 seconds
- 5-6 sections, each revealing a new angle
- Delivery instructions in {{curly braces}}
- Deep psychological analysis
- Interactive ending with a question
- Last line: thumbnail description

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
        if "🎬" in line or "thumbnail" in line.lower():
            return line.strip()
    return ""


def clean_script_for_tts(script):
    """Remove production instructions from script for clean TTS."""
    lines = []
    for line in script.split("\n"):
        # Remove thumbnail line
        if "🎬" in line: continue
        # Remove bracketed instructions but keep text
        cleaned = line
        import re
        cleaned = re.sub(r'\{[^}]*\}', '', cleaned)
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
        event = {"year": "Unknown", "text": "A mysterious historical event", "pages": []}

    prompt = build_short_prompt(event)
    script = generate_script_with_claude(prompt, is_short=True)
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
    prompt = build_long_prompt(topic)
    script = generate_script_with_claude(prompt, is_short=False)
    title = extract_title(script) or topic or "Historical Topic"
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