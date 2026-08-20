"""
Swarm Researcher — fills missing form insights across ALL Betway regions
(USA, Japan, South Africa, etc.) and polls free horse-racing news feeds.

Two workloads, one loop:
  A. Form backfill   — every runner missing Betway `timeForm` gets a deterministic
                       field blurb (zero cost) upgraded to a web-grounded Groq
                       summary for priority runners (aiSelections / movers /
                       short-priced). Persisted to Chroma racing_insights.
  B. News poller     — polls BBC/Guardian/Mirror RSS feeds, normalises, dedupes,
                       and writes data/news_latest.json. No LLM calls on news
                       (headlines + snippets used verbatim).

Budget guards (no wasted calls):
  - Chroma freshness gate: insights from today are never regenerated.
  - Groq capped to MAX_GROQ_PER_CYCLE, only for gated runners, cached by horse+date.
  - Web search cached (maf_search:{query}) and only issued for gated runners.
"""

import asyncio
import hashlib
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from core_agent.skills.memory.curated_memory import curated_memory

logger = logging.getLogger("swarm-researcher")

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
NEWS_PATH = os.path.join(DATA_DIR, "news_latest.json")
SWARM_INSIGHTS_PATH = os.path.join(DATA_DIR, "swarm_insights.json")
NEWS_IMAGES_DIR = os.path.join(DATA_DIR, "news_images")

# Max Groq calls per researcher cycle (strict budget).
MAX_GROQ_PER_CYCLE = 6
# Only runners at or under this odds are candidates for web grounding.
WEB_GROUND_ODDS_CAP = 6.0
# Resolve extended odds like "6/1" / "9.0" into a float.
_ODDS_RE = re.compile(r"^(\d+(?:\.\d+)?)/(\d+)$")

RSS_FEEDS = [
    {
        "source": "BBC Sport",
        "region": "UK/IRE",
        "url": "https://feeds.bbci.co.uk/sport/horse-racing/rss.xml",
    },
    {
        "source": "The Guardian",
        "region": "UK/IRE",
        "url": "https://www.theguardian.com/sport/horseracing/rss",
    },
    {
        "source": "Daily Mirror",
        "region": "UK/IRE",
        "url": "https://www.mirror.co.uk/sport/horse-racing/rss.xml",
    },
]

REGION_PREFIXES = {
    "USA": ("usa", "united states", "north america"),
    "Japan": ("japan", "jpn", "nagoya", "kawasaki"),
    "South Africa": ("south africa", "sa:", "zaf", "turffontein", "fairview", "greyville", "kenilworth", "vaal", "scottsville", "durbanville", "flamingo"),
    "UK/IRE": ("uk", "ireland", "ire", "gb", "britain"),
    "Australia": ("australia", "aus", "royal randwick", "flemington", "caulfield", "moonee"),
    "New Zealand": ("new zealand", "nz:", "nzl", "ellerslie", "trentham", "riccarton", "avondale", "hastings", "te rapa"),
    "France": ("france", "fra", "longchamp", "chantilly", "auteuil", "deauville"),
    "Hong Kong": ("hong kong", "hkg", "sh tin", "sha tin", "happy valley"),
    "UAE": ("uae", "dubai", "meydan", "jebel ali"),
}


def _norm_date(ts: str) -> str:
    """YYYY-MM-DD from RFC-822-ish timestamps or ISO."""
    try:
        from email.utils import parsedate_to_datetime
        d = parsedate_to_datetime(ts)
        return d.strftime("%Y-%m-%d")
    except Exception:
        return ts[:10] if isinstance(ts, str) else ""


def _odds_float(o: Any) -> Optional[float]:
    """Parse a runner odds value (number, '6/1', '9.0', 'SP') to float."""
    if o is None:
        return None
    if isinstance(o, (int, float)):
        return float(o)
    s = str(o).strip().lower()
    if s in ("sp", "", "n/a"):
        return None
    m = _ODDS_RE.match(s)
    if m:
        num, den = float(m.group(1)), float(m.group(2))
        return num / den + 1.0 if den else None
    try:
        return float(s)
    except ValueError:
        return None


