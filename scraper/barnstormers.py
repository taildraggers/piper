"""Scraper for classic Piper taildragger listings on barnstormers.com.

Pulls directly from eleven Barnstormers category pages - nine of them
dedicated single-model pages (J-3 Cub, J-5 Cub Cruiser, L-4 Cub, PA-11 Cub
Special, PA-15/PA-17 Vagabond, PA-16 Clipper, PA-18 Super Cub, PA-20 Pacer)
plus two broader hub pages ("Piper--Super-Cub" and "Piper--Taildragger").
Following the lesson learned in the Cessna repo - a strict brand/model
allowlist over-filters dedicated model-specific category pages, dropping
lots of genuine, unbranded parts listings - titles are only dropped when
they name a different aircraft manufacturer or an unrelated item, the same
approach used there.
"""
from __future__ import annotations

import re
from urllib.parse import unquote, urljoin

from bs4 import BeautifulSoup

from .common import (
    Listing,
    extract_date,
    extract_location,
    extract_price,
    fetch,
    format_aircraft_title,
)

SITE_NAME = "Barnstormers.com"
BASE = "https://www.barnstormers.com"
MAKE = "Piper"

# Nine dedicated model category pages plus two broader Piper taildragger hubs.
CATEGORY_URLS = [
    f"{BASE}/category-21182-Piper--J-3-Cub.html",
    f"{BASE}/category-21184-Piper--J-5-Cub-Cruiser.html",
    f"{BASE}/category-21185-Piper--L--4-Cub.html",
    f"{BASE}/category-21190-Piper--PA-11-Cub-Special.html",
    f"{BASE}/category-21193-Piper--PA-15-Vagabond.html",
    f"{BASE}/category-21194-Piper--PA-16-Clipper.html",
    f"{BASE}/category-21195-Piper--PA-17-Vagabond.html",
    f"{BASE}/category-21196-Piper--PA-18-Super-Cub.html",
    f"{BASE}/category-21197-Piper--PA-20-Pacer.html",
    f"{BASE}/category-21249-Piper--Super-Cub.html",
    f"{BASE}/category-21250-Piper--Taildragger.html",
]

MAX_PAGES = 10
LISTING_LINK_RE = re.compile(r"^/classified-(\d+)-(.+)\.html$")
GENERIC_SITE_TITLE_SNIPPET = "barnstormers.com find aircraft"

# Other manufacturers/off-topic items observed leaking into similarly
# dedicated Cessna category pages. A title naming one of these is dropped
# even though everything else found in these categories is published
# unfiltered.
OFF_BRAND_PHRASES = [
    "bellanca", "cessna", "aeronca", "luscombe", "stinson", "taylorcraft",
    "beechcraft", "beech", "waco", "champion", "citabria", "decathlon",
    "husky", "cubcrafters", "cub crafters", "carbon cub", "maule", "mooney",
    "cirrus", "grumman", "swift", "ercoupe", "pitts", "christen", "fairchild",
    "aviat", "vans", "helio", "chevelle", "chevy",
]


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[-_]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _is_off_brand(title: str) -> bool:
    normalized = " " + _normalize(title) + " "
    return any((" " + phrase + " ") in normalized for phrase in OFF_BRAND_PHRASES)


# Explicit model designators, most specific first. The prefix and number may
# be separated by a space, a hyphen, or nothing, since _title_from_url()
# turns the source URL's hyphens into spaces.
_MODEL_CODE_RULES = [
    (re.compile(r"\bpa[\s-]?11\b", re.IGNORECASE), "PA-11"),
    (re.compile(r"\bpa[\s-]?15\b", re.IGNORECASE), "PA-15"),
    (re.compile(r"\bpa[\s-]?16\b", re.IGNORECASE), "PA-16"),
    (re.compile(r"\bpa[\s-]?17\b", re.IGNORECASE), "PA-17"),
    (re.compile(r"\bpa[\s-]?18\b", re.IGNORECASE), "PA-18"),
    (re.compile(r"\bpa[\s-]?20\b", re.IGNORECASE), "PA-20"),
    (re.compile(r"\bl[\s-]?4\b", re.IGNORECASE), "L-4"),
    (re.compile(r"\bj[\s-]?3\b", re.IGNORECASE), "J-3"),
    (re.compile(r"\bj[\s-]?5\b", re.IGNORECASE), "J-5"),
]


