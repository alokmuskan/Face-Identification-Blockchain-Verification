# Web-based reverse image search integration for the face verification pipeline.
# Uses a headless browser to upload the probe image to a reverse-image search
# engine and extracts matching web page / social media URLs.
from __future__ import annotations

import base64
import hashlib
import io
import logging
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
    """

    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout = timeout_seconds
        self._driver: Any = None

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

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name

        try:
            driver.get('https://yandex.com/images/')

            # Click the camera / reverse-image search button.
            self._click_search_by_image(driver)

            # Upload the file once the file chooser input is visible.
            file_input = self._wait_for_file_input(driver)
            if file_input is None:
                logger.warning('Yandex did not show a file input for image upload.')
                return []

            file_input.send_keys(tmp_path)

            # Wait for result cards or at least some content to appear.
            wait = WebDriverWait(driver, self.timeout)
            try:
                wait.until(
                    lambda d: len(d.find_elements(By.CSS_SELECTOR, 'div.serp-item,'
                                                   'div.CompactView,'
                                                   'div[style*="background-image"],'
                                                   'a[href*="yandex"]')) > 0,
                    'Results did not appear within the timeout.',
                )
            except Exception:
                # Even without detected cards, try to extract whatever is there.
                pass

            results = self._extract_results(driver)
        except Exception as exc:
            logger.warning('Reverse image search failed: %s', exc)
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                pass

        return results

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
        except Exception as exc:
            logger.warning('Could not open search-by-image page: %s', exc)

    def _wait_for_file_input(self, driver: Any) -> Optional[Any]:
        wait = WebDriverWait(driver, self.timeout)
        for css in (
            'input[type=file]',
            'input[name=file]',
            'input[accept*="image"]',
            '#search-by-image__upload input',
            'div.search-by-image__upload input',
        ):
            try:
                el = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, css))
                )
                if el and el.tag_name == 'input' and el.get_attribute('type') == 'file':
                    return el
            except Exception:
                continue
        return None

    def _extract_results(self, driver: Any) -> List[WebSearchResult]:
        """
        Pull the top result cards from the Yandex Images results page.

        Yandex result cards typically contain an <a> with an href (the
        destination page), an image, and a caption snippet.
        """
        results: List[WebSearchResult] = []
        seen: set = set()

        # Yandex uses several different card structures; try a few known selectors.
        card_selectors = [
            'div.serp-item',
            'div.CompactView',
            'div[style*="background-image"]',
            'a[href*="yandex"]',  # sometimes the first match is an inline result
            'div. NODISMEDIA',  # not real but as a guard
        ]

        elements = []
        for sel in card_selectors:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                if els:
                    elements = els
                    break
            except Exception:
                continue

        if not elements:
            # Generic fallback: collect all links that look like external pages.
            try:
                links = driver.find_elements(By.CSS_SELECTOR, 'a:not([href*="yandex"])')
                elements = links
            except Exception:
                return []

        for el in elements:
            try:
                text = (el.text or '').strip()
                if not text and el.tag_name == 'a':
                    text = el.get_attribute('aria-label') or ''
                if len(text) < 3:
                    continue

                url = None
                try:
                    url = el.get_attribute('href')
                except Exception:
                    pass

                if not url:
                    # If this is an image card, the actual link may be inside.
                    try:
                        link_inside = el.find_element(By.CSS_SELECTOR, 'a[href]')
                        url = link_inside.get_attribute('href')
                    except Exception:
                        continue

                if not url or url in seen:
                    continue
                seen.add(url)

                # Prefer the page title or the image caption as the "title"
                title = text.split('\n')[0].strip() if text else ''
                description = text

                # Try to grab the source image URL
                image_url = None
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
                continue

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