def _detect_region(event: Dict) -> str:
    """Region from the event's display name ('USA: Saratoga') or course name."""
    hay = f"{event.get('en', '')} {event.get('course', '')}".strip().lower()
    for region, keys in REGION_PREFIXES.items():
        if any(k in hay for k in keys):
            return region
    return "Unknown"


def _clean_form(form: str) -> str:
    if not form:
        return ""
    return re.sub(r"[^0-9A-Za-z\-]", "", str(form))


def build_field_insight(runner: Dict) -> str:
    """Deterministic, zero-cost insight from a runner's live fields. Never fabricates."""
    name = runner.get("name") or "runner"
    bits = [name]

    form = _clean_form(runner.get("form") or "")
    if form:
        placed = sum(1 for c in form if c in "123")
        total = sum(1 for c in form if c.isdigit())
        if total:
            bits.append(f"form {form} ({placed}/{total} placed in last {total})")
        else:
            bits.append(f"form {form}")

    if isinstance(runner.get("draw"), (int, float)):
        bits.append(f"draw {runner['draw']}")
    age = (runner.get("age") or "").replace(" years", "yo").replace(" year", "yo")
    wgt = runner.get("weight") or ""
    meta = " ".join(x for x in (wgt, age) if x)
    if meta:
        bits.append(meta)
    jockey = runner.get("jockeyName") or ""
    trainer = runner.get("trainerName") or ""
    if jockey:
        bits.append(f"jockey {jockey}")
    if trainer:
        bits.append(f"trainer {trainer}")

    odds = _odds_float(runner.get("odds"))
    if odds:
        bits.append(f"current price {odds:g}")

    if len(bits) == 1:
        return f"{name} — no additional live data available."
    return ", ".join(bits)


async def _groq_call(prompt: str, max_tokens: int = 220, temperature: float = 0.2) -> str:
    """Reuse dreamer's Groq plumbing for a cheap factual summarisation call."""
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return ""
    try:
        from core_agent.core.http_client import get_async_client
        client = get_async_client(timeout=12.0, resolve_hosts={"api.groq.com"})
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "openai/gpt-oss-20b",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        if resp.status_code != 200:
            logger.warning(f"Groq swarm call failed: status {resp.status_code}")
            return ""
        data = resp.json()
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        if not content:
            content = (data.get("choices") or [{}])[0].get("message", {}).get("reasoning") or ""
        return content.strip()[:400]
    except Exception as e:
        logger.warning(f"Groq swarm call error: {e}")
        return ""


async def _web_ground(horse: str, course: str, region: str) -> str:
    """Cached web search for a priority runner. Returns snippet facts or ''."""
    try:
        from core_agent.tools.maf_tool_registry import search_racing_data
        result = await search_racing_data(
            f"{horse} {course} horse racing form preview", limit=2
        )
        results = result.get("results", [])
        if not results:
            return ""
        snippets = []
        for r in results[:2]:
            snip = (r.get("snippet") or r.get("title") or "").strip()
            if snip:
                snippets.append(snip[:200])
        return " | ".join(snippets)[:500]
    except Exception as e:
        logger.debug(f"Web ground failed for {horse}: {e}")
        return ""


def _fresh_insight_exists(horse: str, course: str, region: str) -> bool:
    """Chroma freshness gate — skip today's already-built insights."""
    try:
        from core_agent.core.strike_brain import brain
        if not (brain and brain.memory and brain.memory._is_ready):
            return False
        results = brain.memory.search_form_insights(
            f"{horse} {course}",
            n_results=3,
            where={"type": "racing_insight", "region": region},
        )
        today = datetime.now().strftime("%Y-%m-%d")
        for r in results:
            meta = r.get("metadata") or {}
            if meta.get("horse", "").lower() == horse.lower() and str(meta.get("ts", ""))[:10] == today:
                return True
        return False
    except Exception:
        return False