def _extract_model(title: str) -> tuple[str, str] | None:
    for pattern, canonical in _MODEL_CODE_RULES:
        if pattern.search(title):
            return MAKE, canonical

    # No explicit PA-/J-/L- code found - fall back to common marketing
    # names, most specific first.
    normalized = _normalize(title)
    if re.search(r"\bsuper\s*cub\b", normalized):
        return MAKE, "PA-18"
    if re.search(r"\bcub\s*cruiser\b", normalized):
        return MAKE, "J-5"
    if re.search(r"\bcub\s*special\b", normalized):
        return MAKE, "PA-11"
    if re.search(r"\bclipper\b", normalized):
        return MAKE, "PA-16"
    if re.search(r"\bpacer\b", normalized) and "tri pacer" not in normalized:
        # The Tri-Pacer (PA-22) is a tricycle-gear aircraft, not a
        # taildragger, so it's deliberately excluded from this repo.
        return MAKE, "PA-20"
    if re.search(r"\bvagabond\b", normalized):
        # PA-15 and PA-17 share the Vagabond name and airframe; without an
        # explicit PA number in the title there's no reliable way to tell
        # them apart, so the model is published generically.
        return MAKE, "Vagabond"
    if re.search(r"\bcub\b", normalized):
        return MAKE, "Cub"
    return None


def _title_from_url(url: str) -> str:
    """Listing pages share a generic <title>/<h1>, but the URL slug is the ad's own title."""
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    match = LISTING_LINK_RE.match("/" + slug)
    if not match:
        return unquote(slug)
    return unquote(match.group(2)).replace("-", " ").strip()


def _find_listing_links(html: str) -> set[str]:
    soup = BeautifulSoup(html, "lxml")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].split("?")[0]
        if LISTING_LINK_RE.match(href):
            links.add(urljoin(BASE, href))
    return links


def _find_next_page_url(html: str, current_url: str) -> str | None:
    """Find a "next page" link on a category listing page, if any."""
    soup = BeautifulSoup(html, "lxml")
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True).lower()
        rel = a.get("rel") or []
        if text in ("next", "next »", "»", "next page", ">") or "next" in rel:
            candidate = urljoin(current_url, a["href"])
            if candidate != current_url:
                return candidate
    return None


def _debug_dump_hrefs(html: str, limit: int = 25) -> None:
    soup = BeautifulSoup(html, "lxml")
    hrefs = [a["href"] for a in soup.find_all("a", href=True)]
    interesting = [h for h in hrefs if "classified" in h.lower() or "piper" in h.lower()]
    sample = interesting[:limit] or hrefs[:limit]
    print(f"  [debug] {len(hrefs)} total <a href> on page; sample: {sample}")


def _parse_detail_page(url: str, html: str) -> Listing | None:
    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None
    if title:
        title = re.sub(r"\s*[\|\-]\s*Barnstormers.*$", "", title, flags=re.IGNORECASE).strip()
    if not title or GENERIC_SITE_TITLE_SNIPPET in title.lower():
        title = _title_from_url(url)
    if not title:
        return None

    if _is_off_brand(title):
        return None

    text = soup.get_text(" ", strip=True)

    formatted_title = format_aircraft_title(title, text, _extract_model)
    if not formatted_title:
        return None
    title = formatted_title

    price = extract_price(text)
    location = extract_location(text)
    date_posted = extract_date(text)

    return Listing(
        title=title,
        price=price,
        location=location,
        date_posted=date_posted,
        site=SITE_NAME,
        url=url,
    )


def scrape() -> list[Listing]:
    print(f"[{SITE_NAME}] starting scrape")
    all_links: set[str] = set()

    for category_url in CATEGORY_URLS:
        seen_this_category: set[str] = set()
        url = category_url
        for page in range(1, MAX_PAGES + 1):
            html = fetch(url)
            if not html:
                break
            links = _find_listing_links(html)
            new_links = links - seen_this_category
            print(f"  [{category_url}] page {page}: {len(links)} links ({len(new_links)} new)")
            if page == 1 and not links:
                _debug_dump_hrefs(html)
            seen_this_category |= links
            next_url = _find_next_page_url(html, url)
            if not next_url or not new_links:
                break
            url = next_url
        print(f"  [{category_url}] {len(seen_this_category)} listings total")
        all_links |= seen_this_category

    print(f"[{SITE_NAME}] {len(all_links)} unique listing URLs found across categories")

    candidate_links = {url for url in all_links if not _is_off_brand(_title_from_url(url))}
    dropped_prefetch = len(all_links) - len(candidate_links)
    if dropped_prefetch:
        print(f"[{SITE_NAME}] {dropped_prefetch} dropped pre-fetch as off-brand")

    listings: list[Listing] = []
    for url in sorted(candidate_links):
        html = fetch(url)
        if not html:
            continue
        listing = _parse_detail_page(url, html)
        if listing:
            listings.append(listing)

    print(f"[{SITE_NAME}] parsed {len(listings)} listings")
    return listings
