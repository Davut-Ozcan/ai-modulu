"""Accessibility screen_text → anlamlı içerik segmentleri.

screen_text, ekrandaki tüm node'ların ' | ' ile birleşimi; çoğu UI kromu
(Like, Share, 'Reel by X. Double tap...'). Burada:
  1) UI segmentlerini at
  2) Kalanları tipine göre etiketle: caption / audio / author / comment / text
"""
import re

UI_EXACT = {
    "reels", "home", "profile", "search and explore", "message", "messages", "follow", "following",
    "like", "comment", "more", "share", "save", "repost", "for you", "friends", "audio", "seekbar",
    "create a reel", "turn sound on", "reels tray container", "suggested for you", "add to saved",
    "ad", "add to story", "user avatars", "instagram home feed", "view tagged people", "older posts",
    "notifications", "create", "dismiss", "watch again", "tap to watch more reels", "watch more reels",
    "no unread messages", "back", "add comment…", "interested", "not interested", "install now",
    "shop now", "loading…", "requests", "add note", "location off", "profile picture", "note…",
    "search", "new message", "search or ask meta ai", "instagram recommended", "more actions for this post",
    "…", "instagram profile picture", "learn more", "sponsored", "send", "reply", "see translation",
    "hide", "view all", "unmute", "mute", "pause", "play", "close", "next", "previous",
}

UI_PATTERNS = [
    r"^[\d.,]+[km]?$",
    r"^@?\d+$",
    r"^(save|reshare|like|comment) number is",
    r"^reposted \d+ times?$",
    r"^send post\.",
    r"^.+'s story, \d+ of \d+",
    r"^profile picture of ",
    r"^follow ",
    r"^\d+ (seconds?|minutes?|hours?|days?|weeks?) ago$",
    r"^(january|february|march|april|may|june|july|august|september|october|november|december) \d+$",
    r"^you've seen the latest",
    r"^create a post, story",
    r"^test \w+component",
    r"^double tap",
    r"^try[\d.,]+$",
    r"^[\d.,]+ followers?$",
    r"^go to ",
    r"^view (likes|comments|replies)",
    r"^\d+:\d{2}$",
    r"^(mon|tue|wed|thu|fri|sat|sun), \w+ \d+$",
    r"posts tagged ",
    r"^[\d.,]+[km]? follow .+ on instagram$",
    r"^(followed|liked) by ",
    r" liked this reel$",
    r"^\d+ (replies|likes|comments?)$",
    r"ago\s+•\s+see translation$",
    r"profile photo$",
    r"^\S+ posted$",
    r"^\S+\s+and \S+$",
    r"^(google|gmail|chrome|youtube|reddit|phone|camera|play store|facebook|whatsapp|instagram)( app| lens| search)?$",
]
_UI_RE = re.compile("|".join(UI_PATTERNS), re.I)

_REEL_BY = re.compile(r"^(Sponsored |Suggested )?Reel by ([^,.]+(?:\.[\w]+)*?)(?:\. Double tap|,|$)", re.I)
_PHOTO_BY = re.compile(r"^(?:Suggested |Sponsored )?(?:Photo|Video|Carousel)(?: \d+ of \d+)? by (.+?), [\d.,]+ likes", re.I)
_SUGGESTED = re.compile(r"^(?:Suggested|Sponsored) (?:Reel|Photo|Video|Carousel)(?: by)? ([^,]+?)(?:,|\. Double tap|$)", re.I)
_ORIGINAL = re.compile(r"^(?:Original by|Template from|Photo \d+ of \d+ by) (.+)$", re.I)
_POSTED = re.compile(r"^([\w.]+) posted an? (video|photo|carousel|reel)", re.I)
_USERNAME = re.compile(r"^[a-z0-9._]{3,30}$")


def segments(screen_text: str) -> list[dict]:
    out, seen = [], set()
    for raw in screen_text.split(" | "):
        s = raw.strip()
        if not s or s.lower() in UI_EXACT or _UI_RE.search(s):
            continue
        if m := _REEL_BY.match(s):
            kind, s = ("ad" if (m.group(1) or "").lower().startswith("sponsored") else "author"), m.group(2).strip()
        elif m := _PHOTO_BY.match(s):
            kind, s = "author", m.group(1)
        elif m := _SUGGESTED.match(s):
            kind, s = ("ad" if s.lower().startswith("sponsored") else "author"), m.group(1).strip()
        elif m := _ORIGINAL.match(s):
            kind, s = "author", m.group(1).strip()
        elif m := _POSTED.match(s):
            kind, s = "author", m.group(1)
        elif " · " in s:
            # 'kullanıcı · Original audio' / 'Sanatçı · Şarkı' / 'a, b · yorum'
            kind = "comment" if s.split(" · ")[0].count(",") >= 2 else "audio"
        elif s.endswith("…"):
            kind, s = "caption", s.rstrip(" …").strip()
        elif _USERNAME.match(s):
            kind = "username"
        else:
            kind = "text"
        if kind in ("author", "username"):
            s = s.rstrip(".")
        # 'kullaniciadi caption metni… more' → caption
        s = re.sub(r"…\s*more$", "", s).strip()
        key = s.lower()
        if key in seen or len(s) < 2:
            continue
        seen.add(key)
        out.append({"kind": kind, "text": s})
    return out
