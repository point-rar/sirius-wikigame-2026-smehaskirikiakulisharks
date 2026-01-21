from typing import Optional

from game.wiki_game import WikiGame
from model.page import Page
from model.path import Path

from loguru import logger

from parser.wiki_parser import WikiParserDumb


# The simplest implementation with sequential page parsing using BFS
class WikiGameDumb(WikiGame):
    def __init__(self):
        self.wiki_parser = WikiParserDumb()

    def play(self, start_page_name: str, end_page_name: str, max_depth: int = None) -> Optional[Path]:
        logger.info(
            "Started playing\n\t" +
            f"Start page: '{start_page_name}'\n\t" +
            f"End page: '{end_page_name}'\n\t" +
            f"Max depth: {max_depth}"
        )

        # Simple BFS
        start_page = Page(start_page_name, 0)
        queued_page_names = set(start_page_name)
        queue = [start_page]

        while len(queue) != 0:
            cur_page = queue.pop(0)
            logger.debug(
                f"\n\tParsing '{cur_page.page_name}'\n\t" +
                f"Depth: {cur_page.depth}\n\t" +
                f"Queue size: {len(queue)}"
            )

            logger.debug("Previous page: "
                         f"{cur_page.prev.page_name if cur_page.prev is not None else cur_page.prev}")

            links = self.wiki_parser.get_links(cur_page.page_name)
            for link in links:
                next_page_name = link.title

                if next_page_name == end_page_name:
                    logger.success("Path found!")
                    end_page = Page(next_page_name, cur_page.depth + 1, cur_page)
                    return end_page.path_to_root()

                if ((next_page_name not in queued_page_names) and
                        (max_depth is None or cur_page.depth < max_depth)):
                    queued_page_names.add(next_page_name)
                    next_page = Page(next_page_name, cur_page.depth + 1, cur_page)
                    queue.append(next_page)

        logger.error("Path not found, depth limit reached :(")
        return None
