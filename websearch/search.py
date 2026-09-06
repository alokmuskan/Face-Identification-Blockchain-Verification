# Web-based reverse image search integration for the face verification pipeline.
# Uses a headless browser to upload the probe image to a reverse-image search
# engine and extracts matching web page / social media URLs.
from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)


class WebSearchError(Exception):
    """Raised when the reverse image search cannot produce any results."""


class WebSearchResult:
    """A single reverse-image search hit."""

    def __init__(
        self,
        url: str,
        title: str,
        description: str,
        image_url: Optional[str],
        page_type: str,
    ) -> None:
        self.url = url
        self.title = title
        self.description = description
        self.image_url = image_url
        self.page_type = page_type

    def to_dict(self) -> Dict[str, Any]:
        return {
            'url': self.url,
            'title': self.title,
            'description': self.description,
            'image_url': self.image_url,
            'page_type': self.page_type,
        }


def _page_type(url: str) -> str:
    domain = _domain(url)
    social_domains = (
        'facebook.com', 'instagram.com', 'twitter.com', 'x.com',
        'tiktok.com', 'youtube.com', 'reddit.com', 'pinterest.com',
        'linkedin.com', 't.co', 'vimeo.com', 'threads.net',
    )
    if domain in social_domains:
        return 'social_media'

    image_domains = ('imgur.com', 'flickr.com', 'unsplash.com', 'pixabay.com',
                     'wikimedia.org', 'imageshack.us', 'deviantart.com', 'gyazo.com')
    if domain in image_domains:
        return 'image_host'

    if domain.endswith('.blogspot.com') or domain.endswith('.wordpress.com'):
        return 'blog'

    return 'web'


def _domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.lower()
    except Exception:
        return ''


DEFAULT_CACHE_TTL_SECONDS = 3600  # 1 hour

