import asyncio
import logging
import re
import time
from html import unescape

import feedparser
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_USER_AGENT = "NarrativeTracker/1.0 (financial media research tool)"
# Reddit blocks its anonymous JSON endpoints (www and api.reddit.com) for
# non-browser clients, but still serves the Atom feed to a browser User-Agent.
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
_WWW = "https://www.reddit.com"
_OAUTH = "https://oauth.reddit.com"
_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
# Stay well under Reddit's limits (100/min authenticated, far less anonymous).
_REQUEST_DELAY = 1.2

_token_cache: dict = {"token": None, "expires_at": 0.0}
_TAG_RE = re.compile(r"<[^>]+>")


def _configured() -> bool:
    return bool(settings.reddit_client_id and settings.reddit_client_secret)


def _html_to_text(html: str) -> str:
    text = _TAG_RE.sub(" ", html or "")
    return re.sub(r"\s+", " ", unescape(text)).strip()


# --- official API (preferred) --------------------------------------------------


async def _bearer(client: httpx.AsyncClient) -> str:
    if _token_cache["token"] and time.monotonic() < _token_cache["expires_at"] - 60:
        return _token_cache["token"]
    resp = await client.post(
        _TOKEN_URL,
        data={"grant_type": "client_credentials"},
        auth=(settings.reddit_client_id, settings.reddit_client_secret),
        headers={"User-Agent": _USER_AGENT},
        timeout=20.0,
    )
    resp.raise_for_status()
    payload = resp.json()
    _token_cache.update(token=payload["access_token"], expires_at=time.monotonic() + float(payload.get("expires_in", 3600)))
    return _token_cache["token"]


async def _api_get(client: httpx.AsyncClient, path: str) -> dict | list:
    await asyncio.sleep(_REQUEST_DELAY)
    token = await _bearer(client)
    resp = await client.get(
        f"{_OAUTH}{path}",
        headers={"User-Agent": _USER_AGENT, "Authorization": f"Bearer {token}"},
        timeout=20.0,
    )
    resp.raise_for_status()
    return resp.json()


async def _fetch_via_api(subreddit: str, limit: int) -> list[dict]:
    async with httpx.AsyncClient() as client:
        data = await _api_get(client, f"/r/{subreddit}/hot?limit={limit}&raw_json=1")
        results = []
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            if post.get("stickied"):
                continue
            post_id = post.get("id", "")
            title = post.get("title", "")
            body = (post.get("selftext") or "").strip()
            permalink = post.get("permalink", "")

            comments_text = ""
            try:
                listing = await _api_get(client, f"/r/{subreddit}/comments/{post_id}?limit=20&depth=1&sort=top&raw_json=1")
                top = []
                for c in listing[1].get("data", {}).get("children", []):
                    text = (c.get("data", {}).get("body") or "").strip()
                    if text and text not in ("[deleted]", "[removed]"):
                        top.append(text)
                    if len(top) >= 10:
                        break
                if top:
                    comments_text = "\n\n".join(f"Comment: {c}" for c in top)
            except Exception:
                logger.warning("Failed to fetch comments for post %s", post_id)

            parts = [f"Title: {title}"]
            if body:
                parts.append(f"Post: {body}")
            if comments_text:
                parts.append(comments_text)
            results.append({"title": title, "url": f"{_WWW}{permalink}", "text": "\n\n".join(parts)})
        return results


# --- Atom feed fallback ---------------------------------------------------------


async def _fetch_via_feed(subreddit: str, limit: int) -> list[dict]:
    """Title + self-text only; Reddit's feed carries no comments. Still enough for
    the extraction pass to pull tickers and a sentiment read."""
    await asyncio.sleep(_REQUEST_DELAY)
    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.get(
            f"{_WWW}/r/{subreddit}/hot.rss?limit={limit}",
            headers={"User-Agent": _BROWSER_UA, "Accept": "application/atom+xml,application/xml;q=0.9,*/*;q=0.8"},
            timeout=20.0,
        )
        resp.raise_for_status()
    feed = feedparser.parse(resp.text)

    results = []
    for entry in feed.entries[:limit]:
        title = (entry.get("title") or "").strip()
        link = entry.get("link") or ""
        if not title or not link:
            continue
        html = ""
        if entry.get("content"):
            html = entry["content"][0].get("value", "")
        elif entry.get("summary"):
            html = entry["summary"]
        body = _html_to_text(html)
        # The feed body ends with Reddit's boilerplate link row; drop it.
        body = re.sub(r"\s*submitted by\s+/u/\S+.*$", "", body, flags=re.IGNORECASE).strip()
        parts = [f"Title: {title}"]
        if body:
            parts.append(f"Post: {body}")
        results.append({"title": title, "url": link.split("?")[0], "text": "\n\n".join(parts)})
    return results


async def fetch_hot_posts(subreddit: str, limit: int = 10) -> list[dict]:
    """Return up to `limit` hot posts from the subreddit as {title, url, text}.
    Uses the official API when credentials are configured (posts + top comments),
    else the public Atom feed (posts only)."""
    if _configured():
        try:
            return await _fetch_via_api(subreddit, limit)
        except Exception:
            logger.exception("Reddit API fetch failed for r/%s; falling back to the Atom feed", subreddit)
    return await _fetch_via_feed(subreddit, limit)
