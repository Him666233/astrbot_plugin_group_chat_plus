"""Bounded renderer for known QQ JSON share-card shapes."""
import json
import re
import unicodedata
from urllib.parse import unquote_to_bytes, urlsplit

try:
    from astrbot.api.message_components import Json
except ImportError:
    try:
        from astrbot.core.message.components import Json
    except ImportError:
        Json = None

MAX_RAW = 65536
MAX_OUTPUT = 1000
SECTIONS = ("detail_1", "detail", "news", "video", "music", "mannounce")


def is_json_component(value):
    return Json is not None and isinstance(value, Json)


_BIDI_CONTROLS = {0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A)}


def _unsafe_char(char):
    return unicodedata.category(char) in ("Cc", "Cs") or ord(char) in _BIDI_CONTROLS


def _clean(value, limit):
    if not isinstance(value, str):
        return ""
    value = value[:limit * 4]
    value = "".join(c for c in value if not _unsafe_char(c))
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit]


_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")
_SONG_ID = re.compile(r"[1-9][0-9]{0,19}\Z")
_VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}\Z")
_QUERY_KEY = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,31}\Z")


def _safe_path(path):
    if _PERCENT.search(path):
        return False
    try:
        decoded = unquote_to_bytes(path).decode("utf-8")
    except (UnicodeDecodeError, ValueError):
        return False
    return not any(_unsafe_char(char) for char in decoded)


def _host(netloc, hostname):
    # An @ delimiter, colon, or escaped/non-ASCII authority is never accepted,
    # including empty userinfo and explicit default ports.
    if "@" in netloc or ":" in netloc or "%" in netloc or not netloc.isascii():
        return ""
    if not hostname or len(hostname) > 253 or hostname.endswith("."):
        return ""
    labels = hostname.split(".")
    if len(labels) < 2 or any(
        not label or len(label) > 63 or not label[0].isalnum() or not label[-1].isalnum()
        or any(not (char.isascii() and (char.isalnum() or char == "-")) for char in label)
        for label in labels
    ):
        return ""
    return hostname.lower()


def _route_query(query):
    if not query or len(query) > 512:
        return None
    fields = query.split("&")
    if not 1 <= len(fields) <= 8:
        return None
    parsed = {}
    for field in fields:
        if not field or len(field) > 256 or any(char in field for char in "%+;") or field.count("=") != 1:
            return None
        key, value = field.split("=", 1)
        if not _QUERY_KEY.fullmatch(key) or key.lower() in parsed:
            return None
        parsed[key.lower()] = (key, value)
    return parsed


def _identity(query, key, pattern):
    parsed = _route_query(query)
    if parsed is None or key not in parsed or parsed[key][0] != key:
        return None
    value = parsed[key][1]
    return value if pattern.fullmatch(value) else None


def _url(value):
    if (not isinstance(value, str) or len(value) > 2048
            or any(_unsafe_char(c) or c.isspace() or c == "\\" for c in value)):
        return ""
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
            return ""
        host = _host(parsed.netloc, parsed.hostname)
        if not host or not _safe_path(parsed.path):
            return ""
        scheme = parsed.scheme.lower()
        path = parsed.path
        if host == "music.163.com" and path == "/song":
            song_id = _identity(parsed.query, "id", _SONG_ID)
            return f"{scheme}://{host}/song?id={song_id}" if song_id else ""
        if host == "music.163.com" and path in ("", "/") and parsed.fragment.startswith("/song"):
            if not parsed.fragment.startswith("/song?"):
                return ""
            song_id = _identity(parsed.fragment[len("/song?"):], "id", _SONG_ID)
            return f"{scheme}://{host}/#/song?id={song_id}" if song_id else ""
        if host in ("youtube.com", "www.youtube.com") and path == "/watch":
            video_id = _identity(parsed.query, "v", _VIDEO_ID)
            return f"{scheme}://{host}/watch?v={video_id}" if video_id else ""
        clean = f"{scheme}://{host}{path}"
        return clean if len(clean) <= 500 else ""
    except (ValueError, UnicodeError):
        return ""


def render_json_card(payload):
    """Render only fixed known fields; never stringify unknown payloads."""
    try:
        if isinstance(payload, str):
            if len(payload) > MAX_RAW:
                return "[JSON卡片]"
            payload = json.loads(payload)
        if not isinstance(payload, dict):
            return "[JSON卡片]"
        meta = payload.get("meta")
        if not isinstance(meta, dict):
            meta = {}
        sections = [meta.get(key) for key in SECTIONS if isinstance(meta.get(key), dict)]
        prompt = _clean(payload.get("prompt"), 300)
        app = _clean(payload.get("app"), 100)
        title = next((_clean(section.get("title"), 200) for section in sections if _clean(section.get("title"), 200)), "")
        desc = next((_clean(section.get("desc") or section.get("summary"), 500) for section in sections if _clean(section.get("desc") or section.get("summary"), 500)), "") or _clean(payload.get("desc"), 500)
        link = ""
        for key in ("qqdocurl", "jumpUrl", "url"):
            for candidate in [s.get(key) for s in sections] + [payload.get(key)]:
                link = _url(candidate)
                if link:
                    break
            if link:
                break
        values = []
        for value in (prompt, app, title, desc, link):
            if value and value not in values:
                values.append(value)
        if not values:
            return "[JSON卡片]"
        if link:
            head = "[JSON卡片] " + " | ".join(v for v in values if v != link)
            head = head[:max(0, MAX_OUTPUT - len(link) - 3)].rstrip(" |")
            return (head + " | " + link)[:MAX_OUTPUT]
        return ("[JSON卡片] " + " | ".join(values))[:MAX_OUTPUT]
    except (ValueError, TypeError, RecursionError, UnicodeError):
        return "[JSON卡片]"


def render_json_component(component):
    return render_json_card(getattr(component, "data", None))
