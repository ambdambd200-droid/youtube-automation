"""
SEO Generator — creates optimized titles, descriptions, and tags for YouTube Shorts.
Tailored to each content type (World Cup vs Movie).
"""
import json
import os
import sys
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DEFAULT_TAGS, CHANNEL_NAME


# ── Title Templates ─────────────────────────────────────────

WORLDCUP_TITLES = [
    "⚽ THIS MOMENT from World Cup 2026",
    "World Cup 2026: INSANE Moment",
    "World Cup 2026: You Won't Believe This",
    "⚽ Controversial Moment in World Cup 2026",
    "World Cup 2026: Pure Brilliance",
    "World Cup 2026: The Crowd Went CRAZY",
    "World Cup 2026: UNREAL Skill",
    "World Cup 2026: Did You Catch This?",
    "⚽ World Cup 2026 - Best Moment",
    "World Cup 2026: The Stadium ERUPTED",
    "World Cup 2026: Controversial Call",
    "World Cup 2026: Absolute CINEMA",
    "World Cup 2026: HEARTBREAK",
    "World Cup 2026: JOY",
    "World Cup 2026 - One of the Best Moments",
]

MOVIE_TITLES = [
    "🎬 This Scene is PERFECTION",
    "🎬 One of the Best Scenes in Cinema",
    "🎬 Cinema at its Finest",
    "🎬 This Scene Lives Rent Free in My Head",
    "🎬 Absolute Cinema Moment",
    "🎬 They Don't Make Movies Like This Anymore",
    "🎬 This Scene is Iconic",
    "🎬 Pure Cinematic Brilliance",
    "🎬 A Masterpiece of a Scene",
    "🎬 This Movie Scene Changed Everything",
    "🎬 You've Seen This Scene Before",
    "🎬 One of Cinema's Greatest Moments",
    "🎬 This Scene is Peak Cinema",
    "🎬 Unforgettable Movie Moment",
    "🎬 This Scene is Art",
]

# ── Description Templates ───────────────────────────────────

WORLDCUP_DESCRIPTION = """⚽ World Cup 2026 — a moment you have to see.

Natural sound. No music. Just the moment.

━━━━━━━━━━━━━━━━━━━━━━
🎬 New clips every day on VARY
🌍 Movies • Sports • Internet
━━━━━━━━━━━━━━━━━━━━━━

#WorldCup2026 #Football #Soccer #Shorts"""

MOVIE_DESCRIPTION = """🎬 A scene worth watching again.

Natural sound. No music. Just cinema.

━━━━━━━━━━━━━━━━━━━━━━
🎬 New clips every day on VARY
🌍 Movies • Sports • Internet
━━━━━━━━━━━━━━━━━━━━━━

#MovieScenes #Cinema #Shorts #Film"

# ── Tags ────────────────────────────────────────────────────

WORLDCUP_TAGS = [
    "World Cup 2026", "FIFA World Cup", "soccer", "football",
    "world cup moments", "viral world cup", "sports shorts",
    "world cup highlight", "football shorts",
]

MOVIE_TAGS = [
    "movie scene", "cinema", "film", "movie moment",
    "iconic scene", "best movie scenes", "cinematic",
    "film scene", "movie shorts", "classic scene",
]


def truncate_title(title, max_chars=100):
    """Truncate a title to fit YouTube's limit."""
    if len(title) <= max_chars:
        return title
    return title[:max_chars-3] + "..."


def generate_metadata(source_title, content_type, source_url=None):
    """Generate full SEO metadata for a video.

    Args:
        source_title: Title of the source video/content
        content_type: "worldcup_2026" or "movie"
        source_url: Original source URL (optional)

    Returns:
        Dict with title, description, tags
    """
    # Generate title
    if content_type == "worldcup_2026":
        title_template = random.choice(WORLDCUP_TITLES)
        title = title_template
        # Sometimes append the source title
        if source_title and random.random() < 0.4:
            short_source = source_title[:40].replace("World Cup", "").strip()
            if short_source:
                title = f"{title} - {short_source}"
    else:
        title_template = random.choice(MOVIE_TITLES)
        title = title_template
        # Sometimes append the source title
        if source_title and random.random() < 0.4:
            short_source = source_title[:40].strip()
            if short_source:
                title = f"{title} - {short_source}"

    # Generate description
    if content_type == "worldcup_2026":
        description = WORLDCUP_DESCRIPTION
        if source_title:
            description = f"Source: {source_title}\n\n" + description
    else:
        description = MOVIE_DESCRIPTION
        if source_title:
            description = f"Scene from: {source_title}\n\n" + description

    # Add source URL if provided
    if source_url:
        description = f"Original: {source_url}\n\n" + description

    # Add channel signature
    description += (
        f"\n\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔔 Subscribe to VARY for daily clips\n"
        f"👍 Like if you enjoyed this\n"
        f"💬 What should we feature next?\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"#VARY #DailyClips"
    )

    # Generate tags
    base_tags = list(DEFAULT_TAGS)
    if content_type == "worldcup_2026":
        base_tags.extend(WORLDCUP_TAGS)
    else:
        base_tags.extend(MOVIE_TAGS)

    if source_title:
        # Add some words from the source title as tags
        for word in source_title.split()[:5]:
            word = word.strip(",.!?-:;\"'()[]{}")
            if word and len(word) > 3 and word not in base_tags:
                base_tags.append(word)

    # Remove duplicates while preserving order
    seen = set()
    tags = []
    for tag in base_tags:
        tag_lower = tag.lower()
        if tag_lower not in seen:
            seen.add(tag_lower)
            tags.append(tag)

    return {
        "title": truncate_title(title),
        "description": description,
        "tags": tags,
    }


if __name__ == "__main__":
    import sys
    ct = sys.argv[1] if len(sys.argv) > 1 else "movie"
    title = sys.argv[2] if len(sys.argv) > 2 else ""
    result = generate_metadata(title, ct)
    print(json.dumps(result, indent=2, ensure_ascii=False))
