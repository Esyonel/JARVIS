"""
Wraps Panniantong/agent-reach (https://github.com/Panniantong/agent-reach), a
Python toolkit that gives an AI agent zero-config, no-login access to public
internet sources. Only the channels that work without cookies/OAuth are wired
up here: any webpage (Jina Reader), YouTube video info, GitHub repo search,
Bilibili video search, RSS/Atom feeds, and V2EX hot topics.

Login-gated channels (Twitter, Reddit, Instagram, Facebook, XiaoHongShu,
LinkedIn) are intentionally NOT wired up — they need the user to run
`agent-reach configure <platform>-cookies` by hand first.
"""
import re

PLUGIN = {
    "name": "internet_reach",
    "description": (
        "Fetches specific content from a named platform: reads the clean text of a "
        "given URL, looks up a YouTube video's title/description, searches GitHub "
        "repositories, searches Bilibili videos, reads the latest items from an "
        "RSS/Atom feed URL, or lists today's hot topics on V2EX. Use this when the "
        "user gives an explicit URL to read, or explicitly names GitHub, YouTube, "
        "Bilibili, an RSS feed, or V2EX. For general web/news/price search without "
        "a named platform or URL, use web_search instead."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "One of: read_url, youtube_info, github_search, bilibili_search, "
                    "rss_read, v2ex_hot"
                ),
            },
            "query": {
                "type": "STRING",
                "description": (
                    "URL (for read_url/youtube_info/rss_read) or search text "
                    "(for youtube_info/github_search/bilibili_search). Not needed for v2ex_hot."
                ),
            },
        },
        "required": ["action"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = (parameters.get("action") or "").strip().lower()
    query = (parameters.get("query") or "").strip()

    handlers = {
        "read_url": _read_url,
        "youtube_info": _youtube_info,
        "github_search": _github_search,
        "bilibili_search": _bilibili_search,
        "rss_read": _rss_read,
        "v2ex_hot": _v2ex_hot,
    }
    handler = handlers.get(action)
    if handler is None:
        return f"Sir, '{action}' isn't a known internet_reach action."

    try:
        result = handler(query)
    except Exception as e:
        result = f"Sir, internet_reach couldn't complete '{action}': {e}"

    _log(result, player)
    return result


def _log(message: str, player=None) -> None:
    print(f"[InternetReach] {message}")
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


def _read_url(query: str) -> str:
    if not query:
        return "Sir, I need a URL to read."
    from agent_reach.channels.web import WebChannel

    url = query if query.startswith(("http://", "https://")) else f"https://{query}"
    text = WebChannel().read(url)
    return f"Here's what's on that page: {_truncate(text, 1200)}"


def _youtube_info(query: str) -> str:
    if not query:
        return "Sir, I need a video URL or search term for YouTube."
    import yt_dlp

    target = query if query.startswith(("http://", "https://")) else f"ytsearch1:{query}"
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(target, download=False)
    if "entries" in info:
        entries = info.get("entries") or []
        if not entries:
            return f"Sir, no YouTube video found for '{query}'."
        info = entries[0]

    title = info.get("title", "Unknown title")
    uploader = info.get("uploader", "unknown channel")
    duration = info.get("duration")
    duration_txt = f"{duration // 60}m{duration % 60:02d}s" if duration else "unknown length"
    desc = _truncate(info.get("description") or "", 250)
    return f"'{title}' by {uploader}, {duration_txt}. {desc}"


def _github_search(query: str) -> str:
    if not query:
        return "Sir, I need a search term for GitHub."
    import requests

    resp = requests.get(
        "https://api.github.com/search/repositories",
        params={"q": query, "sort": "stars", "order": "desc", "per_page": 5},
        headers={"Accept": "application/vnd.github+json", "User-Agent": "JARVIS-internet-reach"},
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        return f"Sir, no GitHub repositories found for '{query}'."
    lines = [
        f"{it['full_name']} ({it['stargazers_count']} stars): {_truncate(it.get('description') or '', 100)}"
        for it in items
    ]
    return f"Top GitHub results for '{query}': " + "; ".join(lines)


def _bilibili_search(query: str) -> str:
    if not query:
        return "Sir, I need a search term for Bilibili."
    import requests

    resp = requests.get(
        "https://api.bilibili.com/x/web-interface/search/all/v2",
        params={"keyword": query},
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        return f"Sir, Bilibili search failed: {data.get('message', 'unknown error')}"

    videos = []
    for group in (data.get("data") or {}).get("result") or []:
        if group.get("result_type") == "video":
            videos = group.get("data") or []
            break
    if not videos:
        return f"Sir, no Bilibili videos found for '{query}'."

    lines = []
    for v in videos[:5]:
        title = re.sub(r"</?em[^>]*>", "", v.get("title", ""))
        lines.append(f"{title} by {v.get('author', 'unknown')} ({v.get('play', 0)} views)")
    return f"Top Bilibili results for '{query}': " + "; ".join(lines)


def _rss_read(query: str) -> str:
    if not query:
        return "Sir, I need a feed URL to read."
    import feedparser

    feed = feedparser.parse(query)
    entries = feed.entries[:5]
    if not entries:
        return f"Sir, I couldn't find any entries in that feed."
    titles = [e.get("title", "(untitled)") for e in entries]
    feed_title = feed.feed.get("title", "the feed")
    return f"Latest from {feed_title}: " + "; ".join(titles)


def _v2ex_hot(query: str) -> str:
    from agent_reach.channels.v2ex import V2EXChannel

    topics = V2EXChannel().get_hot_topics(limit=5)
    if not topics:
        return "Sir, V2EX didn't return any hot topics right now."
    lines = [f"{t['title']} ({t['replies']} replies)" for t in topics]
    return "Trending on V2EX: " + "; ".join(lines)
