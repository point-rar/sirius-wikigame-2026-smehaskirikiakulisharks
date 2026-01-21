from abc import ABC, abstractmethod
from typing import Optional

from model.path import Path


class WikiGame(ABC):
    @abstractmethod
    def play(self, start_page_name: str, end_page_name: str, max_depth: int = None) -> Optional[Path]:
        pass
