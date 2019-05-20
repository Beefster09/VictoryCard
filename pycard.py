import argparse
import csv
import logging
import os
import re
import time

import livereload
import yaml
import jinja2
from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler, FileSystemEventHandler

log = logging.getLogger('pycard')


VERSION = '0.2.0'

RENDERED_CARDS_FILE = "index.html"

FULL_DECK_TEMPLATE = os.path.join(os.path.dirname(__file__), 'cards.html.jinja2')


def render_from_csv(csv_path, delimiter=','):
    base, ext = os.path.splitext(csv_path)
    card_template_path = base + '.html.jinja2'
    header_path = base + '.header.html'
    # load the single card template
    with open(card_template_path) as tf:
        template = jinja2.Template(tf.read())

    # load the csv file
    rendered_cards = []
    with open(csv_path, encoding='utf-8-sig') as csvfile:
        for card in csv.DictReader(csvfile, delimiter=delimiter):
            if str(card.get('ignore', "false")).lower() == "true":
                continue

            rendered = template.render(
                card,
                __card_data=card,
                __time=str(time.time())
            )
            copies = card.get('copies', 1)
            if not copies.isdigit():
                copies = 1

            for i in range(int(copies)):
                rendered_cards.append(rendered)

    # Load custom header html if it exists
    custom_header = None

    if os.path.exists(header_path):
        with open(header_path) as f:
            custom_header = f.read()

    # render the cards template with all rendered cards
    with open(FULL_DECK_TEMPLATE) as tf:
        template = jinja2.Template(tf.read())

    with open(output_path, "w") as of:
        of.write(
            template.render(
                rendered_cards=rendered_cards,
                stylesheet=os.basename(base) + '.css',
                custom_header=custom_header
            )
        )


def render_from_yaml(yaml_path):
    base, ext = os.path.splitext(os.path.basename(yaml_path))
    source_dir = os.path.dirname(yaml_path)

    with open(yaml_path) as yf:
        deck_info = yaml.safe_load(yf)

    global_ = {
        'template': FULL_DECK_TEMPLATE,
        'stylesheet': base + '.css',
        'header': base + '.header.html',
        'output': base + '.html',
        **deck_info.get('global', {})
    }
    defaults = {
        'template': base + '.html.jinja2',
        'copies': 1,
        **deck_info.get('default', {})
    }

    template_cache = {}
    def get_template(name):
        nonlocal template_cache
        if not name.endswith('.html.jinja2'):
            name += '.html.jinja2'
        if name in template_cache:
            return template_cache[name]
        else:
            with open(os.path.join(source_dir, name)) as tf:
                template = jinja2.Template(tf.read())
            template_cache[name] = template
            return template

    rendered_cards = []
    for card in deck_info['cards']:
        try:
            copies = int(card.pop('copies', defaults['copies']) or '1')
        except ValueError as err:
            log.warning("Invalid value for 'copies': {}".format(err.args[0]))
            copies = 1

        if copies <= 0:
            continue

        log.info(card)
        template = get_template(card.pop('template', defaults['template']))
        rendered = template.render(
            {**defaults, **card},
            __card_data=card,
            __time=str(time.time())
        )
        log.info(rendered)
        rendered_cards += [rendered] * copies

    log.info("%d total cards", len(rendered_cards))

    header_path = os.path.join(source_dir, global_['header'])
    if os.path.exists(header_path):
        with open(header_path) as f:
            custom_header = f.read()
    else:
        custom_header = None

    with open(global_['template']) as tf:
        global_template = jinja2.Template(tf.read())

    with open(os.path.join(source_dir, global_['output']), "w") as of:
        of.write(
            global_template.render(
                rendered_cards=rendered_cards,
                stylesheet=global_['stylesheet'],
                custom_header=custom_header
            )
        )
    return source_dir, global_['output']


class RenderingEventHandler(FileSystemEventHandler):
    def __init__(self, render_func, ignore=()):
        self._render_func = render_func
        self._ignored_files = ignore

    def on_any_event(self, event):
        if event.src_path in self._ignored_files:
            return

        time.sleep(0.5)  # wait for the file to be written
        self._render_func()


def parse_args():
    parser = argparse.ArgumentParser(
        description="HTML + CSS card template renderer"
    )

    parser.add_argument(
        'path',
        type=os.path.abspath,
        metavar='PATH',
        help="path to assets"
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

    return parser.parse_args()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    args = parse_args()

    source, output = render_from_yaml(args.path)

    if args.run_server:
        observer = Observer()
        observer.schedule(
            LoggingEventHandler(),
            source,
            recursive=True
        )
        observer.schedule(
            RenderingEventHandler(lambda: render_from_yaml(args.path), output),
            source,
            recursive=True
        )

        observer.start()

        server = livereload.Server()
        server.watch(source)
        server.serve(root=source, port=args.port, host=args.host)

        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()
