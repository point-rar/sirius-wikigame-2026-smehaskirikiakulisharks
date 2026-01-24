#!/bin/python3.11


import sys
import time

from argparse import ArgumentParser
from loguru import logger


from game.wiki_game_dumb import WikiGameDumb
from game.wiki_game_async import WikiGameAsync

if __name__ == '__main__':

    started_at = time.perf_counter()
    argumentParser = ArgumentParser(

        prog='WikiGame',
        description='Let\'s play WikiGame!'
    )

    DefaultStart = "Down syndrome"
    DefaultEnd = "Segment tree"
    DefaultDepth = 4
    DefaultGameType = 'async'

    argumentParser.add_argument('-s', '--start', default=DefaultStart)
    argumentParser.add_argument('-e', '--end', default=DefaultEnd)
    argumentParser.add_argument('-dep', '--depth', default=DefaultDepth, type=int)
    argumentParser.add_argument('-gametype', '--gametype', choices=['dumb', 'async'], default=DefaultGameType)
    argumentParser.add_argument('--debug', action='store_true')

    args = argumentParser.parse_args()

    if not args.debug:
        logger.remove(0)
        logger.add(sys.stderr, level='INFO')

    wiki_game = None
    if args.gametype == 'dumb':
        wiki_game = WikiGameDumb()
        path = wiki_game.play(args.start, args.end, args.depth)
    elif args.gametype == 'async':
        import asyncio
        wiki_game = WikiGameAsync()
        path = asyncio.run(wiki_game.play(args.start, args.end, args.depth))
    else:
        logger.error("Incorrect game_old type.")
        exit(-1)

    duration_s = time.perf_counter() - started_at

    if path:
        logger.success("Path is:\n\t"
                       + " -> \n\t".join([f"'{p}'" for p in path.page_names])
                       + f"\n\n\tExecution time: {duration_s:.3f}s")
    else:
        logger.error(f"Execution time: {duration_s:.3f}s")

