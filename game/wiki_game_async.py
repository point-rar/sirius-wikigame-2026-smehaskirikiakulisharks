import asyncio
import random
from typing import Optional

from loguru import logger

from game.wiki_game import WikiGame
from model.page import Page
from model.path import Path
from parser.wiki_parser import WikiParser


class WikiGameAsync(WikiGame):
    def __init__(self, concurrency=10):
        self.wiki_parser = WikiParser()
        self.concurrency = concurrency

    async def play(self, start_page_name: str, end_page_name: str, max_depth: int = None) -> Optional[Path]:
        logger.info(
            "Started playing (Bidirectional + Heuristic + Ratio)\n\t" +
            f"Start page: '{start_page_name}'\n\t" +
            f"End page: '{end_page_name}'\n\t" +
            f"Max depth: {max_depth}"
        )

        # Warmup connection to avoid slow first request
        await self.wiki_parser.warmup()

        queue_fwd = asyncio.PriorityQueue()
        queue_bwd = asyncio.PriorityQueue()

        async def add_to_queue(priority, page_name, page, direction):
            item = (priority, page_name, (page, direction))
            if direction == 0:
                await queue_fwd.put(item)
            else:
                await queue_bwd.put(item)

        # 0 for forward, 1 for backward
        start_page = Page(start_page_name, 0)
        end_page_node = Page(end_page_name, 0)

        await add_to_queue(0, start_page_name, start_page, 0)
        await add_to_queue(0, end_page_name, end_page_node, 1)

        visited_forward = {start_page_name: start_page}
        visited_backward = {end_page_name: end_page_node}

        result: Optional[Path] = None
        stop_event = asyncio.Event()

        async def get_priority(lenght: int, page: Page, direction: int):
            # TODO: сделайте тут что то рабочее по братски
            return lenght

        async def worker():
            nonlocal result

            task_fwd = None
            task_bwd = None

            while not stop_event.is_set():
                try:
                    # Maintain two pending tasks
                    if not task_fwd:
                        task_fwd = asyncio.create_task(queue_fwd.get())
                    if not task_bwd:
                        task_bwd = asyncio.create_task(queue_bwd.get())

                    selected_task = None

                    # Logic to select which completed task to process
                    fwd_done = task_fwd.done()
                    bwd_done = task_bwd.done()

                    if fwd_done and bwd_done:
                        # Both available: prioritize forward (4:1 ratio = 80%)
                        if random.random() < 0.8:
                            selected_task = task_fwd
                        else:
                            selected_task = task_bwd
                    elif fwd_done:
                        selected_task = task_fwd
                    elif bwd_done:
                        selected_task = task_bwd
                    else:
                        # Wait for at least one
                        done, _ = await asyncio.wait(
                            [task_fwd, task_bwd],
                            return_when=asyncio.FIRST_COMPLETED
                        )
                        # Loop again to handle selection logic
                        continue

                    # Get the item from the selected task
                    try:
                        prio, _, item = await selected_task
                    except asyncio.CancelledError:
                        return

                    # Clear the task variable so it's recreated next loop
                    if selected_task == task_fwd:
                        task_fwd = None
                        target_queue_for_ack = queue_fwd
                    else:
                        task_bwd = None
                        target_queue_for_ack = queue_bwd

                    cur_page, direction = item

                    # --- Processing Start ---
                    try:
                        if stop_event.is_set():
                            target_queue_for_ack.task_done()
                            continue

                        if direction == 0:  # Forward
                            logger.debug(
                                f"Forward: Parsing '{cur_page.page_name}' (Depth {cur_page.depth}, Prio {-prio})")
                            links_method = self.wiki_parser.get_links
                            own_visited = visited_forward
                            other_visited = visited_backward
                        else:  # Backward
                            logger.debug(
                                f"Backward: Parsing backlinks for '{cur_page.page_name}' (Depth {cur_page.depth}, Prio {-prio})")
                            links_method = self.wiki_parser.get_backlinks
                            own_visited = visited_backward
                            other_visited = visited_forward

                        links = await links_method(cur_page.page_name)

                        candidates = []

                        for link in links:
                            next_page_name = link.title

                            if next_page_name in other_visited:
                                logger.success(f"Path found! Meeting at '{next_page_name}'")
                                meeting_page_other = other_visited[next_page_name]

                                if direction == 0:
                                    path_f = Page(next_page_name, cur_page.depth + 1,
                                                  cur_page).path_to_root().page_names
                                    path_b = meeting_page_other.path_to_root().page_names
                                else:
                                    path_b = Page(next_page_name, cur_page.depth + 1,
                                                  cur_page).path_to_root().page_names
                                    path_f = meeting_page_other.path_to_root().page_names

                                full_path_names = path_f[:-1] + path_b[::-1]
                                result = Path(full_path_names)
                                stop_event.set()
                                target_queue_for_ack.task_done()
                                return

                            if next_page_name not in own_visited:
                                if max_depth is None or cur_page.depth < max_depth:
                                    next_page = Page(next_page_name, cur_page.depth + 1, cur_page)
                                    own_visited[next_page_name] = next_page
                                    candidates.append(next_page)

                        if candidates and not stop_event.is_set():
                            # Limit total chunk size to MAX_LINKS_IN_CHUNK
                            max_chunk_size = self.wiki_parser.MAX_LINKS_IN_CHUNK
                            if len(candidates) > max_chunk_size:
                                logger.debug(f"Chunk has {len(candidates)} candidates, limiting to {max_chunk_size}")
                                candidates = candidates[:max_chunk_size]

                            # For backward search, heuristics might differ, but using same for now
                            candidate_names = [p.page_name for p in candidates]
                            page_infos = await self.wiki_parser.get_pages_info(candidate_names)

                            for next_page in candidates:
                                length = page_infos.get(next_page.page_name, 0)

                                priority = await get_priority(length, next_page, direction)
                                await add_to_queue(priority, next_page.page_name, next_page, direction)

                    except Exception as e:
                        logger.error(f"Error processing {cur_page.page_name}: {e}")
                    finally:
                        target_queue_for_ack.task_done()
                    # --- Processing End ---

                except asyncio.CancelledError:
                    return

        workers = [asyncio.create_task(worker()) for _ in range(self.concurrency)]

        async def queue_monitor():
            await asyncio.gather(queue_fwd.join(), queue_bwd.join())
            stop_event.set()

        monitor = asyncio.create_task(queue_monitor())

        await stop_event.wait()

        for w in workers:
            w.cancel()

        await asyncio.gather(*workers, return_exceptions=True)
        monitor.cancel()

        await self.wiki_parser.close()

        if result:
            return result

        logger.error("Path not found, depth limit reached or queues empty :(")
        return None