def save_racing_insight(horse: str, insight: str, metadata: Dict) -> bool:
    """Central writer — Chroma racing_insight + agent note. Idempotent by horse+date."""
    try:
        from core_agent.core.strike_brain import brain
        if not (brain and brain.memory and brain.memory._is_ready):
            return False
        ok = brain.memory.add_form_insight(
            horse=horse,
            insight=insight,
            metadata=metadata,
        )
        if ok and metadata.get("type") == "racing_insight":
            try:
                region = metadata.get("region", "")
                source = metadata.get("source", "")
                date = str(metadata.get("ts", ""))[:10]
                curated_memory.append_agent_note(
                    f"[{date}] Racing insight saved ({region}/{source}): {horse}"
                )
            except Exception:
                pass
        return bool(ok)
    except Exception as e:
        logger.warning(f"Save racing insight failed: {e}")
        return False


def load_swarm_insights() -> Dict:
    if os.path.exists(SWARM_INSIGHTS_PATH):
        try:
            with open(SWARM_INSIGHTS_PATH) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_swarm_insights(data: Dict) -> None:
    tmp = SWARM_INSIGHTS_PATH + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, SWARM_INSIGHTS_PATH)
    except Exception as e:
        logger.warning(f"Failed to write swarm_insights: {e}")


def enrich_snapshot_with_insights(state: Dict) -> None:
    """Inline, zero-cost enrichment for every runner missing Betway timeForm.

    Any runner without timeForm prose gets a deterministic field blurb instantly.
    Pre-existing swarm/web insights (keyed by outcomeId) take priority.
    """
    swarm = load_swarm_insights()
    for eid, event in state.get("events", {}).items():
        region = _detect_region(event)
        for runner in event.get("runners", []):
            if not runner.get("timeForm"):
                oid = str(runner.get("outcomeId") or "")
                existing = swarm.get(oid) or {}
                runner["region"] = region
                runner["swarmInsight"] = (
                    existing.get("insight")
                    or build_field_insight(runner)
                )
                runner["insightSource"] = (
                    existing.get("source") or "field_only"
                )
                runner["insightTs"] = existing.get("ts") or datetime.now().isoformat()


async def backfill_form_insights(state: Dict) -> int:
    """Pass A — build/upgrade form insights for ALL regions without timeForm.

    Returns number of Groq calls made (for logging / budget tracking).
    """
    swarm = load_swarm_insights()
    groq_calls = 0
    gated = []

    for event in state.get("events", {}).values():
        region = _detect_region(event)
        course = event.get("course", "")
        for runner in event.get("runners", []):
            if runner.get("timeForm"):
                continue  # Betway already covers this one
            oid = str(runner.get("outcomeId") or "")
            name = runner.get("name", "")
            odds = _odds_float(runner.get("odds")) or 999.0

            # Already upgraded today? skip.
            existing = swarm.get(oid)
            if existing and str(existing.get("ts", ""))[:10] == datetime.now().strftime("%Y-%m-%d"):
                continue

            field = build_field_insight(runner)
            if _fresh_insight_exists(name, course, region):
                swarm[oid] = {"source": "chroma", "insight": field, "ts": datetime.now().isoformat(), "region": region}
                continue

            # Baseline field blurb is always persisted immediately (zero cost).
            if not existing:
                swarm[oid] = {"source": "field_only", "insight": field, "ts": datetime.now().isoformat(), "region": region}

            # Gate: only priority runners get web grounding + Groq.
            if odds <= WEB_GROUND_ODDS_CAP:
                gated.append((oid, name, course, region, field))

    # Process gated runners — strict budget cap, newest first.
    gated.sort(key=lambda g: g[1])
    for oid, name, course, region, field in gated[:MAX_GROQ_PER_CYCLE]:
        facts = await _web_ground(name, course, region)
        if not facts:
            continue
        prompt = (
            "Horse racing analyst. Build ONE concise factual insight from the text below.\n"
            f"Horse: {name} | Track: {course} | Region: {region}\n"
            f"Local data: {field}\n"
            f"Web facts: {facts}\n"
            "Output 1-2 sentences of facts only. No speculation, no odds advice, no fluff."
        )
        summary = await _groq_call(prompt)
        groq_calls += 1
        if summary:
            swarm[oid] = {
                "source": "web",
                "insight": summary,
                "field": field,
                "ts": datetime.now().isoformat(),
                "region": region,
            }
            save_racing_insight(
                name,
                insight=f"[{name} @ {course}] {summary}",
                metadata={
                    "type": "racing_insight",
                    "horse": name,
                    "course": course,
                    "region": region,
                    "source": "web",
                    "ts": datetime.now().isoformat(),
                },
            )
            logger.info(f"[SWARM] Web-grounded insight: {name} ({region})")

    save_swarm_insights(swarm)
    return groq_calls


