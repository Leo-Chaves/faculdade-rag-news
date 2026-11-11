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
    "Economia": "https://feeds.bbci.co.uk/news/business/rss.xml",
    "Ciência e ambiente": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
}
BBC_HOSTS = {"bbc.com", "www.bbc.com", "bbc.co.uk", "www.bbc.co.uk"}
AGENCIA_HOST = "agenciabrasil.ebc.com.br"
AGENCIA_CATEGORIES = {
    "meio-ambiente": "Ciência e ambiente",
    "internacional": "Mundo",
    "economia": "Economia",
    "cultura": "Cultura",
    "politica": "Política",
    "educacao": "Educação",
    "saude": "Saúde",
    "esportes": "Esportes",
    "justica": "Justiça",
    "direitos-humanos": "Direitos humanos",
}
NEWS_FEEDS = [
    *(("BBC News", category, url) for category, url in BBC_FEEDS.items()),
    ("Agência Brasil", "Geral", "https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml"),
]
logger = logging.getLogger(__name__)
cache_lock = Lock()
cached_articles: list["Article"] = []
cached_until = 0.0


class Article(BaseModel):
    url: str
    title: str
    summary: str = ""
    category: str = ""
    publisher: str = "BBC News"
    published: datetime | None = None
    image_url: str | None = None


def publisher_for_url(url: str) -> str | None:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return None
    if parsed.scheme != "https" or not parsed.path.strip("/"):
        return None
    host = parsed.netloc.lower()
    if host in BBC_HOSTS:
        return "BBC News"
    if host == AGENCIA_HOST:
        return "Agência Brasil"
    return None


def article_key(url: str) -> str:
    # The BBC uses the same path on its regional domains and adds RSS tracking parameters.
    try:
        parsed = urlsplit(url)
        if parsed.netloc.lower() in BBC_HOSTS:
            return parsed.path.rstrip("/")
        if parsed.netloc.lower() == AGENCIA_HOST:
            return AGENCIA_HOST + parsed.path.rstrip("/")
    except ValueError:
        pass
    return url


def fetch_feed(item: tuple[str, str, str]) -> list[Article]:
    publisher, category, url = item
    try:
        response = httpx.get(url, timeout=7, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Feed indisponível (%s / %s): %s", publisher, category, exc)
        return []

    articles = []
    for entry in feedparser.parse(response.content).entries:
        link = entry.get("link", "")
        title = unescape(entry.get("title", "")).strip()
        if not title or publisher_for_url(link) != publisher:
            continue

        summary = " ".join(unescape(re.sub(r"<[^>]*>", " ", entry.get("summary", ""))).split())
        if len(summary) > 750:
            summary = summary[:750].rsplit(" ", 1)[0] + "…"
        topic = category
        if publisher == "Agência Brasil":
            section = urlsplit(link).path.strip("/").split("/", 1)[0]
            topic = AGENCIA_CATEGORIES.get(section, category)
        date = entry.get("published_parsed")
        published = datetime(*date[:6], tzinfo=timezone.utc) if date else None
        thumbnails = entry.get("media_thumbnail") or []
        image_url = thumbnails[0].get("url", "") if thumbnails else ""
        if not image_url.startswith("https://ichef.bbci.co.uk/"):
            image_url = None
        articles.append(Article(
            url=link, title=title, summary=summary, category=topic, publisher=publisher,
            published=published, image_url=image_url,
        ))

    return articles


def latest_articles() -> list[Article]:
    global cached_articles, cached_until
    with cache_lock:
        if monotonic() < cached_until:
            return cached_articles

        with ThreadPoolExecutor(max_workers=len(NEWS_FEEDS)) as executor:
            feeds = list(executor.map(fetch_feed, NEWS_FEEDS))

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
            raise HTTPException(503, "Não foi possível carregar os feeds de notícias. Tente novamente.")

        return cached_articles
