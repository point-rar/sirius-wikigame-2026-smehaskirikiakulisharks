from abc import ABC, abstractmethod
from typing import Dict, Any

import requests
import aiohttp
import asyncio

from bs4 import BeautifulSoup
from loguru import logger

from typing import Optional


class WikiParser():
    URL = 'https://en.wikipedia.org/w/api.php'
    RATE_LIMIT = 10  # Requests per second
    MAX_LINKS_PER_PAGE = 100  # Maximum links to take from one page
    MAX_LINKS_IN_CHUNK = 500  # Maximum total links in processing chunk

    def __init__(self):
        self.session = None
        self.last_request_time = 0
        self.rate_limit_lock = asyncio.Lock()
        self.links_cache: dict[str, set[str]] = {}
        self.backlinks_cache: dict[str, set[str]] = {}



    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            connector = aiohttp.TCPConnector(limit=30, ttl_dns_cache=300)
            self.session = aiohttp.ClientSession(
                connector=connector,
                headers={"User-Agent": "WikiGame/1.0 (contact: your_email@example.com)"}
            )
        return self.session

    async def warmup(self):
        """Pre-initialize session and establish connection to Wikipedia API"""
        logger.info("Warming up connection to Wikipedia API...")
        session = await self.get_session()
        try:
            # Make a lightweight request to establish connection
            params = {
                'action': 'query',
                'meta': 'siteinfo',
                'format': 'json'
            }
            async with session.get(url=self.URL, params=params) as resp:
                await resp.json()
            logger.info("Connection warmed up successfully")
        except Exception as e:
            logger.warning(f"Warmup failed: {e}")

    async def close(self):
        if self.session:
            await self.session.close()

    async def _make_request(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        retry_count = 5
        base_delay = 1.0
        session = await self.get_session()

        async with self.rate_limit_lock:
            now = asyncio.get_running_loop().time()
            time_since_last = now - self.last_request_time
            delay_needed = 1.0 / self.RATE_LIMIT

            if time_since_last < delay_needed:
                await asyncio.sleep(delay_needed - time_since_last)

            self.last_request_time = asyncio.get_running_loop().time()

        for attempt in range(retry_count):
            try:
                async with session.get(url=self.URL, params=params) as resp:
                    page_name = params.get('page') or params.get('bltitle') or 'unknown'

                    if resp.status == 429:
                        retry_after = float(resp.headers.get("Retry-After", base_delay * (2 ** attempt)))
                        logger.warning(f"Rate limited (429) for '{page_name}'. Retrying in {retry_after:.2f}s...")
                        await asyncio.sleep(retry_after)
                        continue

                    if resp.status != 200:
                        logger.warning(f"Unexpected status code {resp.status} for '{page_name}'")
                        if resp.status >= 500:
                            await asyncio.sleep(base_delay * (2 ** attempt))
                            continue
                        return None

                    data = await resp.json()

                    if data.get('error'):
                        error_code = data['error'].get('code')
                        if error_code in ('maxlag', 'ratelimited'):
                            wait_time = base_delay * (2 ** attempt)
                            logger.warning(f"API Error '{error_code}' for '{page_name}'. Retrying in {wait_time}s...")
                            await asyncio.sleep(wait_time)
                            continue
                        logger.error(f"API Error for '{page_name}': {data['error'].get('info')}")
                        return None

                    return data

            except aiohttp.ClientError as e:
                logger.error(f"Network error fetching: {e}")
                if attempt < retry_count - 1:
                    await asyncio.sleep(base_delay * (2 ** attempt))
                    continue
                raise
            except Exception as e:
                logger.error(f"Error fetching: {e}")
                if attempt < retry_count - 1:
                    await asyncio.sleep(base_delay * (2 ** attempt))
                    continue
                raise
        return None

    async def __get_page(self, page_name: str) -> list[Any]:
        params = {
            'action': 'parse',
            'page': page_name,
            'format': 'json',
            'prop': 'links'
        }

        data = await self._make_request(params)

        if data is None or data.get('parse', None) is None:
            return []
        return data['parse']['links']

    async def _get_backlinks(self, page_name: str) -> list[Any]:
        # See: https://en.wikipedia.org/w/api.php?action=help&modules=query%2Bbacklinks
        params = {
            'action': 'query',
            'list': 'backlinks',
            'bltitle': page_name,
            'format': 'json',
            'bllimit': 'max',
            'blnamespace': 0,  # Only articles
            'blredirect': 1
        }

        data = await self._make_request(params)

        if data is None or data.get('query', None) is None:
            return []

        return data['query']['backlinks']

    async def _get_links_single(self, page_name: str) -> set[str]:
        logger.info(f"Parsing links from '{page_name}'")

        if page_name in self.links_cache:
            logger.debug(f"Giving cached links for page {page_name}")
            return self.links_cache[page_name]

        raw_links = await self.__get_page(page_name)

        # Limit to MAX_LINKS_PER_PAGE
        if len(raw_links) > self.MAX_LINKS_PER_PAGE:
            logger.debug(f"Page '{page_name}' has {len(raw_links)} links, limiting to {self.MAX_LINKS_PER_PAGE}")
            raw_links = raw_links[:self.MAX_LINKS_PER_PAGE]

        links = set()
        for raw_link in raw_links:
            links.add(raw_link["*"])

        self.links_cache[page_name] = links
        return links

    async def _get_backlinks_single(self, page_name: str) -> set[str]:
        logger.info(f"Parsing backlinks for '{page_name}'")
        if page_name in self.backlinks_cache:
            logger.debug(f"Giving cached backlinks for page {page_name}")
            return self.backlinks_cache[page_name]

        raw_links = await self._get_backlinks(page_name)

        # Limit to MAX_LINKS_PER_PAGE
        if len(raw_links) > self.MAX_LINKS_PER_PAGE:
            logger.debug(f"Page '{page_name}' has {len(raw_links)} backlinks, limiting to {self.MAX_LINKS_PER_PAGE}")
            raw_links = raw_links[:self.MAX_LINKS_PER_PAGE]

        links = set()
        for raw_link in raw_links:
            links.add(raw_link["title"])

        self.backlinks_cache[page_name] = links
        return links

    # Legacy wrappers using batch implementation with single item or direct call if preferred
    async def get_links(self, page_name: str) -> set[str]:
        return await self._get_links_single(page_name)

    async def get_backlinks(self, page_name: str) -> set[str]:
        return await self._get_backlinks_single(page_name)

    async def get_pages_info(self, page_names: list[str], direction: int) -> Dict[str, int]:
        if not page_names:
            return {}

        chunk_size = 50
        results = {}

        cache = self.links_cache if direction == 0 else self.backlinks_cache

        filtered = []
        for page_name in page_names:
            if page_name in cache:
                results[page_name] = cache[page_name]
            else:
                filtered.append(page_name)

        chunks = [filtered[i:i + chunk_size] for i in range(0, len(filtered), chunk_size)]

        for chunk in chunks:
            params = {
                'action': 'query',
                'prop': 'links',
                'titles': '|'.join(chunk),
                'format': 'json',
                'pllimit': 'max',
                'plnamespace': 0
            }

            data = await self._make_request(params)

            if data and data.get('query') and data['query'].get('pages'):
                for page_id, page_info in data['query']['pages'].items():
                    if 'missing' in page_info:
                        continue


                    links = page_info.get('links', [])

                    if len(links) == 0:
                        continue

                    links = links[:self.MAX_LINKS_PER_PAGE]
                    links = [link['title'] for link in links]
                    links = set(links)

                    links_count = len(links)

                    cache[page_info['title']] = links
                    results[page_info['title']] = links_count

        return results

class WikiParserDumb(WikiParser):
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "WikiGame/1.0 (contact: your_email@example.com)"})

    def __get_page(self, page_name: str) -> list[Any] | Any:
        params = {
            'action': 'parse',
            'page': page_name,
            'format': 'json',
            'prop': 'links'
        }
        req = self.session.get(url=self.URL, params=params)
        data: Dict = req.json()

        if data.get('parse', None) is None:
            return []
        return data['parse']['links']

    def get_links(self, page_name: str) -> set[str]:
        logger.info(f"Parsing links from '{page_name}'")
        raw_links = self.__get_page(page_name)

        if len(raw_links) > self.MAX_LINKS_PER_PAGE:
            logger.debug(f"Page '{page_name}' has {len(raw_links)} links, limiting to {self.MAX_LINKS_PER_PAGE}")
            raw_links = raw_links[:self.MAX_LINKS_PER_PAGE]

        links = set()

        for raw_link in raw_links:
            links.add(raw_link["*"])

        return links
