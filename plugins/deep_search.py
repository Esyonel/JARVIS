"""
JARVIS plugin — Deep Search (multi-agent internet research).

Fans three search agents out in parallel — a Gemini-grounded search biased
toward the user's own region, and two DuckDuckGo passes (region-local, then
worldwide) — then merges them into one answer. For product queries ("Bambulab
A2L nozzle fiyatı ne kadar") that means a price comparison with a link per
offer, region-local sellers first. For anything else it's a synthesized,
sourced summary. All three agents run concurrently so the whole thing takes
about as long as the slowest single search, not the sum of three.
"""

import re
import threading
from urllib.parse import urlparse

PLUGIN = {
    "name": "deep_search",
    "description": (
        "Fast MULTI-AGENT deep internet search — runs several search agents in "
        "parallel (region-biased Gemini grounded search + two DuckDuckGo passes) "
        "and merges them into one answer, on ANY topic. Use this — instead of "
        "web_search — whenever the user explicitly asks for a deep/thorough "
        "search ('derin ara', 'deep search', 'iyice araştır'), OR asks for a "
        "PRODUCT PRICE / where-to-buy / price comparison (e.g. 'Bambulab A2L "
        "nozzle fiyatı ne kadar', 'en ucuz nereden alırım', 'fiyat karşılaştır'). "
        "For price queries it returns actual offers with site name, price, and "
        "a clickable link, checking the user's own region/country first. "
        "Pass kind='price' for any product/price/purchase question, otherwise "
        "kind='general'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "What to search for — product name or topic/question, in the user's own words.",
            },
            "kind": {
                "type": "STRING",
                "description": "'price' for a product price/purchase/comparison lookup, 'general' for anything else. Default 'general'.",
            },
            "region": {
                "type": "STRING",
                "description": "Country to prioritize results from (e.g. 'Turkey', 'Germany'). Defaults to Turkey.",
            },
        },
        "required": ["query"],
    },
}

_GEMINI_MODEL = "gemini-flash-latest"

# Country name (however the model spells it) -> DuckDuckGo region code.
_REGION_CODES = {
    "turkey": "tr-tr", "türkiye": "tr-tr", "turkiye": "tr-tr",
    "usa": "us-en", "united states": "us-en", "america": "us-en",
    "uk": "uk-en", "united kingdom": "uk-en", "england": "uk-en",
    "germany": "de-de", "deutschland": "de-de",
    "france": "fr-fr",
}
_DEFAULT_REGION_NAME = "Turkey"
_DEFAULT_REGION_CODE = "tr-tr"

_PRICE_RE = re.compile(
    r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\s*(TL|₺|USD|\$|EUR|€)'
    r'|(TL|₺|USD|\$|EUR|€)\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)',
    re.IGNORECASE,
)


def _region_code(name: str) -> str:
    return _REGION_CODES.get((name or "").strip().lower(), _DEFAULT_REGION_CODE)


def _extract_price(text: str) -> str | None:
    m = _PRICE_RE.search(text or "")
    if not m:
        return None
    groups = [g for g in m.groups() if g]
    return "".join(groups[:2]) if len(groups) >= 2 else None


def _price_value(price_str: str) -> float:
    """Best-effort numeric value for sorting; never raises."""
    digits = re.sub(r'[^\d.,]', '', price_str or '')
    digits = digits.replace('.', '').replace(',', '.') if digits.count(',') == 1 else digits.replace(',', '')
    try:
        return float(re.sub(r'[^\d.]', '', digits) or 'inf')
    except Exception:
        return float('inf')


# ── agents (each runs in its own thread, never raises) ─────────────────────

def _gemini_grounded(key: str, prompt: str) -> str:
    from google import genai

    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model=_GEMINI_MODEL,
        contents=prompt,
        config={"tools": [{"google_search": {}}]},
    )
    text = "".join(
        part.text for part in response.candidates[0].content.parts
        if getattr(part, "text", None)
    ).strip()
    if not text:
        raise RuntimeError("empty response")
    return text


