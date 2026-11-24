"""Scraper of the official Picos de Europa itinerary pages (miteco.gob.es)."""

import dataclasses
import logging
import re
from urllib import parse

import bs4

from trip_planner.experiments.shared.source_data import fetch

_LOGGER = logging.getLogger(__name__)

INDEX_URL = (
    'https://www.miteco.gob.es/es/parques-nacionales-oapn/red-parques-nacionales/'
    'parques-nacionales/picos-europa/guia-visitante/itinerarios.html'
)

# Spanish field label on a trail page -> TrailRecord attribute.
_FIELD_LABELS = {
    'longitud': 'length_text',
    'desnivel': 'elevation_text',
    'duración': 'duration_text',
    'dificultad': 'difficulty_text',
    'descripción': 'description',
    'cómo hacer la ruta': 'how_to',
    'preste atención a': 'points_of_interest',
    'precauciones': 'precautions_es',
    'caution notes': 'precautions_en',
}
_SECTION_TYPES = {
    'Senderos de pequeño recorrido (PR)': 'short_distance',
    'Senderos de gran recorrido (GR)': 'long_distance',
    'Rutas de alta montaña': 'high_mountain',
}
# Leading word(s) of the difficulty text -> normalized level, most specific first.
_DIFFICULTY_LEVELS = (
    ('muy alta', 'very_hard'),
    ('muy difícil', 'very_hard'),
    ('media-alta', 'hard'),
    ('medio-alta', 'hard'),
    ('baja', 'easy'),
    ('fácil', 'easy'),
    ('sencilla', 'easy'),
    ('media', 'moderate'),
    ('moderada', 'moderate'),
    ('alta', 'hard'),
    ('difícil', 'hard'),
)
# Decimal marks seen on the pages: '15,1', '7'6' and '2.5'.
_NUMBER = r"(\d+(?:[.,']\d+)?)"
_UP_WORDS = r'ascenso|subida|positivo'
_DOWN_WORDS = r'descenso|bajada|negativo'


@dataclasses.dataclass
class TrailRecord:
    """One itinerary: the index entry, its page fields and the values parsed from them."""

    trail_code: str
    name: str
    section: str
    trail_type: str
    length_km: float | None
    ascent_m: int | None
    descent_m: int | None
    duration_h: float | None
    difficulty: str | None
    length_text: str = ''
    elevation_text: str = ''
    duration_text: str = ''
    difficulty_text: str = ''
    description: str = ''
    how_to: str = ''
    points_of_interest: str = ''
    precautions_es: str = ''
    precautions_en: str = ''
    map_pdf_url: str = ''
    profile_pdf_url: str = ''
    source_url: str = ''


class PicosTrailScraper:
    """Reads the itinerary index, then every trail page it links to."""

    def __init__(self, fetcher: fetch.PageFetcher, index_url: str = INDEX_URL):
        """Initializes the scraper.

        Args:
            fetcher: Downloads (or reads cached) pages.
            index_url: The itinerary index page.
        """
        self._fetcher = fetcher
        self._index_url = index_url

    def run(self) -> list[TrailRecord]:
        """Returns one record per trail listed on the index page, in page order."""
        records = []
        for section, code, name, url in self._parse_index():
            try:
                records.append(self._parse_trail(section, code, name, url))
            except Exception:  # One broken page must not lose the others.
                _LOGGER.exception('Skipping %s (%s)', code, url)
        return records

    def _parse_index(self) -> list[tuple[str, str, str, str]]:
        soup = bs4.BeautifulSoup(self._fetcher.fetch(self._index_url), 'html.parser')
        entries = []
        for heading in soup.find_all('h2', class_='cmp-title__text'):
            section = heading.get_text(strip=True)
            if section not in _SECTION_TYPES:
                continue
            container = heading.find_parent('li', class_='paragraph-item')
            for link in container.find_all('a', class_='ficon-link'):
                code, _, name = link.get_text(strip=True).partition(':')
                entries.append((section, code.strip(), name.strip().title(), link['href']))
        return entries

    def _parse_trail(self, section: str, code: str, name: str, url: str) -> TrailRecord:
        soup = bs4.BeautifulSoup(self._fetcher.fetch(url), 'html.parser')
        fields = _extract_fields(soup)
        pdfs = _extract_pdfs(soup, url)
        ascent_m, descent_m = parse_elevation(fields.get('elevation_text', ''))
        return TrailRecord(
            trail_code=code,
            name=name,
            section=section,
            trail_type=_SECTION_TYPES[section],
            length_km=parse_length_km(fields.get('length_text', '')),
            ascent_m=ascent_m,
            descent_m=descent_m,
            duration_h=parse_duration_h(fields.get('duration_text', '')),
            difficulty=parse_difficulty(fields.get('difficulty_text', '')),
            map_pdf_url=pdfs.get('mapa', ''),
            profile_pdf_url=pdfs.get('perfil', ''),
            source_url=url,
            **fields,
        )


