"""
Content Selector — randomly picks today's content type (World Cup or Movie).
Tracks history in a JSON log to prevent repeating the same scene/topic.
"""
import json
import os
import sys
import random
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LOG_DIR, CONTENT_WEIGHTS, WORLDCUP_KEYWORDS, MOVIE_KEYWORDS

HISTORY_FILE = os.path.join(LOG_DIR, "content_history.json")
USED_SCENES_FILE = os.path.join(LOG_DIR, "used_scenes.json")


def load_history():
    """Load content history from JSON log."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"last_30_days": [], "total_count": 0}


def save_history(entry):
    """Append an entry to content history."""
    history = load_history()
    history.setdefault("last_30_days", []).append(entry)
    history["total_count"] = history.get("total_count", 0) + 1
    # Keep only last 90 entries
    if len(history["last_30_days"]) > 90:
        history["last_30_days"] = history["last_30_days"][-90:]
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def load_used_scenes():
    """Load used scenes/matches to avoid repeats."""
    if os.path.exists(USED_SCENES_FILE):
        try:
            with open(USED_SCENES_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"movie_scenes": [], "worldcup_matches": []}


def save_used_scene(content_type, identifier):
    """Mark a scene/match as used so it won't be repeated."""
    used = load_used_scenes()
    key = "movie_scenes" if content_type == "movie" else "worldcup_matches"
    used.setdefault(key, []).append({
        "identifier": identifier,
        "date_used": datetime.now().isoformat()
    })
    # Keep last 500 entries
    if len(used[key]) > 500:
        used[key] = used[key][-500:]
    with open(USED_SCENES_FILE, "w") as f:
        json.dump(used, f, indent=2)


def is_scene_used(content_type, identifier):
    """Check if a scene/match has been used before."""
    used = load_used_scenes()
    key = "movie_scenes" if content_type == "movie" else "worldcup_matches"
    for entry in used.get(key, []):
        if entry["identifier"] == identifier:
            return True
    return False


def select_content_type():
    """Randomly select content type based on weights, with variety enforcement."""
    history = load_history()
    last_30 = history.get("last_30_days", [])

    # Check last 5 days to avoid streaks
    last_5_types = [h.get("type") for h in last_30[-5:]]

    weights = dict(CONTENT_WEIGHTS)

    # If we've had 3+ of same type in last 5, reduce its weight
    for ct in weights:
        streak = last_5_types.count(ct)
        if streak >= 3:
            weights[ct] = max(0.1, weights[ct] * 0.5)

    # Normalize weights
    total = sum(weights.values())
    weights = {k: v / total for k, v in weights.items()}

    # Weighted random choice
    r = random.random()
    cumulative = 0
    for ct, weight in weights.items():
        cumulative += weight
        if r <= cumulative:
            return ct

    return "movie"  # fallback


def generate_search_query(content_type):
    """Generate a search query for the selected content type."""
    if content_type == "worldcup_2026":
        # Pick a random search keyword for World Cup
        kw = random.choice(WORLDCUP_KEYWORDS)

        # Add variety: sometimes specify a region or team
        regions = ["", "USA", "Argentina", "Brazil", "France", "Germany",
                    "England", "Spain", "Portugal", "Netherlands", "Morocco"]
        if random.random() < 0.3:
            team = random.choice(regions)
            kw = f"{kw} {team}"

        return {
            "type": "worldcup_2026",
            "search_query": kw,
            "description": f"World Cup 2026 - {kw}",
        }

    else:  # movie
        # Pick a random movie keyword
        kw = random.choice(MOVIE_KEYWORDS)

        # Add variety: sometimes specify a genre
        genres = ["", "action", "drama", "comedy", "thriller", "sci-fi",
                   "romance", "horror", "animated", "classic", "award winning"]
        if random.random() < 0.3:
            genre = random.choice(genres)
            kw = f"{genre} {kw}"

        return {
            "type": "movie",
            "search_query": kw,
            "description": f"Movie Scene - {kw}",
        }


def select_today_content():
    """Main entry point — selects today's content type and search query."""
    content_type = select_content_type()

    # If same as yesterday, re-roll once (extra variety)
    history = load_history()
    if history.get("last_30_days"):
        last_type = history["last_30_days"][-1].get("type")
        if last_type == content_type and random.random() < 0.5:
            content_type = "movie" if content_type == "worldcup_2026" else "worldcup_2026"

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
