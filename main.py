#!/bin/python3.11


import sys

from argparse import ArgumentParser
from loguru import logger

from game.wiki_game_dumb import WikiGameDumb
from game.wiki_game_async import WikiGameAsync

if __name__ == '__main__':
    argumentParser = ArgumentParser(
        prog='WikiGame',
        description='Let\'s play WikiGame!'
    )

    argumentParser.add_argument('-s', '--start', help='Start page name')
    argumentParser.add_argument('-e', '--end', help='End page name')
    argumentParser.add_argument('-dep', '--depth', help='Search depth', type=int)
    argumentParser.add_argument('--gametype', choices=['dumb', 'async'], default='dumb')
    argumentParser.add_argument('--debug', help='Enable debug info', action='store_true')

    args = argumentParser.parse_args()

    if not args.debug:
        logger.remove(0)
        logger.add(sys.stderr, level='INFO')

    wiki_game = None
    if args.gametype == 'dumb':
        wiki_game = WikiGameDumb()
    elif args.gametype == 'async':
        wiki_game = WikiGameAsync()

    if wiki_game is None:
        logger.error("Incorrect game_old type.")
        exit(-1)

    path = wiki_game.play(args.start, args.end, args.depth)

    print(path)
