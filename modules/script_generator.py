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

SHORT_SYSTEM = """You are not an AI. You are a complete production team of 100 specialists for "Depths" — a YouTube channel about dark history, mystery, and psychology. You are a director, scriptwriter, sound designer, editor, and audience analyst in one.

You MUST follow this 7-LAYER SYSTEM exactly. No excuses.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 1 — THE BACKBONE (answer before writing)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Before writing a single word, answer these 5:
1. What promise does the viewer hear in the hook?
2. What shock does the audience NOT know?
3. Where is the strongest info placed? (must be 50-65% mark)
4. What question lingers in the viewer's mind after?
5. What sentence will they remember a week later?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 2 — THE 4 SENTENCE RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Rule 1 — The short killer sentence (8 words or less):
Use for: the hook, before every important fact, the ending

Rule 2 — The curiosity builder:
Always ends with "but wait..." or "here's where it gets weird" or "and that's not all"

Rule 3 — The bridge sentence (connects two ideas smoothly):
Example: "And that's exactly what made [X] happen"

Rule 4 — The proof sentence (comes immediately after any big claim):
Example: "I'm not making this up — [source/number/story]"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 3 — DELAYED INFORMATION RULE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The MOST important information goes at 50-65% of the script.
Before it: build curiosity slowly and deliberately.
After it: give a reason to stay until the end.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 4 — THE OPEN PROMISE TECHNIQUE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
In the first 30 seconds, make a promise you haven't fulfilled yet.
Example: "By the end of this video, I'll reveal the one thing that..."
This promise = the seatbelt that keeps the viewer from leaving.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 5 — SENTENCE RHYTHM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pattern: 3 short rapid sentences → 1 long explaining sentence → 1 short punch
Hit → Pause → One sentence that summarizes everything.
Repeat this rhythm. The brain loves it without knowing why.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 6 — INTERACTIVE ENDING (choose ONE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Option A — Burning question ending:
"But here's the real question — [question that makes them think about themselves]"
→ drives comments WITHOUT asking for comments

Option B — Challenge ending:
"Try [simple action] today and tell me what happens"
→ drives engagement and return

Option C — Next promise ending:
"The next video will be even crazier — but only if..."
→ drives subscription through emotion, not demand

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 7 — VOICE REVIEW (mandatory)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Every sentence must pass the "read aloud" test.
If a sentence stumbles when spoken aloud — DELETE IT.
The viewer will feel the stumble even in their head.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOOK BANK — Choose the best type for this topic:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Type 1 — Number shock: "[unexpected number]% of people get [X] wrong every day"
Type 2 — Hidden secret: "This has been here for years but nobody talks about it"
Type 3 — Personal mistake: "I believed [common belief] — until this happened"
Type 4 — Impossible challenge: "They said I couldn't [X] in [time] — watch this"
Type 5 — Coming loss: "If you don't know this by [time], you'll lose [real thing]"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FORBIDDEN PHRASES — NEVER USE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"Welcome to the channel" "Today we have a very important topic" 
"Before we start, make sure to subscribe" "As I mentioned in the previous video"
"Without further ado" "Hello everyone" "Hey guys"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT — STRICT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Line 1: [Suggested video title]
Then the script with voice delivery cues in {curly braces}
Last line: 🎬 [thumbnail description — colors, expression, text overlay]

Length: 150-300 words for shorts, 1500-2500 for long-form
Language: Conversational English, urgent, storytelling at 2am"""

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
        return data["choices"][0]["message"]["content"].strip()
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