def _agent_gemini(query: str, kind: str, region_name: str, out: dict) -> None:
    try:
        from core.gemini_keys import call_with_rotation

        if kind == "price":
            instructions = (
                f"This is a PRODUCT PRICE / where-to-buy query. Search for current offers, "
                f"prioritizing sellers and sites based in {region_name} first, then other "
                f"major sites if useful. Reply with a one-sentence intro, then a numbered "
                f"list of the best offers: site name — price (with currency) — the product "
                f"page URL. Sort cheapest first when you can tell."
            )
        else:
            instructions = (
                f"Search for this and give a clear, well-organized, comprehensive answer: "
                f"key facts, current state, and useful nuance. Prefer sources from "
                f"{region_name} when relevant, but don't skip better sources elsewhere. "
                f"Mention source names inline."
            )
        prompt = f'Query: "{query}"\n{instructions}\nReply in the same language as the query.'

        out["gemini"] = call_with_rotation(_gemini_grounded, prompt)
    except Exception as e:
        print(f"[DeepSearch] ⚠️ Gemini agent failed: {e}")
        out["gemini"] = ""


def _ddg_pass(query: str, region: str, max_results: int = 6) -> list[dict]:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS

    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, region=region, max_results=max_results):
            results.append({
                "title": r.get("title", ""),
                "snippet": r.get("body", ""),
                "url": r.get("href", ""),
            })
    return results


def _agent_ddg_local(query: str, kind: str, region_code: str, out: dict) -> None:
    try:
        q = f"{query} fiyat" if kind == "price" else query
        out["ddg_local"] = _ddg_pass(q, region=region_code)
    except Exception as e:
        print(f"[DeepSearch] ⚠️ DDG local agent failed: {e}")
        out["ddg_local"] = []


def _agent_ddg_global(query: str, kind: str, out: dict) -> None:
    try:
        q = f"{query} price" if kind == "price" else query
        out["ddg_global"] = _ddg_pass(q, region="wt-wt")
    except Exception as e:
        print(f"[DeepSearch] ⚠️ DDG global agent failed: {e}")
        out["ddg_global"] = []


# ── merge + format ──────────────────────────────────────────────────────────

# Social/forum/reference platforms never sell products — casual mentions of a
# dollar figure in a comment or article there ("snagged mine for $50 under
# MSRP") get misread as a store price. Excluded regardless of query topic.
_NON_COMMERCE_DOMAINS = {
    "reddit.com", "youtube.com", "wikipedia.org", "twitter.com", "x.com",
    "facebook.com", "instagram.com", "quora.com", "pinterest.com", "linkedin.com",
}

# Editorial URL patterns (news/review/blog articles) show up for any product
# category — a $600 mentioned in a GPU review or a car review is a quoted
# figure, not something you can click "buy" on. Path-based, not domain-based,
# so it generalizes across topics instead of hardcoding one industry's sites.
_EDITORIAL_PATH_HINTS = ("/review", "/news/", "/article/", "/blog/", "/haberler/", "/yorum/")


def _domain(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "").lower()


def _looks_commercial(url: str) -> bool:
    domain = _domain(url)
    if not domain or domain in _NON_COMMERCE_DOMAINS:
        return False
    path = urlparse(url).path.lower()
    return not any(hint in path for hint in _EDITORIAL_PATH_HINTS)


