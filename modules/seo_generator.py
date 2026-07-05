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


def build_rich_description(source_title, content_type, source_url=None):
    """Blueprint Section 1.2: SEO-Optimized Description Matrix.
    Minimum 250 words with structured hierarchy:
      - First 150 chars: Keyword-rich snippet (repeats title core)
      - Narrative Expansion (100 words)
      - Contextual Footer (facts + location)
      - Hashtag Triad
    """
    lines = []

    # First 150 chars — snippet / meta-description
    snippet = f"{source_title[:60] if source_title else 'This moment'} — raw emotion, no music, pure impact."
    lines.append(snippet)
    lines.append("")

    # Narrative Expansion (~200 words for 250+ total)
    if content_type == "football":
        narrative = (
            f"In the world of football, moments like these are why we watch. "
            f"The stadium holds its breath as the play unfolds. Every touch, every step, "
            f"every decision leads to this single frame. The crowd's reaction tells the story — "
            f"from stunned silence to explosive celebration. This is the raw beauty of the sport: "
            f"unscripted, unfiltered, unforgettable. Watch closely and you will see the technique, "
            f"the precision, and the pure athleticism that separates the great from the legendary. "
            f"No commentary needed. No music required. Just the sound of the game breathing. "
            f"This is football at its most honest. What makes this moment special is not just the "
            f"skill involved but the context — the pressure of the match, the stakes for the team, "
            f"the hopes of the fans watching around the world. Every match has its turning point, "
            f"and this is it. The player did not hesitate. The decision was made in a fraction of "
            f"a second. Body position, ball control, spatial awareness — all came together in one "
            f"fluid motion. This is what peak athletic performance looks like when the pressure is "
            f"at its highest and the moment demands everything. "
            f"This is the kind of play that defines careers and becomes part of football folklore. "
            f"It will be replayed, analyzed, and talked about for years to come. And yet, for the "
            f"player involved, it was just an instant. A split-second decision executed with "
            f"thousands of hours of training behind it. That is the beauty of sport at this level."
        )
    elif content_type == "series":
        narrative = (
            f"Television at its finest lives in moments like this. The writers crafted every word, "
            f"the actors delivered every glance with precision, and the directors captured it all "
            f"in a single, unbroken take. This scene represents the peak of what serialized "
            f"storytelling can achieve — building episodes of tension, character development, "
            f"and emotional investment that culminates in this frame. No background music needed. "
            f"No dramatic score. Just the raw talent of everyone involved, captured in real time. "
            f"This is why television has become the dominant art form of our generation. What makes "
            f"this scene extraordinary is the restraint shown by everyone involved. The silence "
            f"between the lines. The micro-expressions on the actors faces. The way the camera "
            f"holds just a moment longer than expected. These are choices made by people who "
            f"understand that less is more. Great television does not tell you what to feel — it "
            f"creates space for you to feel it yourself. This scene does exactly that. It trusts "
            f"the audience. It respects the intelligence of the viewer. And in doing so, it "
            f"achieves something that stays with you long after the episode ends. This is writing "
            f"at its most confident. This is acting at its most truthful. This is why we invest "
            f"hours of our lives following these characters and their stories. Moments like this "
            f"make it all worth it. They remind us why storytelling matters."
        )
    else:
        narrative = (
            f"Cinema has the power to stop time. This scene, captured in a single moment, "
            f"represents everything that makes film the most immersive art form. The cinematography, "
            f"the blocking, the performance — all elements align to create something transcendent. "
            f"Every frame is a painting. Every silence carries meaning. The director's vision, "
            f"the actor's commitment, and the editor's rhythm combine to produce a moment that "
            f"lives in the mind long after the credits roll. No music distracts. No score manipulates. "
            f"Just pure cinema. Consider what went into making this moment work. The lighting design "
            f"that draws your eye exactly where it needs to go. The production design that places "
            f"every object with purpose. The sound design that captures the ambient texture of the "
            f"world. These are not accidents. They are the result of hundreds of artists working "
            f"toward a shared vision. When you watch a scene like this, you are seeing the "
            f"culmination of thousands of decisions, each one made in service of the story. "
            f"Great cinema does not explain itself. It simply exists, and invites you to experience it. "
            f"Watch this scene and notice how much is communicated without words. The framing, "
            f"the lighting, the movement within the frame — all of it is language. A language "
            f"that transcends borders and speaks directly to something universal in all of us."
        )
    lines.append(narrative)
    lines.append("")

    # Contextual Footer
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🎬 VARY — three times daily, one clip at a time")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")

    if content_type == "football":
        lines.append("⚽ Source: " + (source_title or "Match footage"))
        lines.append("🏟️ Format: Raw match moment — no music, natural sound only")
    elif content_type == "series":
        lines.append("📺 Source: " + (source_title or "TV series scene"))
        lines.append("🎭 Format: Scene clip — original dialogue preserved")
    else:
        lines.append("🎬 Source: " + (source_title or "Film scene"))
        lines.append("🎥 Format: Cinema moment — original audio preserved")

    if source_url:
        lines.append(f"📎 Original: {source_url}")

    lines.append("")
    lines.append("No music. No commentary. Just the moment.")
    lines.append("")

    # Hashtag Triad
    if content_type == "football":
        lines.append("#Shorts #Football #RawEmotion")
    elif content_type == "series":
        lines.append("#Shorts #TVSeries #RawEmotion")
    else:
        lines.append("#Shorts #Cinema #RawEmotion")

    return "\n".join(lines)


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

    # Blueprint Section 1.2: Build rich 250+ word description
    description = build_rich_description(source_title, content_type, source_url)

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
