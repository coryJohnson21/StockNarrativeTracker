import asyncio
import logging
import httpx

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "NarrativeTracker/1.0 (financial media research tool)"}
_BASE = "https://www.reddit.com"
# Reddit anonymous API: stay well under 1 req/sec to avoid 429s.
_REQUEST_DELAY = 1.2


async def _get(client: httpx.AsyncClient, url: str) -> dict:
    await asyncio.sleep(_REQUEST_DELAY)
    resp = await client.get(url, headers=_HEADERS, timeout=20.0)
    resp.raise_for_status()
    return resp.json()


async def fetch_hot_posts(subreddit: str, limit: int = 10) -> list[dict]:
    """Return up to `limit` hot posts from the subreddit, each with title, body,
    permalink, and top comments concatenated into a single text blob."""
    url = f"{_BASE}/r/{subreddit}/hot.json?limit={limit}"
    async with httpx.AsyncClient() as client:
        data = await _get(client, url)
        posts = data.get("data", {}).get("children", [])

        results = []
        for child in posts:
            post = child.get("data", {})
            # Skip stickied mod posts and link posts with no body
            if post.get("stickied"):
                continue

            post_id = post.get("id", "")
            title = post.get("title", "")
            body = post.get("selftext", "").strip()
            permalink = post.get("permalink", "")
            url_hint = post.get("url", "")

            # Fetch top comments
            comments_text = ""
            try:
                comments_url = f"{_BASE}/r/{subreddit}/comments/{post_id}.json?limit=20&depth=1&sort=top"
                comments_data = await _get(client, comments_url)
                comment_listing = comments_data[1].get("data", {}).get("children", [])
                top_comments = []
                for c in comment_listing:
                    cdata = c.get("data", {})
                    text = cdata.get("body", "").strip()
                    if text and text != "[deleted]" and text != "[removed]":
                        top_comments.append(text)
                    if len(top_comments) >= 10:
                        break
                if top_comments:
                    comments_text = "\n\n".join(f"Comment: {c}" for c in top_comments)
            except Exception:
                logger.warning(f"Failed to fetch comments for post {post_id}")

            parts = [f"Title: {title}"]
            if body:
                parts.append(f"Post: {body}")
            if comments_text:
                parts.append(comments_text)

            results.append({
                "title": title,
                "url": f"{_BASE}{permalink}",
                "text": "\n\n".join(parts),
            })

        return results
