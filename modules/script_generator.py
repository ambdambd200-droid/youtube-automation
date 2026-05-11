"""
Professional script generator for الأعماق channel.
Generates viral Arabic scripts with hooks, retention, and engagement.
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
SHORT_SYSTEM = """أنت فريق إنتاج متكامل من 100 متخصص لقناة "الأعماق" — قناة يوتيوب عربية متخصصة في المحتوى التاريخي والنفسي والغامض.

قوانين السكريبت:
1. الهوك (أول 3 ثواني): جملة صادمة تمنع الإغلاق — "تخيل..."، "هل تعلم أن..."، "شيء ما كان يحدث في..."
2. اللغة: عامية عربية مفهمة للجميع (ليست فصحى، ليست عامية ثقيلة) — أسلوب "باختصار" و"لوريستي"
3. الإيقاع: جمل قصيرة ومتقطعة. سطر-سطر. كل جملة تحفة بحد ذاتها
4. تقنيات الاحتفاظ: استخدم "بس انتظر..."، "والجنون إنه..."، "وهون صار شي ما توقعته..."
5. البنية: صدمة ← فضول ← معلومة ← مفاجأة ← نهاية تفاعلية
6. الخاتمة: سؤال مفتوح يدفع المشاهد يكتب تعليق أو يشارك
7. الطول: 250-400 كلمة للشورت (1-2 دقيقة)، 2000-3000 كلمة للطويل (12-15 دقيقة)
8. كل شوية حط تعليمات إلقاء بين قوسين {} — مثل {بصوت عالي} {بهدوء} {بسرعة} {توقف}
9. للشورت: الموضوع = حدث تاريخي حصل في نفس اليوم من السنة
10. للطويل: الموضوع = تحليل عميق لحدث أو شخصية أو ظاهرة

أول سطر: [عنوان الفيديو المقترح]
آخر سطر: 🎬 [وصف الثمبنيل — المشهد والألوان والنص]"""

LONG_SYSTEM = SHORT_SYSTEM.replace("250-400 كلمة للشورت", "2000-3000 كلمة للطويل (12-15 دقيقة)")
LONG_SYSTEM += "\n\nقسم النص إلى 5-6 أقسام بعناوين فرعية. كل قسم يكشف زاوية جديدة."


def generate_script_with_claude(prompt, is_short=True):
    """Send prompt to Claude via OpenRouter with the professional system prompt."""
    system_msg = SHORT_SYSTEM if is_short else LONG_SYSTEM

    headers = {
        "Authorization": f"Bearer {CLAUDE_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5678",
        "X-Title": "الأعماق YouTube Automation"
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
        return f"خطأ في توليد النص: {ex}"


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

    return f"""اكتب سكريبت فيديو قصير لقناة "الأعماق" عن حدث حصل في مثل هذا اليوم من التاريخ.

الحدث: {event_text}
السنة: {event_year}
التفاصيل: {(extract or '')[:600]}

مطلوب:
- هوك قاتل في أول 3 ثواني
- فضول في كل جملة
- خاتمة تسأل المشاهد سؤال
- تعليمات إلقاء {بين قوسين}
- آخر سطر: وصف الثمبنيل

اكتب السكريبت كاملًا الآن."""


def build_long_prompt(topic=None):
    """Build a prompt for a long-form video."""
    if not topic:
        topic = "واحدة من أكثر الحوادث التاريخية رعبًا وتأثيرًا في نفسية البشر"

    return f"""اكتب سكريبت فيديو طويل لقناة "الأعماق" عن: {topic}

مطلوب:
- هوك في أول 3 ثواني
- 5-6 أقسام كل قسم يكشف زاوية جديدة
- تعليمات إلقاء {بين قوسين}
- تحليل نفسي عميق
- خاتمة تفاعلية مع سؤال
- آخر سطر: وصف الثمبنيل

اكتب السكريبت كاملًا الآن."""


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
        if "🎬" in line or "الثمبنيل" in line or "thumbnail" in line.lower():
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
        event = {"year": "Unknown", "text": "حدث تاريخي غامض", "pages": []}

    prompt = build_short_prompt(event)
    script = generate_script_with_claude(prompt, is_short=True)
    title = extract_title(script) or event.get("text", "حدث تاريخي")
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
    title = extract_title(script) or topic or "موضوع تاريخي"
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