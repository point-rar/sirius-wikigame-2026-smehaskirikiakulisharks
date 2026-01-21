from abc import ABC, abstractmethod

import requests

from bs4 import BeautifulSoup
from loguru import logger

from model.link import Link


class WikiParser(ABC):
    URL = 'https://en.wikipedia.org/w/api.php'

    @abstractmethod
    def get_links(self, page_name: str) -> set[str]:
        pass


class WikiParserDumb(WikiParser):
    def __init__(self):
        self.session = requests.Session()

    def __get_page(self, page_name: str) -> str:
        # See: https://en.wikipedia.org/w/api.php?action=help&modules=parse
        # https://en.wikipedia.org/w/api.php, https://ru.wikipedia.org/w/api.php
        params = {
            'action': 'parse',
            'page': page_name,
            'format': 'json'
        }
        req = self.session.get(url=self.URL, params=params)
        data = req.json()

        return data['parse']['text']['*']

    def get_links(self, page_name: str) -> set[Link]:
        logger.info(f"Parsing links from '{page_name}'")
        page = self.__get_page(page_name)
        # https://beautiful-soup-4.readthedocs.io/en/latest/
        soup = BeautifulSoup(page, 'html.parser')
        raw_links = soup.find_all('a', href=lambda x: x and x.startswith('/wiki/'), class_=False)

        links = set()

        for raw_link in raw_links:
            title = raw_link.attrs['title']
            # Avoid beginnings
            # Help: Wikipedia: Special: Category: Template: User talk:
            if ':' not in title:
                links.add(Link(title))

        return links
