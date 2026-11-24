"""Scrapes the Picos de Europa trails and the hiking gear list into CSV files."""

import argparse
import logging

from trip_planner.experiments.shared.source_data import fetch
from trip_planner.experiments.shared.source_data import gear
from trip_planner.experiments.shared.source_data import trails
from trip_planner.experiments.shared.utils import files
from trip_planner.experiments.shared.utils import paths

_LOGGER = logging.getLogger(__name__)
_SOURCES = ('trails', 'gear')


def _scrape_trails(args: argparse.Namespace) -> None:
    fetcher = fetch.PageFetcher(
        paths.PICOS_TRAILS / 'raw', delay_s=args.delay, refresh=args.refresh
    )
    try:
        records = trails.PicosTrailScraper(fetcher).run()
    finally:
        fetcher.close()
    files.write_csv(paths.PICOS_TRAILS / 'trails.csv', records)
    missing = [r.trail_code for r in records if r.length_km is None or r.duration_h is None]
    _LOGGER.info('Wrote %d trails; without length or duration: %s', len(records), missing)


def _scrape_gear(args: argparse.Namespace) -> None:
    fetcher = fetch.PageFetcher(
        paths.HIKING_GEAR / 'raw', delay_s=args.delay, refresh=args.refresh
    )
    try:
        items = gear.GearListScraper(fetcher, args.gear_url).run()
    finally:
        fetcher.close()
    files.write_csv(paths.HIKING_GEAR / 'gear_items.csv', items)
    _LOGGER.info('Wrote %d gear items', len(items))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', nargs='+', choices=_SOURCES, default=list(_SOURCES))
    parser.add_argument(
        '--refresh', action='store_true', help='re-download pages already in data/*/raw'
    )
    parser.add_argument('--delay', type=float, default=1.0, help='seconds between requests')
    parser.add_argument('--gear-url', default=gear.SNAPSHOT_URL)
    return parser.parse_args()


def main() -> None:
    """Runs the selected scrapers."""
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
    args = _parse_args()
    if 'trails' in args.sources:
        _scrape_trails(args)
    if 'gear' in args.sources:
        _scrape_gear(args)


if __name__ == '__main__':
    main()
