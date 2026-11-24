"""Polite HTTP page fetching with retries and a raw-HTML snapshot cache."""

import hashlib
import logging
import pathlib
import time

import httpx

_LOGGER = logging.getLogger(__name__)
_USER_AGENT = 'Mozilla/5.0 (compatible; trip-planner-data-collector/0.1)'


class PageFetcher:
    """Downloads pages once and keeps their HTML on disk for reproducible parsing."""

    def __init__(
        self,
        cache_dir: pathlib.Path,
        delay_s: float = 1.0,
        retries: int = 3,
        timeout_s: float = 30.0,
        refresh: bool = False,
    ):
        """Initializes the fetcher.

        Args:
            cache_dir: Directory of the raw HTML snapshots, one file per URL.
            delay_s: Pause before every network request, to spare the server.
            retries: Attempts per URL before giving up.
            timeout_s: Timeout of one request.
            refresh: Re-download pages that are already cached.
        """
        self._cache_dir = cache_dir
        self._delay_s = delay_s
        self._retries = retries
        self._refresh = refresh
        self._client = httpx.Client(
            headers={'User-Agent': _USER_AGENT},
            follow_redirects=True,
            timeout=timeout_s,
        )

    def fetch(self, url: str) -> str:
        """Returns the HTML of a page, from the cache when present.

        Args:
            url: Page address.

        Returns:
            The decoded page body.

        Raises:
            httpx.HTTPError: If every attempt failed.
        """
        path = self._cache_path(url)
        if path.exists() and not self._refresh:
            return path.read_text(encoding='utf-8')
        html = self._download(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding='utf-8')
        return html

    def close(self) -> None:
        """Releases the HTTP connections."""
        self._client.close()

    def _cache_path(self, url: str) -> pathlib.Path:
        slug = url.rstrip('/').rsplit('/', 1)[-1].removesuffix('.html') or 'index'
        digest = hashlib.sha1(url.encode('utf-8')).hexdigest()[:8]
        return self._cache_dir / f'{slug}-{digest}.html'

    def _download(self, url: str) -> str:
        for attempt in range(1, self._retries + 1):
            time.sleep(self._delay_s * attempt)
            try:
                response = self._client.get(url)
                response.raise_for_status()
                return response.text
            except httpx.HTTPError as error:
                _LOGGER.warning(
                    'Attempt %d/%d for %s failed: %s', attempt, self._retries, url, error
                )
                if attempt == self._retries:
                    raise
        raise AssertionError('unreachable')
