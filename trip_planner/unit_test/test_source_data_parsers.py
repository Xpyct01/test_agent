"""Tests of the experiment scrapers: Picos trail pages and the hiking gear list."""

import logging

import httpx
import pytest

pytest.importorskip('bs4', reason='needs the experiments dependency group')

# pylint: disable=wrong-import-position
from trip_planner.experiments.shared.source_data import gear
from trip_planner.experiments.shared.source_data import trails

# pylint: enable=wrong-import-position


class _FakeFetcher:
    """Serves pages from a dict; unknown URLs fail like a dead link."""

    def __init__(self, pages: dict[str, str]):
        self._pages = pages
        self.requested: list[str] = []

    def fetch(self, url: str) -> str:
        self.requested.append(url)
        if url not in self._pages:
            raise httpx.HTTPError(f'404 for {url}')
        return self._pages[url]


# ---------------------------------------------------------------- field parsers


@pytest.mark.parametrize(
    'text, expected',
    [
        ('21 Km. (Trayecto de ida)', 21.0),
        ('15,1 km', 15.1),
        ("7'6 Km.", 7.6),
        ('2.5 kilómetros', 2.5),
        ('800 m', 0.8),
        ('1250 m (ida y vuelta)', 1.25),
        ('sin datos', None),
        ('', None),
    ],
)
def test_parse_length_km(text, expected):
    assert trails.parse_length_km(text) == expected


@pytest.mark.parametrize(
    'text, expected',
    [
        ('899 m. de descenso y 160 m. de ascenso', (160, 899)),
        ('50 m. (de ascenso y descenso)', (50, 50)),
        ('391 m. de subida y de bajada', (391, 391)),
        ('1.110 m. de subida y bajada', (1110, 1110)),
        ('974 m. (todos en descenso)', (None, 974)),
        ('1.070 m de subida', (1070, None)),
        ('610 m.', (610, None)),
        ('', (None, None)),
    ],
)
def test_parse_elevation(text, expected):
    assert trails.parse_elevation(text) == expected


@pytest.mark.parametrize(
    'text, expected',
    [
        ('3 h. 20 min. (solo ida)', 3.33),
        ('2 horas y 30 min', 2.5),
        ('5 horas', 5.0),
        ('4,5 h', 4.5),
        ('1 hora', 1.0),
        ('45 min', 0.75),
        ('', None),
    ],
)
def test_parse_duration_h(text, expected):
    assert trails.parse_duration_h(text) == expected


@pytest.mark.parametrize(
    'text, expected',
    [
        ('Media - Alta', 'hard'),
        ('Medio-alta', 'hard'),
        ('Muy alta', 'very_hard'),
        ('Muy difícil en invierno', 'very_hard'),
        ('Baja', 'easy'),
        ('Fácil', 'easy'),
        ('Media', 'moderate'),
        ('Alta', 'hard'),
        ('Ruta de dificultad media', 'moderate'),
        ('desconocida', None),
        ('', None),
    ],
)
def test_parse_difficulty(text, expected):
    assert trails.parse_difficulty(text) == expected


# ---------------------------------------------------------------- trail scraper

_BASE = 'https://parks.test/picos/'
_INDEX_HTML = f"""
<ul>
  <li class="paragraph-item">
    <h2 class="cmp-title__text">Senderos de pequeño recorrido (PR)</h2>
    <a class="ficon-link" href="{_BASE}pr-1.html">PR PNPE 1: RUTA DEL CARES</a>
    <a class="ficon-link" href="{_BASE}broken.html">PR PNPE 2: ROTA</a>
  </li>
  <li class="paragraph-item">
    <h2 class="cmp-title__text">Rutas de alta montaña</h2>
    <a class="ficon-link" href="{_BASE}am-1.html">AM 1: Peña Santa</a>
  </li>
  <li class="paragraph-item">
    <h2 class="cmp-title__text">Otros recursos</h2>
    <a class="ficon-link" href="{_BASE}other.html">X: Not a trail</a>
  </li>
</ul>
"""
_PR1_HTML = """
<div class="cmp-text">
  <p><strong>Longitud</strong> (Length): 12 Km. (ida)</p>
  <p><strong>Desnivel</strong> (Gradient): 899 m. de descenso y 160 m. de ascenso</p>
  <p><strong>Duración</strong> (Duration): 3 h. 20 min.</p>
  <p><strong>Dificultad</strong> (Difficulty): Media - Alta</p>
  <p><strong>Descripción:</strong> Un recorrido
     por la   garganta.</p>
  <p><strong>Caution notes</strong>: Watch for falling rocks.</p>
  <p><strong>Longitud</strong>: 99 km</p>
  <p><strong>Autor</strong>: ignored label</p>
  <p>
    <a href="/docs/mapa-pr1.pdf">Mapa de la ruta</a>
    <a href="perfil-pr1.pdf">Perfil</a>
    <a href="mapa-otro.pdf">Mapa alternativo</a>
  </p>
</div>
"""
_AM1_HTML = """
<div class="cmp-text">
  <p><strong>Longitud:</strong> 800 m</p>
  <p><strong>Desnivel:</strong> 974 m. (todos en descenso)</p>
</div>
"""


@pytest.fixture
def trail_scraper() -> tuple[trails.PicosTrailScraper, _FakeFetcher]:
    fetcher = _FakeFetcher({
        f'{_BASE}index.html': _INDEX_HTML,
        f'{_BASE}pr-1.html': _PR1_HTML,
        f'{_BASE}am-1.html': _AM1_HTML,
    })
    return trails.PicosTrailScraper(fetcher, f'{_BASE}index.html'), fetcher


