# -*- coding: utf-8 -*-
"""
SEO Generator — creates optimized titles, descriptions, and tags for YouTube Shorts.
Tailored to each content type (World Cup vs Movie).
"""
import json
import os
import sys
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DEFAULT_TAGS, is_world_cup_active


# ── Title Templates ─────────────────────────────────────────
# Three tiers: POETIC (counter-algorithmic, restrained),
#                BALANCED (default current style),
#                DIRECT (conventional YouTube hook)

POETIC_WORLDCUP_TITLES = [
    "the moment before the roar",
    "a second. then everything.",
    "they didn't see it coming.",
    "stillness. then chaos.",
    "the ball. the net. the silence.",
    "this is where it turned.",
    "watch the eyes.",
    "one pass. one breath.",
    "the stadium held its breath.",
    "not a goal. a statement.",
    "between the whistle and the scream.",
    "the frame that changed everything.",
    "nothing after this was the same.",
    "they knew before it happened.",
    "the split second that lasted forever.",
]

POETIC_MOVIE_TITLES = [
    "watch the eyes.",
    "the silence between the words.",
    "this frame. nothing else.",
    "they didn't rehearse this.",
    "the camera didn't blink.",
    "one take. one lifetime.",
    "hear the silence.",
    "before the line. after the look.",
    "the moment the actor forgot to act.",
    "not a scene. a sentence.",
    "the frame holds its breath.",
    "this is where the movie peaks.",
    "the director left it in.",
    "watch the background.",
    "the pause that carries the weight.",
]

# ── Balanced (current style) ─────────────────────────────────
WORLDCUP_TITLES = [
    "THIS MOMENT from World Cup 2026",
    "World Cup 2026: INSANE Moment",
    "World Cup 2026: You Won't Believe This",
    "Controversial Moment in World Cup 2026",
    "World Cup 2026: Pure Brilliance",
    "World Cup 2026: The Crowd Went CRAZY",
    "World Cup 2026: UNREAL Skill",
    "World Cup 2026: Did You Catch This?",
    "World Cup 2026 - Best Moment",
    "World Cup 2026: The Stadium ERUPTED",
    "World Cup 2026: Controversial Call",
    "World Cup 2026: Absolute CINEMA",
    "World Cup 2026: HEARTBREAK",
    "World Cup 2026: JOY",
    "World Cup 2026 - One of the Best Moments",
]

MOVIE_TITLES = [
    "This Scene is PERFECTION",
    "One of the Best Scenes in Cinema",
    "Cinema at its Finest",
    "This Scene Lives Rent Free in My Head",
    "Absolute Cinema Moment",
    "They Don't Make Movies Like This Anymore",
    "This Scene is Iconic",
    "Pure Cinematic Brilliance",
    "A Masterpiece of a Scene",
    "This Movie Scene Changed Everything",
    "You've Seen This Scene Before",
    "One of Cinema's Greatest Moments",
    "This Scene is Peak Cinema",
    "Unforgettable Movie Moment",
    "This Scene is Art",
]

# ── Direct (conventional YouTube style) ─────────────────────
DIRECT_WORLDCUP_TITLES = [
    "World Cup 2026 — Best Moment",
    "World Cup 2026 Crazy Moment!",
    "Best World Cup 2026 Clip",
    "World Cup 2026 Highlight",
    "Unreal World Cup 2026 Moment",
]

DIRECT_MOVIE_TITLES = [
    "Best Movie Scene",
    "Iconic Movie Scene",
    "Cinematic Masterpiece",
    "Best Scene in Cinema",
    "Unforgettable Movie Moment",
]

# ── Description Templates ───────────────────────────────────

# ── Description Templates (minimalist restraint) ────────────

WORLDCUP_DESCRIPTION = """a moment.

natural sound. no music. one clip.

━━━━━━━━━━━━━━━━━━━━━━━
vary.
07:33 · 17:55 · 22:18 utc
daily.
━━━━━━━━━━━━━━━━━━━━━━━"""

MOVIE_DESCRIPTION = """a frame.

natural sound. no music. one clip.

━━━━━━━━━━━━━━━━━━━━━━━
vary.
07:33 · 17:55 · 22:18 utc
daily.
━━━━━━━━━━━━━━━━━━━━━━━"""

# Description used after the World Cup ends (no football/sports references)
MOVIE_DESCRIPTION_POST_WC = """a frame.

natural sound. no music. one clip.

━━━━━━━━━━━━━━━━━━━━━━━
vary.
07:33 · 17:55 · 22:18 utc
daily.
━━━━━━━━━━━━━━━━━━━━━━━"""

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
    # Determine title style from evolution engine (via public API)
    style = "balanced"
    try:
        from modules.evolution_engine import get_parameter
        evo_style = get_parameter("title_style_preference", "balanced")
        style = evo_style if evo_style in ("poetic", "direct", "balanced") else "balanced"
    except Exception:
        pass

    # Generate title
    if content_type == "worldcup_2026":
        if style == "poetic":
            title_template = random.choice(POETIC_WORLDCUP_TITLES)
        elif style == "direct":
            title_template = random.choice(DIRECT_WORLDCUP_TITLES)
        else:
            title_template = random.choice(WORLDCUP_TITLES)

        title = title_template.capitalize() if not title_template[0].islower() else title_template

        # Sometimes append the source title (for balanced/direct styles)
        if source_title and random.random() < 0.4 and style != "poetic":
            short_source = source_title[:40].replace("World Cup", "").strip()
            if short_source:
                title = f"{title} - {short_source}"
    else:
        if style == "poetic":
            title_template = random.choice(POETIC_MOVIE_TITLES)
        elif style == "direct":
            title_template = random.choice(DIRECT_MOVIE_TITLES)
        else:
            title_template = random.choice(MOVIE_TITLES)

        title = title_template.capitalize() if not title_template[0].islower() else title_template

        # Sometimes append the source title (for balanced/direct styles)
        if source_title and random.random() < 0.4 and style != "poetic":
            short_source = source_title[:40].strip()
            if short_source:
                title = f"{title} - {short_source}"

    # Generate description — use post-WC descriptions if WC is over
    wc_active = is_world_cup_active()

    if content_type == "worldcup_2026":
        description = WORLDCUP_DESCRIPTION
        if source_title:
            description = f"Source: {source_title}\n\n" + description
    else:
        description = MOVIE_DESCRIPTION_POST_WC if not wc_active else MOVIE_DESCRIPTION
        if source_title:
            description = f"Scene from: {source_title}\n\n" + description

    # Add source URL if provided
    if source_url:
        description = f"Original: {source_url}\n\n" + description

    # Add channel signature (minimalist)
    if style == "poetic":
        description += (
            f"\n\n━━━━━━━━━━━━━━━━━━━━━━\n"
            f"vary.\n"
            f"07:33 · 17:55 · 22:18 utc\n"
            f"\n"
            f"not content. moments.\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
    else:
        description += (
            f"\n\n━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔔 VARY — three times daily\n"
            f"👍 one clip at a time\n"
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
