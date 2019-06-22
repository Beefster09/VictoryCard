#!/usr/bin/env python3.7

import argparse
import glob
import itertools
import logging
import os
import sys

import livereload

from core.deck import Deck, DeckError

log = logging.getLogger('victorycard')

VERSION = 0, 4, 3

def expand_path(path):
    abspath = os.path.abspath(path)
    if '*' in abspath:  # Fill in glob support on windows
        yield from glob.iglob(abspath)
    elif os.path.isdir(path):
        for entry in os.scandir(path):
            if entry.name.endswith('.yaml'):
                yield entry.path
    else:
        yield abspath

def main():
    parser = argparse.ArgumentParser(
        description="HTML + CSS card template renderer"
    )

    parser.add_argument(
        'sources',
        type=expand_path,
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

    parser.add_argument(
        '--debug',
        action='store_true',
        help="Show traceback information for deck errors."
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    sources = [*itertools.chain.from_iterable(args.sources)]
    # TODO? when using directories, maybe it could detect new decks

    source_dir = os.path.dirname(sources[0])

    def try_Deck(deck_file):
        try:
            return Deck(deck_file)
        except DeckError as err:
            print("Error:", err)
        except Exception:
            log.exception("Unexpected error (this is a bug)")

    decks = [try_Deck(deck_file) for deck_file in sources]
    for deck in decks:
        if deck is None:
            continue
        try:
            deck.render()
        except DeckError as err:
            print("Error:", err)
        except Exception:
            log.exception("Unexpected error (this is a bug)")

    if any(deck is None for deck in decks):
        print("Some of the decks had errors. Aborting")
        sys.exit(1)

    if args.run_server:
        if not all(os.path.dirname(path) == source_dir for path in sources):
            # Restrict files to being in the same directory so that the server can have a common root
            # TODO: eliminate this restriction somehow
            print("All deck files must be in the same directory for live server use.")
            sys.exit(2)

        def sync():
            for deck in decks:
                try:
                    deck.sync()
                except DeckError as err:
                    print("Error:", err)
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
