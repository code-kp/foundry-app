from __future__ import annotations

import json
import re
from html import unescape
from html.parser import HTMLParser
from typing import Dict, List, Tuple
from urllib.parse import parse_qs, quote_plus, urlparse, unquote
from urllib.request import Request, urlopen

from core.interfaces.tools import current_progress, tool


DEFAULT_TIMEOUT_SECONDS = 12
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
SCRIPT_STYLE_RE = re.compile(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>")
TAG_RE = re.compile(r"(?s)<[^>]+>")
TITLE_RE = re.compile(r"(?is)<title[^>]*>(?P<title>.*?)</title>")
WHITESPACE_RE = re.compile(r"\s+")


class _DuckDuckGoResultsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: List[Dict[str, str]] = []
        self._current: Dict[str, str] | None = None
        self._capture_title = False
        self._capture_snippet = False

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())

        if tag == "a" and "result__a" in classes:
            self._finalize_current()
            href = _resolve_result_url(attributes.get("href", ""))
            self._current = {"title": "", "url": href, "snippet": ""}
            self._capture_title = True
            self._capture_snippet = False
            return

        if self._current and "result__snippet" in classes:
            self._capture_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._capture_title:
            self._capture_title = False
            return
        if tag in {"a", "div", "span"} and self._capture_snippet:
            self._capture_snippet = False

    def handle_data(self, data: str) -> None:
        if not self._current:
            return
        if self._capture_title:
            self._current["title"] += data
        elif self._capture_snippet:
            self._current["snippet"] += data

    def close(self) -> None:
        super().close()
        self._finalize_current()

    def _finalize_current(self) -> None:
        if not self._current:
            return
        title = _clean_text(self._current.get("title", ""))
        url = self._current.get("url", "").strip()
        snippet = _clean_text(self._current.get("snippet", ""))
        if title and url:
            self.results.append({"title": title, "url": url, "snippet": snippet})
        self._current = None
        self._capture_title = False
        self._capture_snippet = False


@tool(description="Search the public web for recent answers and return concise result snippets.")
def search_web(query: str, max_results: int = 5) -> dict:
    progress = current_progress()
    progress.comment("Searching the web.", query=query, max_results=max_results)

    html = _http_get(
        "https://html.duckduckgo.com/html/?q={query}".format(query=quote_plus(query)),
    )
    results = _parse_duckduckgo_results(html, max_results=max_results)
    if not results:
        results = _search_web_instant_answer(query=query, max_results=max_results)

    progress.comment("Web search completed.", matches=len(results))
    return {"query": query, "results": results}


@tool(description="Fetch a web page and extract readable text for summarization.")
def fetch_web_page(url: str, max_chars: int = 5000) -> dict:
    progress = current_progress()
    progress.comment("Fetching web page.", url=url)
    body = _http_get(url)
    title, content = _extract_page_content(body, max_chars=max_chars)
    progress.comment("Fetched web page.", title=title or "untitled", characters=len(content))
    return {"url": url, "title": title, "content": content}


def _http_get(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _search_web_instant_answer(query: str, max_results: int) -> List[Dict[str, str]]:
    body = _http_get(
        "https://api.duckduckgo.com/?q={query}&format=json&no_redirect=1&no_html=1&skip_disambig=1".format(
            query=quote_plus(query)
        )
    )
    payload = json.loads(body)
    results: List[Dict[str, str]] = []

    abstract_text = _clean_text(payload.get("AbstractText", ""))
    abstract_url = str(payload.get("AbstractURL", "") or "").strip()
    heading = _clean_text(payload.get("Heading", "")) or query
    if abstract_text and abstract_url:
        results.append(
            {
                "title": heading,
                "url": abstract_url,
                "snippet": abstract_text,
            }
        )

    for topic in payload.get("RelatedTopics", []):
        if len(results) >= max_results:
            break
        if isinstance(topic, dict) and "Topics" in topic:
            nested = topic.get("Topics") or []
        else:
            nested = [topic]
        for item in nested:
            if len(results) >= max_results:
                break
            if not isinstance(item, dict):
                continue
            text = _clean_text(item.get("Text", ""))
            url = str(item.get("FirstURL", "") or "").strip()
            if not text or not url:
                continue
            title = text.split(" - ", 1)[0].strip()
            results.append(
                {
                    "title": title or query,
                    "url": url,
                    "snippet": text,
                }
            )
    return results[:max_results]


def _parse_duckduckgo_results(html: str, max_results: int) -> List[Dict[str, str]]:
    parser = _DuckDuckGoResultsParser()
    parser.feed(html)
    parser.close()
    return parser.results[:max_results]


def _extract_page_content(html: str, max_chars: int) -> Tuple[str, str]:
    title_match = TITLE_RE.search(html or "")
    title = _clean_text(title_match.group("title")) if title_match else ""
    stripped = SCRIPT_STYLE_RE.sub(" ", html or "")
    text = _clean_text(TAG_RE.sub(" ", stripped))
    if max_chars > 0 and len(text) > max_chars:
        text = text[: max_chars - 3].rstrip() + "..."
    return title, text


def _resolve_result_url(url: str) -> str:
    candidate = str(url or "").strip()
    if not candidate:
        return ""
    if candidate.startswith("//"):
        candidate = "https:" + candidate
    parsed = urlparse(candidate)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [])
        if target:
            return unquote(target[0])
    return candidate


def _clean_text(value: str) -> str:
    text = unescape(str(value or ""))
    return WHITESPACE_RE.sub(" ", text).strip()


__all__ = ["search_web", "fetch_web_page"]
