"""
Generates Arabic scripts for dark explainer videos using Claude/OpenRouter API.
Call: python -m modules.script_generator --type short --date "2026-05-09" --topic "optional custom topic"
Outputs JSON to stdout with the script text.
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

def generate_script_with_claude(prompt, is_short=True):
    """Send prompt to Claude via OpenRouter and return the response."""
    system_msg = (
        "أنت كاتب نصوص لقناة يوتيوب عربية متخصصة في المحتوى المظلم والتاريخي."
        " تكتب نصوص فيديوهات بالعربية الفصحى المبسطة، بأسلوب مشوق ومثير للفضول."
        "أسلوبك: مكثف بالمعلومات، درامي لكن موضوعي، مع تحليل نفسي عميق للأحداث والشخصيات."
        "لا تستخدم لغة أكاديمية. اجعل النص مناسبًا للمشاهدين الشباب (16-30 سنة)."
        "استخدم جمل قصيرة ومؤثرة. ابدأ بمقدمة صادمة تجذب الانتباه."
        + ("اجعل النص مناسبًا لفيديو قصير (1-2 دقيقة)، من 250-400 كلمة."
           if is_short else
           "اجعل النص مناسبًا لفيديو طويل (12-15 دقيقة)، من 2000-3000 كلمة، مقسمًا إلى 5-6 أقسام."
           "أضف عنوانًا لكل قسم واكتب انتقالاً سلسًا بين الأقسام.")
    )

    headers = {
        "Authorization": f"Bearer {CLAUDE_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5678",
        "X-Title": "YouTube Automation"
    }

    payload = {
        "model": CLAUDE_MODEL,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 4000 if is_short else 8000,
        "temperature": 0.8
    }

    try:
        resp = requests.post(CLAUDE_API_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content.strip()
    except Exception as ex:
        return f"خطأ في توليد النص: {ex}"

def build_short_prompt(event):
    """Build a prompt for a short video about a historical event."""
    event_year = event.get("year", "")
    event_text = event.get("text", "")
    pages = event.get("pages", [])
    title = ""
    extract = ""
    if pages and len(pages) > 0:
        title = pages[0].get("title", "")
        extract = pages[0].get("extract", "")

    return f"""اكتب نصًا لفيديو قصير بالعربية (250-400 كلمة) عن حدث وقع في مثل هذا اليوم من التاريخ.

الحدث: {event_text}
السنة: {event_year}
تفاصيل إضافية: {extract[:500] if extract else title}

المطلوب:
- ابدأ بجملة صادمة تجذب الانتباه
- اشرح الحدث بإيجاز مع التركيز على الجانب النفسي
- اذكر حقائق مدهشة أو مخفية عن الحدث
- استخدم أسلوب "التاريخ المظلم" المشوق
- أنهِ النص بخاتمة قوية تدفع المشاهد للتفكير
- ضع عنوانًا مقترحًا للفيديو بالعربية في أول سطر بين قوسين []

أكتب النص كاملاً من فضلك."""

def build_long_prompt(topic=None):
    """Build a prompt for a long-form video."""
    if topic:
        base_topic = topic
    else:
        base_topic = "واحدة من أكثر الحوادث التاريخية رعبًا وتأثيرًا في نفسية البشر"

    return f"""اكتب نصًا كاملاً لفيديو يوتيوب طويل (12-15 دقيقة، 2000-3000 كلمة) عن "{base_topic}".

قسم النص إلى 6 أقسام مع عناوين لكل قسم:
المقدمة: ابدأ بقصة قصيرة صادمة أو حقيقة مدهشة تجذب المشاهد
الأقسام الرئيسية (4 أقسام): كل قسم يغطي جانبًا مختلفًا من الموضوع
الخاتمة: تحليل نفسي عميق ونهاية قوية

المطلوب:
- لغة عربية فصحى مبسطة، مشوقة وسلسة
- حقائق وأرقام وتواريخ دقيقة
- تحليل نفسي للشخصيات أو الأطراف المعنية
- زوايا مخفية أو غير معروفة عن الحدث
- انتقالات سلسة بين الأقسام
- أضف [(موسيقى)] في الأماكن المناسبة للمؤثرات الصوتية

ضع عنوانًا مقترحًا للفيديو بين قوسين [] في أول سطر."""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["short", "long"], default="short")
    parser.add_argument("--date", default=None)
    parser.add_argument("--topic", default=None)
    args = parser.parse_args()

    if args.type == "short":
        if args.date:
            parts = args.date.split("-")
            month = parts[1].lstrip("0")
            day = parts[2].lstrip("0")
        else:
            from datetime import datetime
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

        result = {
            "type": "short",
            "date": f"{month}-{day}",
            "script": script,
            "event": event,
            "topic": event.get("text", "Historical event")
        }
    else:
        prompt = build_long_prompt(args.topic)
        script = generate_script_with_claude(prompt, is_short=False)

        result = {
            "type": "long",
            "script": script,
            "topic": args.topic or "Deep dive topic"
        }

    print(json.dumps(result, ensure_ascii=False))

def generate_on_this_day_script(date_str=None):
    """Generate a short script about an event on this day in history."""
    if date_str:
        parts = date_str.split("-")
        month = parts[1].lstrip("0") if len(parts) >= 2 else str(datetime.now().month)
        day = parts[2].lstrip("0") if len(parts) >= 3 else str(datetime.now().day)
    else:
        from datetime import datetime as dt
        now = dt.now()
        month = str(now.month)
        day = str(now.day)

    events = get_on_this_day_events(month, day)
    if events and len(events) > 0:
        event = random.choice(events[:20])
    else:
        event = {"year": "Unknown", "text": "حدث تاريخي غامض", "pages": []}

    prompt = build_short_prompt(event)
    script = generate_script_with_claude(prompt, is_short=True)

    return {
        "type": "short",
        "date": f"{month}-{day}",
        "script": script,
        "event": event,
        "topic": event.get("text", "Historical event")
    }


def generate_long_script(topic=None):
    """Generate a long-form script for a deep dive video."""
    prompt = build_long_prompt(topic)
    script = generate_script_with_claude(prompt, is_short=False)

    return {
        "type": "long",
        "script": script,
        "topic": topic or "Deep dive topic"
    }


if __name__ == "__main__":
    main()