class WebSearchEngine:
    """
    Headless browser-based reverse image search using Yandex Images.

    Why Yandex:
    - Free, no API key required
    - Generally returns the best image-matching results for faces
    - Allows file upload via the web UI (camposer.yandex.com / yandex.com/images)

    The flow in headless mode:
      1. Navigate to Yandex Images
      2. Click the camera search button
      3. Upload the image via the file input
      4. Wait for results, then extract link cards

    Results are cached on disk per image hash so repeated identify attempts
    for the same probe do not re-run the slow browser search during a demo.
    """

    def __init__(
        self,
        timeout_seconds: int = 30,
        cache_dir: Optional[Path] = None,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    ) -> None:
        self.timeout = timeout_seconds
        self._driver: Any = None
        self._cache_dir = cache_dir
        self._cache_ttl = cache_ttl_seconds

    def _ensure_driver(self) -> Any:
        if self._driver is not None:
            return self._driver

        opts = Options()
        opts.add_argument('--headless')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--disable-gpu')
        opts.add_argument('--window-size=1280,900')
        opts.add_argument('--disable-blink-features=AutomationControlled')
        opts.add_experimental_option('excludeSwitches', ['enable-automation'])
        opts.add_experimental_option('useAutomationExtension', False)

        try:
            service = Service()  # auto-discovers chromedriver if installed
            self._driver = webdriver.Chrome(service=service, options=opts)
        except Exception:
            # If chromedriver isn't found, fall back to the bundled Playwright-like
            # selenium-manager which is included in selenium 4.6+.
            try:
                self._driver = webdriver.Chrome(options=opts)
            except Exception as exc:
                raise WebSearchError(
                    'Could not start a headless browser. Install Chrome or Chromium '
                    'and the matching chromedriver, or selenium>=4.6 with a working '
                    'browser installer.'
                ) from exc

        self._driver.set_page_load_timeout(self.timeout)
        self._driver.implicitly_wait(2)
        return self._driver

    def search(self, image_bytes: bytes, image_name: str = 'probe.png') -> List[WebSearchResult]:
        """
        Upload the probe image to Yandex Images and return the top matching results.

        Returns an empty list when no results are found (not an error), so callers
        can still proceed to blockchain upload even without a social media hit.
        """
        driver = self._ensure_driver()
        results: List[WebSearchResult] = []

        digest = hashlib.sha256(image_bytes).hexdigest()

        # If caching is enabled and a fresh cache file exists for this probe,
        # return those results without launching the browser.
        if self._cache_dir is not None:
            cached = self._load_cache(digest)
            if cached is not None:
                return cached

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name

        # Try the full upload flow twice: Yandex occasionally serves a captcha
        # or a slow page on the first load, and a second attempt usually goes
        # through.
        attempts = 2
        for attempt in range(1, attempts + 1):
            try:
                driver.get('https://yandex.com/images/')

                # Click the camera / reverse-image search button.
                self._click_search_by_image(driver)

                # Upload the file once the file chooser input is visible.
                file_input = self._wait_for_file_input(driver)
                if file_input is None:
                    logger.warning(
                        'Yandex did not show a file input for image upload (attempt %d/%d).',
                        attempt, attempts,
                    )
                    continue

                file_input.send_keys(tmp_path)

                # Wait for the results page. Yandex takes ~10-20s to process
                # the upload and navigate from the landing page to /search.
                # NOTE: the landing page is full of its own yandex links and
                # background-image divs, so waiting for those elements alone
                # returns immediately and extraction runs on the wrong page.
                wait = WebDriverWait(driver, self.timeout)
                try:
                    wait.until(
                        lambda d: '/search' in (d.current_url or '')
                        or len(d.find_elements(By.CSS_SELECTOR,
                                               'div.serp-item, div.CompactView')) > 0,
                        'Results page did not load within the timeout.',
                    )
                except Exception:
                    # Some UI variants may render results without navigation.
                    pass

                # Once on the results page, give the cards a moment to render.
                try:
                    WebDriverWait(driver, 15).until(
                        lambda d: len(d.find_elements(By.CSS_SELECTOR, 'div.serp-item,'
                                                      'div.CompactView,'
                                                      'div[style*="background-image"]')) > 0,
                    )
                except Exception:
                    # Even without detected cards, try to extract whatever is there.
                    pass

                results = self._extract_results(driver)
            except Exception as exc:
                logger.warning('Reverse image search failed (attempt %d/%d): %s',
                               attempt, attempts, exc)

            if results:
                break
            if attempt < attempts:
                time.sleep(2)

        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass

        # Persist only non-empty results so a transient failure (captcha, slow
        # page, UI change) is retried on the next run instead of being served
        # from cache for the whole TTL.
        if self._cache_dir is not None and results:
            try:
                self._save_cache(digest, results)
            except Exception:
                logger.debug('Web search cache write skipped.', exc_info=True)

        return results

    def _load_cache(self, digest: str) -> Optional[List[WebSearchResult]]:
        """Return cached results for *digest* if they are still fresh."""
        if self._cache_dir is None:
            return None
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return None

        path = self._cache_dir / f'{digest}.json'
        if not path.exists():
            return None

        try:
            raw = path.read_text(encoding='utf-8')
            payload = json.loads(raw)
        except (OSError, ValueError):
            return None

        now = time.time()
        if payload.get('expires_at', 0) < now:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            return None

        results: List[WebSearchResult] = []
        for item in payload.get('results', []):
            try:
                results.append(WebSearchResult(
                    url=item.get('url', ''),
                    title=item.get('title', ''),
                    description=item.get('description', ''),
                    image_url=item.get('image_url'),
                    page_type=item.get('page_type', 'web'),
                ))
            except Exception:
                continue
        return results

    def _save_cache(self, digest: str, results: List[WebSearchResult]) -> None:
        """Persist *results* for *digest* with an expiry timestamp."""
        if self._cache_dir is None:
            return
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            'expires_at': time.time() + self._cache_ttl,
            'results': [r.to_dict() for r in results],
        }
        path = self._cache_dir / f'{digest}.json'
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
        os.replace(tmp, path)

    def _click_search_by_image(self, driver: Any) -> None:
        """Click the reverse-image search entry point on Yandex Images.

        Tries several selectors and approaches because Yandex's UI changes
        frequently and differs between regions.
        """
        # Approach 1: click known buttons by aria-label / data attributes.
        btn_selectors = [
            'button[aria-label="Search by image"]',
            'button[data-action="search-by-image"]',
            'button[aria-label*="image"]',
            'div.search-by-image__upload button',
            'yandex-search-by-image button',
        ]
        for sel in btn_selectors:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in els:
                    if el and el.is_enabled():
                        el.click()
                        logger.debug('Clicked search-by-image via: %s', sel)
                        return
            except Exception:
                continue

        # Approach 2: scroll the page and click anything that looks like the
        # camera/search-by-image control via text content.
        try:
            body = driver.page_source.lower()
            if 'search by image' in body or 'search by image' in body:
                driver.execute_script(
                    """document.querySelectorAll('button, a, div')
                       .forEach(el => {
                         const txt = (el.getAttribute('aria-label')||'')+
                                     (el.getAttribute('title')||'')+
                                     (el.textContent||'');
                         if (/search by image/i.test(txt)) { el.click(); }
                       });"""
                )
                time.sleep(1)
                return
        except Exception as exc:
            logger.debug('JS text-based click failed: %s', exc)

        # Approach 3: go directly to the dedicated search-by-image page.
        try:
            driver.get('https://yandex.com/images/search-by-image/')
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, 'body'))
            )
            logger.debug('Navigated to yandex.com/images/search-by-image/')
            # On the dedicated page, click the "Image search" button to reveal the upload control.
            time.sleep(2)
            for sel in ['button[aria-label="Image search"]', 'button[aria-label*="image"]', 'button[aria-label*="search"]']:
                try:
                    els = driver.find_elements(By.CSS_SELECTOR, sel)
                    for el in els:
                        if el and el.is_enabled():
                            el.click()
                            logger.debug('Clicked Image Search button on dedicated page via: %s', sel)
                            time.sleep(2)
                            return
                except Exception:
                    continue
        except Exception as exc:
            logger.warning('Could not open search-by-image page: %s', exc)

    def _wait_for_file_input(self, driver: Any) -> Optional[Any]:
        """Wait for and return a visible file input for image upload.

        On Yandex, the file input may be present in the DOM but hidden until
        the user clicks the camera/image-search button. We check both
        visibility and DOM presence.
        """
        # First try to detect a visible file input.
        wait = WebDriverWait(driver, 10)
        for css in (
            'input[type=file][accept*="image"]',
            'input[type=file]',
            'input[name=file]',
            '#search-by-image__upload input',
            'div.search-by-image__upload input',
        ):
            try:
                els = driver.find_elements(By.CSS_SELECTOR, css)
                for el in els:
                    if el.tag_name == 'input' and el.get_attribute('type') == 'file':
                        if el.is_displayed():
                            return el
                        # If hidden but present, we can still use it (send_keys works on hidden inputs too).
                        logger.debug('Found hidden file input, will use it.')
                        return el
            except Exception:
                continue

        # Fallback: wait a bit longer and check again.
        try:
            time.sleep(2)
            for css in ('input[type=file]', 'input[accept*="image"]'):
                els = driver.find_elements(By.CSS_SELECTOR, css)
                for el in els:
                    if el.tag_name == 'input' and el.get_attribute('type') == 'file':
                        return el
        except Exception:
            pass

        return None

    def _extract_results(self, driver: Any) -> List[WebSearchResult]:
        """
        Pull the top result cards from the Yandex Images results page.

        Yandex result cards typically contain an <a> with an href (the
        destination page), an image, and a caption snippet.

        The page body text after a search looks like:
          Similar images
          Sites
          474x592
          Anime icon shoto
          pinterest.com
          ...
        """
        results: List[WebSearchResult] = []
        seen: set = set()

        # Approach 1: Yandex uses <div> cards with class serp-item or similar.
        card_selectors = [
            'div.serp-item',
            'div.CompactView',
            'div[style*="background-image"]',
        ]

        elements: List[Any] = []
        for sel in card_selectors:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                if els:
                    elements = els
                    break
            except Exception:
                continue

        if elements:
            for el in elements:
                try:
                    text = (el.text or '').strip()
                    url = el.get_attribute('href') or ''

                    # If the element itself is not a link, look for inner links.
                    if not url:
                        try:
                            link_inside = el.find_element(By.CSS_SELECTOR, 'a[href]')
                            url = link_inside.get_attribute('href')
                            text = link_inside.text or text
                        except Exception:
                            pass

                    if not url or url in seen or 'yandex' in url:
                        continue
                    seen.add(url)

                    title = text.split('\n')[0].strip() if text else ''
                    description = text

                    image_url: Optional[str] = None
                    try:
                        img_el = el.find_element(By.CSS_SELECTOR, 'img')
                        image_url = img_el.get_attribute('src') or img_el.get_attribute('data-src')
                    except Exception:
                        pass

                    results.append(
                        WebSearchResult(
                            url=url,
                            title=title,
                            description=description,
                            image_url=image_url,
                            page_type=_page_type(url),
                        )
                    )
                    if len(results) >= 10:
                        break
                except Exception:
                    pass

        # Approach 1.5: If cards were found but no image_url was captured,
        # try once more to attach a thumbnail from the result link elements.
        # Many Yandex result links wrap the preview image in an <img>.
        if results and not any(r.image_url for r in results):
            try:
                links = driver.find_elements(By.CSS_SELECTOR, 'a[href]')
                seen_links = {r.url for r in results}
                for link in links:
                    url = link.get_attribute('href') or ''
                    if not url or 'yandex' in url or url in seen_links:
                        continue
                    img = None
                    try:
                        img = link.find_element(By.CSS_SELECTOR, 'img')
                    except Exception:
                        try:
                            img = link.find_element(By.CSS_SELECTOR, 'img')
                        except Exception:
                            pass
                    if img is None:
                        continue
                    candidate = img.get_attribute('src') or img.get_attribute('data-src') or img.get_attribute('data-lazy-src')
                    if candidate and candidate.startswith(('http:', 'https:')):
                        for r in results:
                            if r.url == url and r.image_url is None:
                                r.image_url = candidate
                                break
                        seen_links.add(url)
                    if len([r for r in results if r.image_url]) >= 6:
                        break
            except Exception:
                pass

        # Approach 2: If card-based extraction did not work, parse the page
        # body text to find links and their captions (Yandex text format).
        if not results:
            try:
                body_text = driver.find_element(By.TAG_NAME, 'body').text
                lines_list = [l.strip() for l in body_text.split('\n') if l.strip()]

                # Find all external links on the page.
                links = driver.find_elements(By.CSS_SELECTOR, 'a[href]')
                external = [l for l in links if l.get_attribute('href') and 'yandex' not in (l.get_attribute('href') or '')]

                for link in external:
                    url = link.get_attribute('href') or ''
                    if not url or url in seen:
                        continue
                    seen.add(url)

                    link_text = (link.text or '').strip()
                    title = link_text if link_text else ''
                    description = link_text if link_text else ''

                    # Heuristic: the line right before a domain mention might be the title.
                    domain = _domain(url)
                    for i, line in enumerate(lines_list):
                        if domain in line.lower() and i > 0:
                            prev = lines_list[i - 1]
                            if prev and prev != url and len(prev) > 2:
                                if not title:
                                    title = prev
                                description = prev + '\n' + line
                            break

                    results.append(
                        WebSearchResult(
                            url=url,
                            title=title,
                            description=description,
                            image_url=None,
                            page_type=_page_type(url),
                        )
                    )
                    if len(results) >= 10:
                        break
            except Exception:
                pass

        return results

    def close(self) -> None:
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:
                pass
            finally:
                self._driver = None

    def __enter__(self) -> 'WebSearchEngine':
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
