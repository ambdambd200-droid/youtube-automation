"""
Content Selector — randomly picks today's content type (football, movie, or series).
Tracks history in a JSON log to prevent repeating the same scene/topic.
"""
import json
import os
import sys
import random
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LOG_DIR, FOOTBALL_KEYWORDS, MOVIE_KEYWORDS, SERIES_KEYWORDS, CONTENT_WEIGHTS, CONTENT_TYPES

HISTORY_FILE = os.path.join(LOG_DIR, "content_history.json")
USED_SCENES_FILE = os.path.join(LOG_DIR, "used_scenes.json")


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"last_30_days": [], "total_count": 0}


def save_history(entry):
    history = load_history()
    history.setdefault("last_30_days", []).append(entry)
    history["total_count"] = history.get("total_count", 0) + 1
    if len(history["last_30_days"]) > 90:
        history["last_30_days"] = history["last_30_days"][-90:]
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def load_used_scenes():
    if os.path.exists(USED_SCENES_FILE):
        try:
            with open(USED_SCENES_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"movie_scenes": [], "football_matches": [], "series_scenes": []}


def save_used_scene(content_type, identifier):
    used = load_used_scenes()
    key_map = {"football": "football_matches", "movie": "movie_scenes", "series": "series_scenes"}
    key = key_map.get(content_type, "movie_scenes")
    used.setdefault(key, []).append({
        "identifier": identifier,
        "date_used": datetime.now().isoformat()
    })
    if len(used[key]) > 500:
        used[key] = used[key][-500:]
    with open(USED_SCENES_FILE, "w") as f:
        json.dump(used, f, indent=2)


def is_scene_used(content_type, identifier):
    used = load_used_scenes()
    key_map = {"football": "football_matches", "movie": "movie_scenes", "series": "series_scenes"}
    key = key_map.get(content_type, "movie_scenes")
    for entry in used.get(key, []):
        if entry["identifier"] == identifier:
            return True
    return False


def _load_evolution_weights():
    try:
        from modules.evolution_engine import get_evolved_weights
        return get_evolved_weights()
    except Exception:
        return None


def select_content_type():
    """Randomly select content type based on weights, with variety enforcement."""
    history = load_history()
    last_30 = history.get("last_30_days", [])

    evolved = _load_evolution_weights()
    if evolved:
        weights = dict(evolved)
    else:
        weights = dict(CONTENT_WEIGHTS)

    last_5_types = [h.get("type") for h in last_30[-5:]]

    for ct in weights:
        streak = last_5_types.count(ct)
        if streak >= 3:
            weights[ct] = max(0.1, weights[ct] * 0.5)

    total = sum(weights.values())
    weights = {k: v / total for k, v in weights.items()}

    r = random.random()
    cumulative = 0
    for ct, weight in weights.items():
        cumulative += weight
        if r <= cumulative:
            return ct

    return "movie"


def _load_evolved_keywords(content_type):
    try:
        from modules.evolution_engine import get_evolved_keywords
        return get_evolved_keywords(content_type)
    except Exception:
        return None


def generate_search_query(content_type):
    """Generate a search query for the selected content type."""
    if content_type == "football":
        kws = _load_evolved_keywords(content_type) or FOOTBALL_KEYWORDS
        kw = random.choice(kws)

        return {
            "type": "football",
            "search_query": kw,
            "description": f"Football - {kw}",
        }

    elif content_type == "series":
        kws = _load_evolved_keywords(content_type) or SERIES_KEYWORDS
        kw = random.choice(kws)

        return {
            "type": "series",
            "search_query": kw,
            "description": f"TV Series - {kw}",
        }

    else:
        kws = _load_evolved_keywords(content_type) or MOVIE_KEYWORDS
        kw = random.choice(kws)

        return {
            "type": "movie",
            "search_query": kw,
            "description": f"Movie Scene - {kw}",
        }


def select_today_content():
    """Main entry point — selects today's content type and search query."""
    content_type = select_content_type()

    history = load_history()
    if history.get("last_30_days"):
        last_type = history["last_30_days"][-1].get("type")
        if last_type == content_type and random.random() < 0.5:
            others = [t for t in CONTENT_TYPES if t != content_type]
            content_type = random.choice(others)

    query_info = generate_search_query(content_type)

    entry = {
        "type": content_type,
        "search_query": query_info["search_query"],
        "date": datetime.now().isoformat(),
    }
    save_history(entry)

    return query_info


if __name__ == "__main__":
    result = select_today_content()
    print(json.dumps(result, indent=2))
