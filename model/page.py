from model.path import Path
from loguru import logger


class Page:
    def __init__(self, page_name: str, depth: int, prev=None):
        self.prev = prev
        self.page_name = page_name
        self.depth = depth

    # restoring the path through prev-links
    def path_to_root(self) -> Path:
        path = []

        cur_page = self
        while cur_page.prev is not None:
            path.append(cur_page.page_name)
            cur_page = cur_page.prev

        path.append(cur_page.page_name)
        path.reverse()

        logger.success("Path is:\n\t" + " -> ".join([f"'{p}'" for p in path]))

        return Path(path)
