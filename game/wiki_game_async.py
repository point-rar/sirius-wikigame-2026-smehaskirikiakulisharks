from typing import Optional

from game.wiki_game import WikiGame
from model.path import Path


class WikiGameAsync(WikiGame):
    def play(self, start_page_name: str, end_page_name: str, max_depth: int = None) -> Optional[Path]:
        raise NotImplementedError