def _clean(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def _extract_fields(soup: bs4.BeautifulSoup) -> dict[str, str]:
    """Maps each `<strong>Label</strong> (English gloss): value` paragraph to a field."""
    fields: dict[str, str] = {}
    for strong in soup.select('div.cmp-text strong'):
        label = _clean(strong.get_text()).rstrip(':').lower()
        attribute = _FIELD_LABELS.get(label)
        paragraph = strong.find_parent('p')
        if attribute is None or paragraph is None or attribute in fields:
            continue
        text = _clean(paragraph.get_text(' '))
        value = text[len(_clean(strong.get_text())):]
        value = re.sub(r'^\s*\([^)]*\)', '', value)  # Drops the "(Length)" gloss.
        fields[attribute] = value.lstrip(' :').strip()
    return fields


def _extract_pdfs(soup: bs4.BeautifulSoup, page_url: str) -> dict[str, str]:
    """Returns the route map and elevation profile PDF links, keyed 'mapa'/'perfil'."""
    pdfs = {}
    for link in soup.select('div.cmp-text a[href$=".pdf"]'):
        text = link.get_text(strip=True).lower()
        for key in ('mapa', 'perfil'):
            if text.startswith(key) and key not in pdfs:
                pdfs[key] = parse.urljoin(page_url, link['href'])
    return pdfs


def _to_float(number: str) -> float:
    return float(number.replace(',', '.').replace("'", '.'))


def parse_length_km(text: str) -> float | None:
    """Returns the first distance in km, e.g. 21 from '21 Km. (Trayecto ...)'."""
    match = re.search(_NUMBER + r'\s*(km|kilómetros)', text, re.IGNORECASE)
    if match:
        return _to_float(match.group(1))
    match = re.search(_NUMBER + r'\s*m\b', text)
    return round(_to_float(match.group(1)) / 1000, 2) if match else None


def parse_elevation(text: str) -> tuple[int | None, int | None]:
    """Returns (ascent_m, descent_m) from the first figures of the elevation text.

    '899 m. de descenso y 160 m. de ascenso' gives both directly. A single figure
    applies to every direction the text names: '50 m. (de ascenso y descenso)' gives
    (50, 50), '974 m. (todos en descenso)' gives (None, 974) and a bare '610 m.' is
    taken as the ascent.
    """

    def find(pattern: str) -> int | None:
        match = re.search(pattern, text, re.IGNORECASE)
        # '1.070 m' uses '.' as the thousands separator.
        return int(_to_float(match.group(1).replace('.', ''))) if match else None

    # '391 m. de subida y de bajada', '1.110 m. de subida y bajada'.
    both = find(
        _NUMBER + rf'\s*m\.?[^/\d]{{0,30}}?(?:{_UP_WORDS}|{_DOWN_WORDS})'
        rf'\s+(?:y|como|o)\s+(?:de\s+)?(?:{_UP_WORDS}|{_DOWN_WORDS})'
    )
    if both is not None:
        return both, both
    ascent = find(_NUMBER + rf'\s*m\.?\s*(?:de\s+|en\s+)?(?:{_UP_WORDS})')
    descent = find(_NUMBER + rf'\s*m\.?\s*(?:de\s+|en\s+)?(?:{_DOWN_WORDS})')
    if ascent is None and descent is None:
        figure = find(_NUMBER + r'\s*m\b')
        goes_up = re.search(_UP_WORDS, text, re.IGNORECASE) is not None
        goes_down = re.search(_DOWN_WORDS, text, re.IGNORECASE) is not None
        ascent = figure if goes_up or not goes_down else None
        descent = figure if goes_down else None
    return ascent, descent


def parse_duration_h(text: str) -> float | None:
    """Returns the first duration in hours, e.g. 3.33 from '3 h. 20 min. ...'."""
    match = re.search(
        r'(\d+(?:[.,]\d+)?)\s*(?:h|horas?)\.?(?:\s*(?:y\s*)?(\d+)\s*(?:min|m)\b)?',
        text,
        re.IGNORECASE,
    )
    if match:
        minutes = int(match.group(2)) if match.group(2) else 0
        return round(_to_float(match.group(1)) + minutes / 60, 2)
    match = re.search(r'(\d+)\s*min', text, re.IGNORECASE)
    return round(int(match.group(1)) / 60, 2) if match else None


def parse_difficulty(text: str) -> str | None:
    """Maps the Spanish difficulty text to easy/moderate/hard/very_hard."""
    lowered = re.sub(r'\s*-\s*', '-', text.lower())  # 'Media - Alta' -> 'media-alta'.
    for prefix, level in _DIFFICULTY_LEVELS:
        if lowered.startswith(prefix):
            return level
    for prefix, level in _DIFFICULTY_LEVELS:
        if prefix in lowered:
            return level
    return None