# ── News (Pass B) ────────────────────────────────────────────────────────────

_MRSS = {"media": "http://search.yahoo.com/mrss/", "content": "http://purl.org/rss/1.0/modules/content/"}


def _feed_image(item, ns) -> str:
    """Best-guess image URL from item media elements (media:thumbnail/content)."""
    for tag in ("thumbnail", "content"):
        el = item.find(f"media:{tag}", ns)
        if el is not None:
            url = el.get("url") or el.get("medium")
            if url:
                return url
    return ""


def _parse_feed(xml_text: str, source: str, region: str) -> List[Dict]:
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_text)
    items = []
    for it in root.findall(".//item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        if not title or not link:
            continue
        items.append({
            "id": hashlib.sha1(link.encode()).hexdigest()[:12],
            "title": title[:200],
            "url": link,
            "source": source,
            "region": region,
            "summary": (it.findtext("description") or "")[:400],
            "image_url": _feed_image(it, _MRSS),
            "published": it.findtext("pubDate") or "",
        })
    return items


async def _fetch_feed(feed: Dict) -> List[Dict]:
    try:
        from core_agent.core.http_client import get_async_client
        client = get_async_client(timeout=15.0)
        resp = await client.get(feed["url"], headers={"User-Agent": "StrikeTips/1.0 (+racing research)"})
        if resp.status_code != 200:
            logger.debug(f"Feed {feed['source']} returned {resp.status_code}")
            return []
        return _parse_feed(resp.text, feed["source"], feed["region"])
    except Exception as e:
        logger.debug(f"Feed {feed['source']} failed: {e}")
        return []


async def poll_news() -> int:
    """Pass B — poll feeds, dedupe, cap, persist data/news_latest.json. Returns new count."""
    all_items: List[Dict] = []
    for feed in RSS_FEEDS:
        all_items.extend(await _fetch_feed(feed))

    seen = set()
    deduped = []
    for it in all_items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        deduped.append(it)
    deduped.sort(key=lambda x: x.get("published") or "", reverse=True)
    deduped = deduped[:50]

    prev = []
    if os.path.exists(NEWS_PATH):
        try:
            with open(NEWS_PATH) as f:
                prev = json.load(f)
        except Exception:
            prev = []
    prev_ids = {it.get("id") for it in prev}
    new_ids = {it.get("id") for it in deduped}
    new_count = len(new_ids - prev_ids)

    tmp = NEWS_PATH + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(deduped, f, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, NEWS_PATH)
    except Exception as e:
        logger.warning(f"Failed to write news: {e}")
        return 0

    if new_count:
        logger.info(f"[SWARM] News polled: {len(deduped)} items, {new_count} new")
    return new_count


async def run_swarm_loop(interval: int = 600):
    """Background loop — form backfill + news polling every `interval` seconds."""
    logger.info(f"🚦 Swarm researcher started (interval: {interval}s)")
    while True:
        try:
            from core_agent.core.snapshot_cache import get_snapshot
            snap = get_snapshot() or {}
            if snap.get("events"):
                groq_used = await backfill_form_insights(snap)
                if groq_used:
                    logger.info(f"[SWARM] Form backfill used {groq_used} Groq calls")
            await poll_news()
        except Exception as e:
            logger.warning(f"Swarm cycle failed: {e}")
        await asyncio.sleep(interval)