def _dedupe_by_domain(results: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out = []
    for r in results:
        domain = _domain(r.get("url", ""))
        if domain and domain not in seen:
            seen.add(domain)
            out.append(r)
    return out


def _is_try(price: str) -> bool:
    return "TL" in price.upper() or "₺" in price


def _format_price(query: str, gemini_text: str, ddg_results: list[dict]) -> tuple[str, str]:
    """Returns (spoken_summary, full_panel_text)."""
    candidates = [r for r in _dedupe_by_domain(ddg_results)
                  if r.get("url") and _looks_commercial(r["url"])]

    priced, unpriced = [], []
    for r in candidates:
        price = _extract_price(r.get("snippet", "")) or _extract_price(r.get("title", ""))
        (priced if price else unpriced).append({**r, "price": price} if price else r)

    # Region-local currency (TL) first — that's the whole point of region-biasing —
    # then everything else, each group cheapest-first. Never compare TL to $/€ by
    # raw number: 49000 TL and $599 aren't the same magnitude of "cheap".
    try_offers = sorted((o for o in priced if _is_try(o["price"])), key=lambda o: _price_value(o["price"]))
    other_offers = sorted((o for o in priced if not _is_try(o["price"])), key=lambda o: _price_value(o["price"]))
    offers = try_offers + other_offers

    panel = [f"💰 FİYAT KARŞILAŞTIRMA — {query}", ""]
    if gemini_text:
        panel += [gemini_text, ""]
    if offers:
        panel.append("Bulunan teklifler:")
        for i, o in enumerate(offers[:6], 1):
            panel.append(f"{i}. {_domain(o['url'])} — {o['price']}")
            panel.append(f"   {o['url']}")
    if unpriced:
        panel.append("")
        panel.append("Diğer ilgili siteler (fiyat için tıklayın):")
        for r in unpriced[:4]:
            panel.append(f"• {_domain(r['url'])} — {r['url']}")
    panel_text = "\n".join(panel).strip()

    cheapest = try_offers[0] if try_offers else (offers[0] if offers else None)
    if cheapest:
        spoken = f"En ucuz seçenek {_domain(cheapest['url'])} üzerinde {cheapest['price']}. Tüm teklifleri ekranda gösteriyorum efendim."
    elif gemini_text:
        spoken = gemini_text[:400]
    elif unpriced:
        spoken = f"Kesin fiyat bulamadım ama {_domain(unpriced[0]['url'])} üzerinde ürünü buldum, detayları ekranda gösteriyorum efendim."
    else:
        spoken = f"'{query}' için fiyat bulamadım efendim."
    return spoken, panel_text or f"'{query}' için sonuç bulunamadı."


def _format_general(query: str, gemini_text: str, ddg_all: list[dict]) -> tuple[str, str]:
    sources = _dedupe_by_domain(ddg_all)[:6]

    panel = [f"🔎 DERİN ARAMA — {query}", ""]
    if gemini_text:
        panel += [gemini_text, ""]
    if sources:
        panel.append("Kaynaklar:")
        for s in sources:
            if s.get("title"):
                panel.append(f"• {s['title']}")
            if s.get("url"):
                panel.append(f"  {s['url']}")
    panel_text = "\n".join(panel).strip()

    if gemini_text:
        spoken = gemini_text[:500]
    elif sources:
        spoken = sources[0].get("snippet", "")[:400] or "Sonuçları ekranda gösteriyorum efendim."
    else:
        spoken = f"'{query}' hakkında bir şey bulamadım efendim."
    return spoken, panel_text or f"'{query}' için sonuç bulunamadı."


# ── entry point ───────────────────────────────────────────────────────────

def run(parameters: dict, player=None, session_memory=None) -> str:
    params = parameters or {}
    query = (params.get("query") or "").strip()
    kind = (params.get("kind") or "general").strip().lower()
    if kind not in ("price", "general"):
        kind = "general"
    region_name = (params.get("region") or "").strip() or _DEFAULT_REGION_NAME
    region_code = _region_code(region_name)

    if not query:
        return "Ne aramamı istediğinizi söyler misiniz efendim?"

    from core.gemini_keys import all_keys
    has_gemini = bool(all_keys())

    if player:
        player.write_log(f"[DeepSearch:{kind}] {query} (region={region_name})")
    print(f"[DeepSearch] 🔍 kind={kind!r} query={query!r} region={region_name!r}")

    out: dict = {}
    threads = []
    if has_gemini:
        threads.append(threading.Thread(target=_agent_gemini, args=(query, kind, region_name, out), daemon=True))
    threads.append(threading.Thread(target=_agent_ddg_local, args=(query, kind, region_code, out), daemon=True))
    threads.append(threading.Thread(target=_agent_ddg_global, args=(query, kind, out), daemon=True))

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15.0)

    gemini_text = out.get("gemini", "")
    ddg_all = (out.get("ddg_local") or []) + (out.get("ddg_global") or [])

    try:
        if kind == "price":
            spoken, panel_text = _format_price(query, gemini_text, ddg_all)
        else:
            spoken, panel_text = _format_general(query, gemini_text, ddg_all)
    except Exception as e:
        return f"Sir, deep_search couldn't put the results together: {e}"

    if player:
        try:
            title = "💰 FİYAT SONUÇLARI" if kind == "price" else "🔎 ARAMA SONUÇLARI"
            player.show_content(title, panel_text)
        except Exception:
            pass

    return spoken
