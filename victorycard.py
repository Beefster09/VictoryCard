#!/usr/bin/env python3.7

import argparse
import functools
import logging
import os
import re
import sys
import time
from datetime import datetime

import jinja2
import livereload
import markdown
import yaml
from markdown.extensions import Extension
from markdown.inlinepatterns import InlineProcessor, SimpleTagInlineProcessor
from markdown.util import etree

from core.deck import Deck

log = logging.getLogger('victorycard')

VERSION = '0.4.0'


def main():
    parser = argparse.ArgumentParser(
        description="HTML + CSS card template renderer"
    )

    parser.add_argument(
        'definitions',
        type=os.path.abspath,
        nargs='+',
        metavar='PATH',
        help="Path(s) to yaml files defining each deck."
    )

    parser.add_argument(
        '-p', '--port',
        type=int,
        default=8800,
        metavar='PORT',
        help="port to use for live reloaded page",
    )

    parser.add_argument(
        '--host',
        help="host address to bind to",
        default='0.0.0.0',
        metavar='ADDRESS'
    )

    parser.add_argument(
        '-1', '--no-server',
        dest='run_server',
        action='store_false',
        help="Do not start up a server that watches the directory"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    source_dir = os.path.dirname(args.definitions[0])

    if not all(os.path.dirname(path) == source_dir for path in args.definitions):
        # Restrict files to being in the same directory so that the server can have a common root
        parser.error("All deck files must be in the same directory.")

    def try_Deck(deck_file):
        try:
            return Deck(deck_file)
        except Exception as err:
            print("Error:", err)
            return None

    decks = [try_Deck(deck_file) for deck_file in args.definitions]
    for deck in decks:
        if deck is None:
            continue
        try:
            deck.render()
        except Exception as err:
            print("Error:", err)

    if any(deck is None for deck in decks):
        print("Some of the decks had errors. Aborting")
        sys.exit(1)

    if args.run_server:
        def sync():
            for deck in decks:
                try:
                    deck.sync()
                except Exception:
                    log.exception("Cannot sync %r", deck.source.path)

        server = livereload.Server()
        server.watch(
            f'{source_dir}/*',
            sync,
            ignore=lambda path: not any(deck.is_dependency(path) for deck in decks)
        )
        server.serve(
            root=source_dir,
            port=args.port,
            host=args.host,
            live_css=False,  # Live CSS causes some issues with syncing the html reloads
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted.")
