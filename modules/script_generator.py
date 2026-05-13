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
# 7-LAYER LORISTY-STYLE PROMPT — Full production manifesto
# ═══════════════════════════════════════════════════════════════

SHORT_SYSTEM = """You are a legendary storyteller for "Depths" — a channel inspired by the "Loristy" style of dark mystery, philosophical inquiry, and deep history. You don't just share facts; you weave a dark, cinematic experience.

CORE PHILOSOPHY:
- Mystery & Atmosphere: Every sentence should feel like a whisper in a dark room.
- Psychological Depth: Connect historical events to human nature and fear.
- The "Loristy" Hook: Start with a philosophical or chilling question that challenges the viewer's reality.

RULES — Internalize them, do NOT output them:
- Hook (0-3s): A chilling realization or a question about the nature of existence.
- Pacing: Short, rhythmic, and punchy. Avoid academic language. Use evocative metaphors.
- Build Curiosity: Use "But they didn't know...", "The truth was much darker...", "Imagine a world where..."
- Voice Delivery Cues: Use {pause}, {whisper}, {cold_voice}, {intense} for the narrator.
- Key Insight: Reveal the "Dark Truth" at the 60% mark.
- Ending: Leave the viewer with a lingering thought or a question that haunts them.

FORBIDDEN: "Welcome", "Today", "In this video", "Don't forget to like", "Hey guys". Never break the fourth wall.

OUTPUT FORMAT:
Line 1: [Cinematic Video Title]
The script body with voice cues.
Last line: 🎬 [Cinematic thumbnail description: high contrast, dark atmosphere, one central striking object/figure]

Length: 200-350 words. Dramatic English."""

LONG_SYSTEM = """You are a master of cinematic long-form storytelling for "Depths". Your style is atmospheric, dark, and deeply engaging, mirroring the best of "Loristy".

STRUCTURE:
1. The Hook: A 60-second atmospheric setup that poses a central mystery.
2. The Deep Dive: 5-6 sections that peel back the layers of the story.
3. The Philosophical Pivot: Connect the story to a larger human truth.
4. The Final Chill: A haunting conclusion.

RULES:
- Use subheadings but keep the narrative flow seamless.
- End every section with a mini-cliffhanger or a chilling question.
- Vocabulary: Use words that evoke imagery (shadows, echoes, forgotten, blood-soaked, whispers).
- Rhythm: Alternate between intense rapid-fire sentences and long, descriptive passages.

FORBIDDEN: Standard documentary tropes. This is a cinematic narrative.

OUTPUT FORMAT:
Line 1: [Epic Video Title]
Full script with subheadings and {voice_cues}.
Last line: 🎬 [Epic thumbnail description]

Length: 1800-2500 words. Dramatic English."""


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
        if resp.status_code != 200:
            return f"Error {resp.status_code}: {resp.text[:500]}"
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()

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

    return f"""Write a cinematic "Loristy-style" script for "Depths" about a dark moment in history.

Event: {event_text}
Year: {event_year}
Historical Context: {(extract or '')[:800]}

Your goal: Transform this event into a haunting narrative. Don't just report the facts—explore the shadows behind them.
Focus on the atmosphere, the human cost, and the lingering mystery.

Follow the Loristy-style guidelines exactly.
End with 🎬 thumbnail description.

Write the complete script now."""


def build_long_prompt(topic=None):
    """Build a prompt for a long-form video."""
    if not topic:
        topic = "the most disturbing psychological event in human history"
    return f"""Write an epic, cinematic "Loristy-style" long-form script for "Depths" about: {topic}

Requirements:
- Deep philosophical and psychological exploration.
- Immersive storytelling that feels like a dark documentary.
- Clear subheadings that mark the progression of the mystery.
- Atmospheric voice cues.

Follow the Loristy-style guidelines exactly.
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