def test_trail_scraper_reads_known_sections_only(trail_scraper):
    scraper, fetcher = trail_scraper

    records = scraper.run()

    assert [r.trail_code for r in records] == ['PR PNPE 1', 'AM 1']
    assert f'{_BASE}other.html' not in fetcher.requested


def test_trail_scraper_skips_broken_pages(trail_scraper, caplog):
    scraper, _ = trail_scraper

    with caplog.at_level(logging.ERROR):
        records = scraper.run()

    assert 'PR PNPE 2' not in [r.trail_code for r in records]
    assert 'Skipping PR PNPE 2' in caplog.text


def test_trail_scraper_parses_trail_page(trail_scraper):
    scraper, _ = trail_scraper

    record = scraper.run()[0]

    assert record.name == 'Ruta Del Cares'
    assert record.section == 'Senderos de pequeño recorrido (PR)'
    assert record.trail_type == 'short_distance'
    assert record.length_text == '12 Km. (ida)'  # First label wins.
    assert record.length_km == 12.0
    assert (record.ascent_m, record.descent_m) == (160, 899)
    assert record.duration_h == 3.33
    assert record.difficulty_text == 'Media - Alta'
    assert record.difficulty == 'hard'
    assert record.description == 'Un recorrido por la garganta.'
    assert record.precautions_en == 'Watch for falling rocks.'
    assert record.map_pdf_url == 'https://parks.test/docs/mapa-pr1.pdf'
    assert record.profile_pdf_url == f'{_BASE}perfil-pr1.pdf'
    assert record.source_url == f'{_BASE}pr-1.html'


def test_trail_scraper_leaves_missing_fields_empty(trail_scraper):
    scraper, _ = trail_scraper

    record = scraper.run()[1]

    assert record.trail_type == 'high_mountain'
    assert record.length_km == 0.8
    assert (record.ascent_m, record.descent_m) == (None, 974)
    assert record.duration_h is None
    assert record.difficulty is None
    assert record.duration_text == ''
    assert record.map_pdf_url == ''


# ---------------------------------------------------------------- gear scraper

_GEAR_URL = 'https://gear.test/list/'
_ARCHIVE = 'https://web.archive.org/web/20251116185735'
_GEAR_HTML = f"""
<h3 id="intro">Introduction</h3>
<p><strong>Not gear:</strong> <a href="https://gear.test/about">before the list</a></p>
<h3 id="pack-system">Pack   System</h3>
<p><strong>Backpack:</strong> <a href="{_ARCHIVE}/https://shop.test/pack">Osprey Exos</a> 58</p>
<p>Why I chose this pack</p>
<ul><li>Light
  weight</li><li>Comfortable</li></ul>
<p>Some intro text without a label.</p>
<h3 id="sleep-system">Sleep System</h3>
<p><strong>Sleeping Mat –</strong> <a href="https://shop.test/mat">S<span>ea</span> to Summit</a></p>
<p>This has <strong>bold</strong> and <a href="https://shop.test/x">a link</a> later.</p>
<h3 id="swap-outs">Swap Outs</h3>
<p><strong>Headlamp:</strong> <a href="{_ARCHIVE}im_/https://shop.test/lamp">Lamp</a></p>
<h3 id="petzl">Petzl Swift RL 900</h3>
<p><strong>Torch:</strong> <a href="https://shop.test/torch">Petzl</a></p>
<h3 id="pdf-version-1">PDF version</h3>
<p><strong>Ignored:</strong> <a href="https://shop.test/ignored">After the list</a></p>
"""


@pytest.fixture
def gear_items() -> list[gear.GearItem]:
    fetcher = _FakeFetcher({_GEAR_URL: _GEAR_HTML})
    return gear.GearListScraper(fetcher, _GEAR_URL).run()


def test_gear_scraper_keeps_only_labelled_items_inside_the_list(gear_items):
    assert [i.item_type for i in gear_items] == [
        'Backpack',
        'Sleeping Mat',
        'Headlamp',
        'Torch',
    ]


def test_gear_scraper_parses_item(gear_items):
    backpack = gear_items[0]

    assert backpack == gear.GearItem(
        category='Pack System',
        item_type='Backpack',
        product='Osprey Exos 58',
        is_swap_out=False,
        reasons='Light weight | Comfortable',
        product_url='https://shop.test/pack',
        source_url=gear.LIVE_URL,
    )


def test_gear_scraper_joins_words_split_across_tags(gear_items):
    mat = gear_items[1]

    assert mat.category == 'Sleep System'
    assert mat.product == 'Sea to Summit'
    assert mat.reasons == ''  # The next linked paragraph is not a reason list.


def test_gear_scraper_keeps_swap_outs_category_to_the_end(gear_items):
    headlamp, torch = gear_items[2:]

    assert headlamp.category == torch.category == 'Swap Outs'
    assert headlamp.is_swap_out and torch.is_swap_out
    assert headlamp.product_url == 'https://shop.test/lamp'


def test_gear_scraper_rejects_page_without_list():
    fetcher = _FakeFetcher({_GEAR_URL: '<h3 id="other">Nothing</h3>'})

    with pytest.raises(ValueError, match='No gear list found'):
        gear.GearListScraper(fetcher, _GEAR_URL).run()
