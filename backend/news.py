import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html import unescape
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit

import feedparser
import httpx
from fastapi import HTTPException
from pydantic import BaseModel

BBC_FEEDS = {
    "Geral": "https://feeds.bbci.co.uk/news/rss.xml",
    "Mundo": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "Tecnologia": "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "Negócios": "https://feeds.bbci.co.uk/news/business/rss.xml",
    "Ciência e ambiente": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
}
BBC_HOSTS = {"bbc.com", "www.bbc.com", "bbc.co.uk", "www.bbc.co.uk"}
logger = logging.getLogger(__name__)
cache_lock = Lock()
cached_articles: list["Article"] = []
cached_until = 0.0


class Article(BaseModel):
    url: str
    title: str
    summary: str = ""
    category: str = ""
    published: datetime | None = None
    image_url: str | None = None


def is_bbc_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return parsed.scheme == "https" and parsed.netloc.lower() in BBC_HOSTS and bool(parsed.path.strip("/"))
    except ValueError:
        return False


def article_key(url: str) -> str:
    # The BBC uses the same path on its regional domains and adds RSS tracking parameters.
    try:
        parsed = urlsplit(url)
        if parsed.netloc.lower() in BBC_HOSTS:
            return parsed.path.rstrip("/")
    except ValueError:
        pass
    return url


def fetch_feed(item: tuple[str, str]) -> list[Article]:
    category, url = item
    try:
        response = httpx.get(url, timeout=7, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Feed da BBC indisponível (%s): %s", category, exc)
        return []

    articles = []
    for entry in feedparser.parse(response.content).entries:
        link = entry.get("link", "")
        title = unescape(entry.get("title", "")).strip()
        if not title or not is_bbc_url(link):
            continue

        summary = unescape(re.sub(r"<[^>]*>", "", entry.get("summary", ""))).strip()
        date = entry.get("published_parsed")
        published = datetime(*date[:6], tzinfo=timezone.utc) if date else None
        thumbnails = entry.get("media_thumbnail") or []
        image_url = thumbnails[0].get("url", "") if thumbnails else ""
        if not image_url.startswith("https://ichef.bbci.co.uk/"):
            image_url = None
        articles.append(Article(
            url=link, title=title, summary=summary, category=category,
            published=published, image_url=image_url,
        ))

    return articles


def latest_articles() -> list[Article]:
    global cached_articles, cached_until
    with cache_lock:
        if monotonic() < cached_until:
            return cached_articles

        with ThreadPoolExecutor(max_workers=len(BBC_FEEDS)) as executor:
            feeds = list(executor.map(fetch_feed, BBC_FEEDS.items()))

        # Prefer the topical feed when a headline also appears in the general feed.
        unique = {}
        for feed in reversed(feeds):
            for article in feed:
                unique.setdefault(article_key(article.url), article)

        if unique:
            cached_articles = sorted(
                unique.values(), key=lambda article: article.published or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True,
            )
            cached_until = monotonic() + 300
        elif cached_articles:
            cached_until = monotonic() + 30
        else:
            raise HTTPException(503, "Não foi possível carregar os feeds da BBC. Tente novamente.")

        return cached_articles
