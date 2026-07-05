# -*- coding: utf-8 -*-
"""
SEO Generator — creates optimized titles, descriptions, and tags for YouTube Shorts.
Tailored to each content type (football, movie, or series).
"""
import json
import os
import sys
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DEFAULT_TAGS


# ── Title Templates ─────────────────────────────────────────
# Three tiers: POETIC (counter-algorithmic, restrained),
#                BALANCED (default current style),
#                DIRECT (conventional YouTube hook)

POETIC_FOOTBALL_TITLES = [
    "the moment before the roar",
    "a second. then everything.",
    "they didn't see it coming.",
    "stillness. then chaos.",
    "the ball. the net. the silence.",
    "this is where it turned.",
    "watch the eyes.",
    "one touch. one breath.",
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
FOOTBALL_TITLES = [
    "Insane Skills 🔥",
    "Unbelievable Goal 🚀",
    "This Touch Was Something Else",
    "Pure Football Genius",
    "How Did He Do That?",
    "Pure Class",
    "Different Gravy",
    "Skills That DEFY Physics",
    "Unreal Footwork",
    "The Ball Was Attached to His Foot",
    "This Pass Is Art",
    "Cold. Calm. Calculated.",
    "Ball Don't Lie",
    "Pure Talent",
    "Different Level",
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
DIRECT_FOOTBALL_TITLES = [
    "Best Football Moment",
    "Crazy Football Skill!",
    "Best Football Clip",
    "Football Highlight",
    "Unreal Football Moment",
]

DIRECT_MOVIE_TITLES = [
    "Best Movie Scene",
    "Iconic Movie Scene",
    "Cinematic Masterpiece",
    "Best Scene in Cinema",
    "Unforgettable Movie Moment",
]

POETIC_SERIES_TITLES = [
    "watch the eyes.",
    "the silence between the words.",
    "this frame. nothing else.",
    "they didn't rehearse this.",
    "the camera didn't blink.",
    "one take. one lifetime.",
    "hear the silence.",
    "before the line. after the look.",
    "the moment the actor forgot to act.",
    "not a scene. a confession.",
    "the frame holds its breath.",
    "this is where it peaks.",
    "the showrunner left it in.",
    "watch the background.",
    "the pause that carries the weight.",
]

SERIES_TITLES = [
    "This Scene is PERFECTION",
    "One of the Best Scenes in Television",
    "TV at its Finest",
    "This Scene Lives Rent Free in My Head",
    "Absolute Cinema Moment",
    "They Don't Make TV Like This Anymore",
    "This Scene is Iconic",
    "Pure Brilliance",
    "A Masterpiece of Television",
    "This TV Scene Changed Everything",
    "You've Seen This Scene Before",
    "One of TV's Greatest Moments",
    "This Scene is Peak Television",
    "Unforgettable TV Moment",
    "This Scene is Art",
]

DIRECT_SERIES_TITLES = [
    "Best TV Scene",
    "Iconic TV Moment",
    "Television Masterpiece",
    "Best Scene in TV",
    "Unforgettable Series Moment",
]

# ── Description Templates ───────────────────────────────────

FOOTBALL_DESCRIPTION_TEMPLATE = """{source_line}

━━━━━━━━━━━━━━━━━━━━━━
⚽ VARY — daily football moments
━━━━━━━━━━━━━━━━━━━━━━

#Football #Soccer #Highlights #VARY #Shorts"""

MOVIE_DESCRIPTION_TEMPLATE = """{source_line}

━━━━━━━━━━━━━━━━━━━━━━
🎬 VARY — daily movie moments
━━━━━━━━━━━━━━━━━━━━━━

#MovieScene #Cinema #Film #VARY #Shorts"""

SERIES_DESCRIPTION_TEMPLATE = """{source_line}

━━━━━━━━━━━━━━━━━━━━━━
📺 VARY — daily series moments
━━━━━━━━━━━━━━━━━━━━━━

#SeriesScene #TV #Series #VARY #Shorts"""

# ── Tags ────────────────────────────────────────────────────

FOOTBALL_TAGS = [
    "football", "soccer", "football skills",
    "football moments", "viral football", "sports shorts",
    "football highlight", "football shorts",
]

MOVIE_TAGS = [
    "movie scene", "cinema", "film", "movie moment",
    "iconic scene", "best movie scenes", "cinematic",
    "film scene", "movie shorts", "classic scene",
]

SERIES_TAGS = [
    "tv series", "series scene", "television", "TV moment",
    "iconic scene", "best series scenes", "TV show",
    "series scene", "tv shorts", "classic scene",
]


def truncate_title(title, max_chars=100):
    """Truncate a title to fit YouTube's limit."""
    if len(title) <= max_chars:
        return title
    return title[:max_chars-3] + "..."


# ── Blueprint Section 1.1: Tri-Part Title Structure ────────

EMOTIONAL_ANCHORS_FOOTBALL = [
    "Pure Shock", "Unbelievable Silence", "The Moment Everything Changed",
    "Absolute Madness", "Pure Insanity", "Heart Stopped",
    "Silence Before the Roar", "Perfect Timing", "Time Stood Still",
    "Raw Emotion", "Pure Magic", "Unreal Scenes",
]

EMOTIONAL_ANCHORS_MOVIE = [
    "Pure Shock", "The Silence Between Words", "Absolute Cinema",
    "Chills Every Time", "Pure Brilliance", "Watch His Eyes",
    "The Moment He Knew", "Masterpiece Frame", "Unforgettable Seconds",
    "Raw Emotion", "This Frame", "Perfect Acting",
]

EMOTIONAL_ANCHORS_SERIES = [
    "Pure Shock", "The Silence Between Words", "Absolute Television",
    "Chills Every Time", "Pure Brilliance", "Watch Their Eyes",
    "The Moment She Knew", "Perfect Writing", "Unforgettable Seconds",
    "Raw Emotion", "This Scene", "Perfect Direction",
]

CURIOSITY_GAPS_FOOTBALL = [
    "Wait for the save", "He didn't see it", "Watch his reaction",
    "The keeper had no chance", "Look at the deflection",
    "Notice the spin", "Wait for the slow-mo",
    "He knew instantly", "The silence says it all",
]

CURIOSITY_GAPS_MOVIE = [
    "Wait for the line", "He didn't see it", "Watch his eyes",
    "The camera didn't blink", "Notice the background",
    "One take wonder", "The director left this in",
    "Look at his face", "The silence says it all",
]

CURIOSITY_GAPS_SERIES = [
    "Wait for the reveal", "They didn't see it", "Watch her eyes",
    "The writers knew", "Notice the detail",
    "This took 20 takes", "The showrunner kept this",
    "Look at her reaction", "The silence says it all",
]


def build_tripart_title(content_type, source_title=None):
    """Blueprint Section 1.1: Tri-Part Title Structure.
    Segment A: Emotional Anchor (0-25 chars) — visceral feeling
    Segment B: Contextual Keyword (25-45 chars) — SEO source material
    Segment C: Curiosity Gap (45-60 chars) — forces the click

    Returns a title <= 60 chars, fragmented, punchy, no punctuation at end.
    """
    if content_type == "football":
        anchor = random.choice(EMOTIONAL_ANCHORS_FOOTBALL)
        gap = random.choice(CURIOSITY_GAPS_FOOTBALL)
    elif content_type == "series":
        anchor = random.choice(EMOTIONAL_ANCHORS_SERIES)
        gap = random.choice(CURIOSITY_GAPS_SERIES)
    else:
        anchor = random.choice(EMOTIONAL_ANCHORS_MOVIE)
        gap = random.choice(CURIOSITY_GAPS_MOVIE)

    # Extract short source name for Segment B
    source_segment = ""
    if source_title:
        short = source_title[:30].strip()
        if short:
            source_segment = f" — {short}"

    title = f"{anchor}{source_segment[:20]} — {gap}"

    # Enforce <= 60 chars with Title Case
    if len(title) > 60:
        title = title[:57].rstrip() + ""

    # Title Case first letter of every major word
    words = title.split()
    title = " ".join(
        w[0].upper() + w[1:] if w and w[0].islower() else w
        for w in words
    )

    return title.strip()


def build_short_description(source_title, content_type, source_url=None):
    """Short description for daily shorts — concise, high-density.
    YouTube Shorts descriptions work best at 1-3 lines.
    """
    if content_type == "football":
        hashtags = "#Shorts #Football #WorldCup2026"
    elif content_type == "series":
        hashtags = "#Shorts #TVSeries #RawEmotion"
    else:
        hashtags = "#Shorts #Cinema #RawEmotion"

    source_line = source_title or "This moment"
    parts = [source_line, "", f"VARY — daily clips", hashtags]

    if source_url:
        parts.insert(0, f"Source: {source_url}")

    return "\n".join(parts)


def generate_metadata(source_title, content_type, source_url=None):
    """Generate full SEO metadata for a video.

    Args:
        source_title: Title of the source video/content
        content_type: "football", "movie", or "series"
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

    # Select title lists based on content type
    if content_type == "football":
        poetic_titles = POETIC_FOOTBALL_TITLES
        direct_titles = DIRECT_FOOTBALL_TITLES
        balanced_titles = FOOTBALL_TITLES
    elif content_type == "series":
        poetic_titles = POETIC_SERIES_TITLES
        direct_titles = DIRECT_SERIES_TITLES
        balanced_titles = SERIES_TITLES
    else:
        poetic_titles = POETIC_MOVIE_TITLES
        direct_titles = DIRECT_MOVIE_TITLES
        balanced_titles = MOVIE_TITLES

    # Blueprint Section 1: Use Tri-Part Title Structure
    title = build_tripart_title(content_type, source_title)

    # Short description for shorts
    description = build_short_description(source_title, content_type, source_url)

    # Generate tags
    base_tags = list(DEFAULT_TAGS)
    if content_type == "football":
        base_tags.extend(FOOTBALL_TAGS)
    elif content_type == "series":
        base_tags.extend(SERIES_TAGS)
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


# ── Weekly Video SEO ───────────────────────────────────────

WEEKLY_MOVIE_TITLES = [
    "The Story of [movie] — A Film Analysis",
    "Understanding [movie]: A Cinematic Journey",
    "Why [movie] is a Masterpiece of Cinema",
    "[movie]: The Story Behind the Masterpiece",
    "What Makes [movie] Unforgettable",
    "The Art of [movie] — A Deep Dive",
    "[movie] Explained: Themes and Symbolism",
    "The Genius of [movie]",
    "[movie] — A Story of [theme]",
    "How [movie] Changed Cinema Forever",
]

WEEKLY_THEMES = [
    "Ambition", "Love", "Loss", "Redemption", "Hope",
    "Sacrifice", "Identity", "Truth", "Courage", "Fate",
]

WEEKLY_MOVIE_TAGS = [
    "movie analysis", "film analysis", "movie explained",
    "cinema", "film criticism", "movie breakdown",
    "film essay", "movie review", "story explained",
    "weekly video", "VARY weekly", "film storytelling",
    "movie story", "masterpiece", "cinematic analysis",
]

WEEKLY_DESCRIPTION_TEMPLATE = """{movie} — A Story of {theme}

A cinematic journey through one of film's greatest achievements.
Every frame. Every silence. Every choice.

━━━━━━━━━━━━━━━━━━━━━━━
🎬 VARY Weekly — every Sunday
👍 one story at a time
━━━━━━━━━━━━━━━━━━━━━━━
#VARY #FilmAnalysis #{movie_tag}"""


def generate_weekly_metadata(source_title, source_url=None):
    """Generate SEO metadata for weekly videos (movie story analysis).

    Weekly videos have different SEO than daily shorts:
    - Longer, essay-style titles
    - Film analysis description
    - Different tags (no shorts tags)
    - No daily posting schedule in description

    Args:
        source_title: Title of the source video/content
        source_url: Original source URL (optional)

    Returns:
        Dict with title, description, tags
    """
    # Extract movie name from title (remove common prefixes/suffixes)
    movie_name = source_title
    for prefix in ["Why ", "The Story of ", "Understanding ", "Analysis of ",
                    "The Genius of ", "How ", "What Makes "]:
        if movie_name.startswith(prefix):
            movie_name = movie_name[len(prefix):]
            break
    for suffix in [" is a masterpiece", " is brilliant", " works", " changed cinema"]:
        if suffix in movie_name:
            movie_name = movie_name[:movie_name.index(suffix)]
            break
    # Clean up
    movie_name = movie_name.strip().strip(":;-,")
    if not movie_name:
        movie_name = source_title[:30]

    # Pick a theme and title template
    theme = random.choice(WEEKLY_THEMES)
    title_template = random.choice(WEEKLY_MOVIE_TITLES)

    title = title_template.replace("[movie]", movie_name).replace("[theme]", theme)

    # Generate movie tag from movie name
    movie_tag = movie_name.split(":")[0].split("(")[0].strip().replace(" ", "")[:20]

    # Build description
    description = WEEKLY_DESCRIPTION_TEMPLATE.format(
        movie=movie_name,
        theme=theme,
        movie_tag=movie_tag,
    )

    if source_url:
        description = f"Original footage: {source_url}\n\n" + description

    # Build tags
    tags = list(WEEKLY_MOVIE_TAGS)
    # Add movie-specific tags
    for word in movie_name.split()[:5]:
        word = word.strip(",.!?-:;\"'()[]{}")
        if word and len(word) > 3 and word.lower() not in [t.lower() for t in tags]:
            tags.append(word)

    return {
        "title": truncate_title(title, max_chars=100),
        "description": description,
        "tags": tags,
    }


if __name__ == "__main__":
    import sys
    ct = sys.argv[1] if len(sys.argv) > 1 else "movie"
    title = sys.argv[2] if len(sys.argv) > 2 else ""
    if ct == "weekly":
        result = generate_weekly_metadata(title)
    else:
        result = generate_metadata(title, ct)
    print(json.dumps(result, indent=2, ensure_ascii=False))
