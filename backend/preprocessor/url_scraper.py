"""
TruthShield — URL Scraper
Web page scraping with BeautifulSoup — extract article text, metadata, images.
"""

import logging
import re
from typing import Optional
from urllib.parse import urlparse

from backend.models.schemas import ContentPacket, ContentType, Language

logger = logging.getLogger(__name__)


class URLScraper:
    """Scrape web pages for article text, images, and metadata."""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    def scrape(self, url: str) -> dict:
        """
        Scrape a URL and extract article content.

        Returns:
            dict with 'text', 'title', 'og_image', 'domain', 'meta_description'
        """
        try:
            import requests
            from bs4 import BeautifulSoup

            response = requests.get(url, headers=self.HEADERS, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Extract title
            title = ""
            if soup.title:
                title = soup.title.string or ""
            og_title = soup.find("meta", property="og:title")
            if og_title:
                title = og_title.get("content", title)

            # Extract og:image
            og_image = None
            og_img_tag = soup.find("meta", property="og:image")
            if og_img_tag:
                og_image = og_img_tag.get("content")

            # Extract meta description
            meta_desc = ""
            desc_tag = soup.find("meta", attrs={"name": "description"})
            if desc_tag:
                meta_desc = desc_tag.get("content", "")

            # ── Strip ALL junk elements from the entire page first ──
            junk_tags = [
                "script", "style", "nav", "footer", "header", "aside",
                "iframe", "noscript", "svg", "form", "button", "figure",
                "ul", "ol", "menu", "canvas"  # Added ul/ol to remove typical nav lists
            ]
            for tag in soup.find_all(junk_tags):
                tag.decompose()

            # Remove junk by class/id patterns (ads, nav, social, cookie, etc.)
            junk_patterns = re.compile(
                r"(nav|menu|sidebar|footer|header|banner|advert|cookie|consent|"
                r"social|share|comment|related|recommend|popup|modal|overlay|"
                r"breadcrumb|widget|signup|subscribe|newsletter|promo|"
                r"partner.?site|site.?map|disclaimer|copyright|taboola|outbrain)",
                re.IGNORECASE,
            )
            for el in soup.find_all(attrs={"class": True}):
                if el.attrs is None:  # Skip already decomposed elements
                    continue
                classes = el.get("class", [])
                classes_str = " ".join(classes) if isinstance(classes, list) else str(classes)
                if junk_patterns.search(classes_str):
                    el.decompose()
                    
            for el in soup.find_all(attrs={"id": True}):
                if el.attrs is None:
                    continue
                if junk_patterns.search(el.get("id", "")):
                    el.decompose()

            # ── Extract article text from best container ──
            article_text = ""
            content_selectors = [
                "article .story-content",
                "article .article-body",
                "article .story-body",
                ".post-content",
                ".entry-content",
                ".article-content",
                ".story-content",
                ".content-body",
                '[itemprop="articleBody"]',
                '[data-article-body]',
                "article",
                "main",
                '[role="main"]',
                ".main-content",
            ]

            for selector in content_selectors:
                container = soup.select_one(selector)
                if container:
                    # Get only paragraph and heading text from the container
                    parts = []
                    for el in container.find_all(["p", "h1", "h2", "h3", "blockquote", "li"]):
                        text = el.get_text(strip=True)
                        if len(text) > 20:  # Skip short fragments
                            parts.append(text)
                    if len(parts) >= 2:  # Need at least 2 substantial paragraphs
                        article_text = "\n\n".join(parts)
                        break

            if not article_text:
                # Fallback: get all paragraph text with strict length filter
                paragraphs = soup.find_all("p")
                good_paras = [
                    p.get_text(strip=True)
                    for p in paragraphs
                    if len(p.get_text(strip=True)) > 50  # Strict: skip short junk
                ]
                article_text = "\n\n".join(good_paras)

            # Clean up text
            article_text = re.sub(r"\n{3,}", "\n\n", article_text).strip()
            # Remove runs of whitespace within lines
            article_text = re.sub(r"[ \t]{3,}", " ", article_text)

            domain = urlparse(url).netloc

            return {
                "text": article_text,
                "title": title.strip(),
                "og_image": og_image,
                "domain": domain,
                "meta_description": meta_desc,
                "url": url,
            }

        except Exception as e:
            logger.error(f"URL scraping failed for {url}: {e}")
            return {
                "text": "",
                "title": "",
                "og_image": None,
                "domain": urlparse(url).netloc,
                "meta_description": "",
                "url": url,
                "error": str(e),
            }

    def process(self, url: str, lang_hint: Optional[str] = None) -> ContentPacket:
        """
        Process a URL into a ContentPacket.

        Args:
            url: The URL to scrape
            lang_hint: Optional language hint

        Returns:
            ContentPacket with scraped text and metadata
        """
        scraped = self.scrape(url)

        # Detect language from scraped text
        from backend.preprocessor.text_processor import TextProcessor
        if scraped["text"]:
            lang = TextProcessor.detect_language(scraped["text"])
        else:
            lang = Language(lang_hint) if lang_hint else Language.EN

        image_paths = []
        if scraped.get("og_image"):
            image_paths = [scraped["og_image"]]

        logger.info(f"URL processed: {scraped['domain']}, {len(scraped['text'])} chars")

        return ContentPacket(
            content_type=ContentType.URL,
            text=scraped["text"] or None,
            lang=lang,
            source_url=url,
            image_paths=image_paths,
            metadata={
                "title": scraped["title"],
                "domain": scraped["domain"],
                "og_image": scraped.get("og_image"),
                "meta_description": scraped["meta_description"],
                "has_error": "error" in scraped,
            },
        )
