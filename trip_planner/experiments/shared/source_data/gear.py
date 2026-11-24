"""Scraper of the Australian Hiker multi-day gear list."""

import dataclasses
import re

import bs4

from trip_planner.experiments.shared.source_data import fetch

# The live site answers scripted clients with a Cloudflare challenge (HTTP 403), so the
# default source is a pinned Internet Archive snapshot of the same page.
LIVE_URL = 'https://australianhiker.com.au/gear/multiday-gear-list/'
SNAPSHOT_URL = f'https://web.archive.org/web/20251116185735/{LIVE_URL}'
_SWAP_OUTS = 'Swap Outs'
_ARCHIVE_PREFIX = re.compile(r'^https?://web\.archive\.org/web/\d+(?:[a-z_]+)?/')


@dataclasses.dataclass
class GearItem:
    """One piece of equipment from the list."""

    category: str
    item_type: str
    product: str
    is_swap_out: bool
    reasons: str
    product_url: str
    source_url: str


class GearListScraper:
    """Reads Tim's multi-day gear list: one item per bold label under a category heading."""

    def __init__(self, fetcher: fetch.PageFetcher, url: str = SNAPSHOT_URL):
        """Initializes the scraper.

        Args:
            fetcher: Downloads (or reads cached) pages.
            url: The gear list page, live or archived.
        """
        self._fetcher = fetcher
        self._url = url

    def run(self) -> list[GearItem]:
        """Returns the items in page order."""
        soup = bs4.BeautifulSoup(self._fetcher.fetch(self._url), 'html.parser')
        first = soup.find('h3', id='pack-system')
        if first is None:
            raise ValueError(f'No gear list found at {self._url}')
        items = []
        category = ''
        for element in [first, *first.find_all_next(['h3', 'p'])]:
            if element.name == 'h3':
                if element.get('id', '').startswith('pdf-version'):
                    break
                # "Swap Outs" runs to the end of the list; a product heading inside it
                # (e.g. "Petzl Swift RL 900 ...") is not a new category.
                if category != _SWAP_OUTS:
                    category = _clean(element.get_text())
                continue
            item = self._parse_item(element, category)
            if item is not None:
                items.append(item)
        return items

    def _parse_item(self, paragraph: bs4.Tag, category: str) -> GearItem | None:
        strong = paragraph.find('strong')
        link = paragraph.find('a', href=True)
        if strong is None or link is None or paragraph.contents[0] is not strong:
            return None
        reasons_list = paragraph.find_next_sibling(['ul', 'p', 'h3'])
        while reasons_list is not None and reasons_list.name == 'p' and not reasons_list.find('a'):
            reasons_list = reasons_list.find_next_sibling(['ul', 'p', 'h3'])  # "Why I chose..."
        reasons = []
        if reasons_list is not None and reasons_list.name == 'ul':
            reasons = [_clean(li.get_text()) for li in reasons_list.find_all('li')]
        # No separator: the page splits words across inline tags ('S<span>ea</span>').
        product = _clean(paragraph.get_text()[len(strong.get_text()):])
        return GearItem(
            category=category,
            item_type=_clean(strong.get_text()).rstrip(' :–-'),
            product=product,
            is_swap_out=category == _SWAP_OUTS,
            reasons=' | '.join(reasons),
            product_url=_ARCHIVE_PREFIX.sub('', link['href']),
            source_url=LIVE_URL,
        )


def _clean(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()
