"""
VARY — YouTube Policy Compliance Checker.
Prevents copyright strikes, Content ID blocks, and reused content violations.
Enforced BEFORE every download and BEFORE every upload.
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LOG_DIR

POLICY_LOG = os.path.join(LOG_DIR, "policy_violations.jsonl")

# ── GOLDEN RULES (NEVER VIOLATE) ────────────────────────────────
# Rule 1: NEVER download from official movie studio channels
#          They ALL use Content ID. Even 3-second clips get blocked.
# Rule 2: NEVER upload un-transformed movie clips
#          Must have voiceover, commentary, or clear analysis.
# Rule 3: NEVER upload compilations of copyrighted clips
#          Multiple copyrighted works = multiple Content ID matches.
# Rule 4: NEVER use clips with music/songs in background
#          Music triggers separate audio Content ID.
# Rule 5: ALWAYS check channel name against studio blacklist
#          Before download, before edit, before upload.

# ── STUDIO BLACKLIST (Content ID death) ────────────────────────
# These channels will ALWAYS result in a Content ID block.
# NEVER download from them, even if the video looks perfect.
STUDIO_CHANNELS = [
    # Major studios — aggressive Content ID
    "paramount pictures", "paramount movies",
    "universal pictures", "focus features",
    "warner bros. pictures", "warner bros pictures",
    "sony pictures", "sony pictures entertainment",
    "movieclips",  # OWNED BY SONY — will always claim
    "marvel entertainment", "marvel hq",
    "disney plus", "disney channel",
    "20th century studios", "20th century fox",
    "apple tv+",
    "amazon mgm",
    "mgm studios",
    "dreamworks animation",
    "illumination",
    "studio ghibli",
    # Less aggressive — allow partial matches (fan channels may have these in name)
    # "paramount", "universal", "warner bros", "netflix",
    # "hbo", "disney", "marvel", "nbc", "abc", "cbs",
    # "lionsgate", "mgm", "a24",
    # "apple tv", "amazon prime video", "prime video",
    # Football broadcasters are SAFE for short clips (news/editorial value)
    # News agencies — aggressive on any news footage
    "abc news", "bbc news",
    "associated press", "ap archive",
    "reuters",
]

# Channels that are SAFE to download from (fan content, analysis, commentary)
SAFE_CHANNEL_PATTERNS = [
    # Fan channels (usually safe)
    "fan", "edits", "edit",
    # Analysis/commentary
    "analysis", "explained", "breakdown", "review",
    # Compilation channels that are actually safe
    "best of", "top ", "amazing",
    # Non-official content
    "clips", "scenes",
]

# Content types that NEVER get copyrighted (safe to use)
SAFE_CONTENT_TYPES = [
    "football",  # Match highlights are generally safe (news/editorial)
]

# Video title patterns that indicate risky content
# NOTE: year patterns like (2024) and "movie clip" are too aggressive — almost
# all clips have these. Only block obvious studio-style title patterns.
RISKY_TITLE_PATTERNS = [
    r"official\s+(trailer|clip|scene)",
]

# Compilation patterns — high risk even from non-studio channels
# A compilation contains N copyrighted works = N ways to get Content ID blocked
COMPILATION_PATTERNS = [
    r"top\s+\d+", r"\d+\s+most", r"best\s+of", r"greatest",
    r"iconic\s+(movie|film|scene|moment|line)",
    r"most\s+(iconic|famous|memorable|epic|amazing)",
    r"compilation", r"mega\s+compilation", r"supercut",
    r"ultimate\s+(compilation|collection|mix)",
    r"all\s+(time|best|greatest)",
    r"every\s+(movie|scene|moment|line)",
    r"100\s+most", r"50\s+best", r"top\s+10", r"top\s+20", r"top\s+100",
]

# ── Violations log ──────────────────────────────────────────────

def _log_violation(policy, video_title, channel, reason):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "policy": policy,
        "video_title": video_title,
        "channel": channel,
        "reason": reason,
        "action": "BLOCKED",
    }
    os.makedirs(os.path.dirname(POLICY_LOG), exist_ok=True)
    with open(POLICY_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"  [policy] BLOCKED [{policy}] {video_title[:60]} — {reason}", flush=True)


# ── Checks ───────────────────────────────────────────────────────

def check_channel_blacklist(channel_name):
    """Check if a channel is a major studio (will trigger Content ID).
    Returns (is_blocked, reason).
    """
    if not channel_name:
        return False, ""
    ch = channel_name.lower().strip()

    for studio in STUDIO_CHANNELS:
        if studio in ch:
            return True, f"Channel '{channel_name}' contains '{studio}' — Content ID risk"

    return False, ""


def check_title_risk(title):
    """Check if video title indicates high copyright risk content."""
    if not title:
        return False, ""
    tl = title.lower()

    for pattern in RISKY_TITLE_PATTERNS:
        if re.search(pattern, tl):
            return True, f"Title matches risky pattern: '{pattern}'"

    return False, ""


def check_compilation_risk(title, content_type="movie"):
    """Check if title indicates a compilation video (high copyright risk).
    Compilations contain multiple copyrighted works = guaranteed Content ID issues.
    """
    if not title:
        return False, ""
    if content_type in SAFE_CONTENT_TYPES:
        return False, ""
    tl = title.lower()
    for pattern in COMPILATION_PATTERNS:
        if re.search(pattern, tl):
            return True, f"Compilation pattern detected: '{pattern}' — multiple copyrighted works"
    return False, ""


def check_studio_seo(title, channel):
    """Combined check — title + channel to detect official studio uploads."""
    tl = title.lower() if title else ""
    ch = channel.lower() if channel else ""

    # If a channel has "movieclips" in name AND title mentions a movie = BLOCK
    studio_indicators = ["movieclips", "paramount", "warner bros", "universal pictures",
                         "sony pictures", "disney", "marvel", "netflix", "hbo"]
    movie_indicators = ["scene", "clip", "official", "trailer", "movie", "film",
                        "(19", "(20"]

    has_studio = any(s in ch for s in studio_indicators)
    has_movie_tell = any(m in tl for m in movie_indicators)

    if has_studio and has_movie_tell:
        return True, f"Studio channel '{channel}' with movie content '{title[:50]}'"

    return False, ""


def check_content_transformation(content_type, has_voiceover, has_speed_ramp,
                                  has_color_grade, has_subtitles):
    """Check if the video has enough transformation for fair use.
    YouTube requires transformative value for reused content.
    Minimum: at least 3 transformations applied.
    """
    transformations = sum([has_voiceover, has_speed_ramp, has_color_grade, has_subtitles])

    if content_type in SAFE_CONTENT_TYPES:
        return True, ""

    if transformations >= 3:
        return True, ""
    elif transformations >= 2:
        return True, "Borderline — 2 transformations applied"
    else:
        return False, f"Only {transformations}/4 transformations — add voiceover + effects"


def check_compilation_risk_for_video(video_info):
    """Check if video is a compilation of multiple copyrighted works.
    These are high-risk even from non-studio channels.
    """
    title = video_info.get("title", "")
    channel = video_info.get("channel", "") or video_info.get("uploader", "")
    content_type = video_info.get("content_type", "movie")

    blocked, reason = check_compilation_risk(title, content_type)
    if blocked:
        _log_violation("COMPILATION_RISK", title, channel, reason)
        return False, reason
    return True, None


def pre_download_check(video_info):
    """Run all policy checks before downloading a video.
    Returns (is_safe, reason_or_none).
    """
    title = video_info.get("title", "")
    channel = video_info.get("channel", "") or video_info.get("uploader", "")
    video_id = video_info.get("id", "")

    # Check 1: Studio channel blacklist
    blocked, reason = check_channel_blacklist(channel)
    if blocked:
        _log_violation("STUDIO_CHANNEL", title, channel, reason)
        return False, reason

    # Check 2: Studio SEO (channel + title combo)
    blocked, reason = check_studio_seo(title, channel)
    if blocked:
        _log_violation("STUDIO_SEO", title, channel, reason)
        return False, reason

    # Check 3: Risky title patterns
    blocked, reason = check_title_risk(title)
    if blocked:
        _log_violation("RISKY_TITLE", title, channel, reason)
        return False, reason

    # Check 4: Compilation risk (multiple copyrighted works)
    blocked, reason = check_compilation_risk(title)
    if blocked:
        _log_violation("COMPILATION_RISK", title, channel, reason)
        return False, reason

    return True, None


def get_policy_report():
    """Get summary of all policy violations for dashboard."""
    violations = []
    if os.path.exists(POLICY_LOG):
        try:
            with open(POLICY_LOG, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        violations.append(json.loads(line))
        except (json.JSONDecodeError, IOError):
            pass
    return violations[-50:]  # Last 50


# ── Policy reference (for GitHub issues) ───────────────────────

POLICY_REFERENCE = {
    "copyrigt_content_id": {
        "title": "Copyright & Content ID — NEVER upload raw movie clips",
        "summary": "YouTube's Content ID system automatically scans every upload against a database of copyrighted material. Major studios (Disney, Warner Bros, Paramount, Sony, Universal, Netflix, HBO) register their content. Even a 3-second clip triggers a block.",
        "consequences": ["Video blocked worldwide", "Copyright strike on channel (3 strikes = termination)",
                          "Channel demonetized", "Loss of access to YouTube Partner Program"],
        "prevention": ["NEVER download from official studio channels (Movieclips, Paramount Movies, etc.)",
                        "ALWAYS add voiceover + commentary (transformative use)",
                        "ALWAYS apply 3+ visual transformations (speed ramp, color grade, subtitles, zoom)",
                        "NEVER use clips with identifiable music/songs",
                        "Prefer fan channels, analysis channels, or commentary channels"],
    },
    "reused_content": {
        "title": "Reused Content Policy — Each video must have unique value",
        "summary": "YouTube's Reused Content Policy (2026) targets channels that repackage third-party content without adding significant original value. Simply cropping, color-grading, and adding transitions is NOT enough. The core experience must come from your unique perspective.",
        "consequences": ["Denied from YouTube Partner Program", "Demonetized",
                          "90-day wait to reapply after fixing content",
                          "Channel flagged as 'reused content' — reduced reach"],
        "prevention": ["Add original voiceover to EVERY video",
                        "Include unique analysis, commentary, or storytelling",
                        "Never produce templated content (same structure daily)",
                        "Each video must be distinguishable from the last",
                        "Use AI as a production assistant, NOT a content creator"],
    },
    "inauthentic_content": {
        "title": "Inauthentic (Repetitious) Content — No mass-produced templates",
        "summary": "YouTube renamed 'Repetitious Content' to 'Inauthentic Content' in 2025. This targets mass-produced, templated videos that differ only in small details. Daily uploads with identical structure, same voiceover style, same b-roll = flagged as spam.",
        "consequences": ["Channel flagged as spam", "Reduced search/suggested reach",
                          "Monetization revoked", "Channel termination for repeat offenses"],
        "prevention": ["Vary video structure daily (different pacing, different effects)",
                        "Use different voiceover styles, music, and pacing",
                        "NEVER use the exact same template for every video",
                        "Include original research or unique perspective",
                        "At least 30% of each video should be original creation"],
    },
    "fair_use": {
        "title": "Fair Use — Transformation is NOT automatic protection",
        "summary": "Fair use is a legal defense, not an automatic right. YouTube does NOT decide fair use — courts do. Simply editing clips (color grade, speed ramp, subtitles) without adding commentary, criticism, or analysis is NOT transformative enough.",
        "consequences": ["Content ID claims still apply even if you edit",
                          "Copyright strikes for unlicensed use",
                          "Legal liability (lawsuits from studios)",
                          "False sense of security = more strikes"],
        "prevention": ["Fair use REQUIRES: commentary, criticism, education, or parody",
                        "Adding voiceover analysis is the MINIMUM for fair use argument",
                        "Short clips (under 10s) are safer but not guaranteed",
                        "NEVER rely on 'editing = transformative' — this is a myth",
                        "When in doubt: add more original content (voice, visuals, analysis)"],
    },
    "community_guidelines": {
        "title": "Community Guidelines — Content must be advertiser-friendly",
        "summary": "YouTube Community Guidelines prohibit violent content, hate speech, misinformation, spam, and harmful acts. Even if content is not copyrighted, it must follow these guidelines or risk channel strikes.",
        "consequences": ["Content removed", "Channel warning or strike",
                          "1-week upload restriction", "Channel termination for 3 strikes"],
        "prevention": ["No violent/graphic content", "No hate speech or harassment",
                        "No misinformation or conspiracy theories",
                        "No spam or deceptive practices",
                        "Mark content as 'made for kids' if applicable"],
    },
}


if __name__ == "__main__":
    # Test
    print(json.dumps({k: v["title"] for k, v in POLICY_REFERENCE.items()}, indent=2))
    if len(sys.argv) > 1:
        test = {"title": sys.argv[1], "channel": sys.argv[2] if len(sys.argv) > 2 else ""}
        safe, reason = pre_download_check(test)
        print(f"Safe: {safe}")
        if reason:
            print(f"Reason: {reason}")
