import argparse
import functools
import logging
import os
import re
import time
from datetime import datetime

import jinja2
import livereload
import markdown
import yaml
from markdown.extensions import Extension
from markdown.inlinepatterns import InlineProcessor
from markdown.util import etree

log = logging.getLogger('pycard')


VERSION = '0.3.0'

FULL_DECK_TEMPLATE = os.path.join(os.path.dirname(__file__), 'cards.html.jinja2')

class IconInsertionProcessor(InlineProcessor):
    def __init__(self, pattern, icon_root='.', fs_root='.'):
        self.icon_root = icon_root
        self.fs_root = fs_root
        super().__init__(pattern)

    def handleMatch(self, m, data):
        icon_name = m.group(1)
        if '.' not in icon_name:
            for ext in ['.svg', '.webp', '.png', '.gif', '.bmp', '.jpeg', '.jpg']:
                candidate = os.path.join(self.icon_root, icon_name + ext)
                if os.path.isfile(os.path.join(self.fs_root, candidate)):
                    icon_path = candidate
                    break
            else:
                log.warning(f"No icons found for {icon_name!r}")
                el = etree.Element('del')
                el.attrib['class'] = '__icon'
                el.text = icon_name
                return el, m.start(0), m.end(0)  # no substitution
        else:
            icon_path = os.path.join(self.icon_root, icon_name)
        el = etree.Element('img')
        el.attrib['src'] = icon_path
        el.attrib['class'] = '__icon'
        return el, m.start(0), m.end(0)


class IconInsertion(Extension):
    def __init__(self, icon_root='.', fs_root='.', **kwargs):
        self.config = {
            "icon_root"  : ['.', "The root to use for the icon, relative to the cards.yaml"],
            "fs_root"  : ['.', "The filesystem root of the deck data"],
        }
        self.icon_root = icon_root
        self.fs_root = fs_root

        super().__init__(**kwargs)

    def extendMarkdown(self, md):
        md.inlinePatterns.add(
            'inline_icon',
            IconInsertionProcessor(r'\[(?:icon|i):([-_A-Za-z0-9]+)\]', self.icon_root, self.fs_root),
            '<link'
        )


P_TAG = re.compile(r'</?p>')


def render_from_yaml(yaml_path):
    base, ext = os.path.splitext(os.path.basename(yaml_path))
    source_dir = os.path.dirname(yaml_path)
    now = datetime.now()

    jinja_loader = jinja2.FileSystemLoader(source_dir)
    jinja_env = jinja2.Environment(loader=jinja_loader)

    with open(yaml_path) as yf:
        deck_info = yaml.safe_load(yf)

    general = {
        'template': FULL_DECK_TEMPLATE,
        'stylesheet': base + '.css',
        'header': base + '.html.header',
        'output': base + '.html',
        'icon_path': '.',
        'markdown': {},
        **deck_info.get('general', {})
    }
    # Configure markdown
    md_extensions = [
        IconInsertion(general['icon_path'], source_dir) if ext == 'icon' else ext
        for ext in general['markdown'].get('extensions', ['smarty', 'icon'])
    ]
    md_ext_conf = {
        'card_icon': {
            'icon_root': general['icon_path'],
            'fs_root': source_dir
        },
        **general['markdown'].get('extension_configs', {})
    }

    jinja_env.filters['md_paragraph'] = md_paragraph = functools.partial(
        markdown.markdown,
        extensions=md_extensions,
        extension_configs=md_ext_conf,
    )
    jinja_env.filters['md_inline'] = md_inline = lambda text: P_TAG.sub('', md_paragraph(text))
    jinja_env.filters['md_auto'] = lambda text: md_paragraph(text) if '\n' in text else md_inline(text)
    jinja_env.filters['markdown'] = jinja_env.filters[f"md_{general['markdown'].get('default_mode', 'auto')}"]


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
            template = jinja_env.get_template(name)
            template_cache[name] = template
            return template

    rendered_cards = []
    for card in deck_info['cards']:
        try:
            copies = int(card.pop('copies', defaults['copies']) or 1)
        except ValueError as err:
            log.warning("Invalid value for 'copies': {}".format(err.args[0]))
            copies = 1

        if copies <= 0:
            continue

        template = get_template(card.pop('template', defaults['template']))
        rendered = template.render(
            {**defaults, **card},
            __card_data=card,
            __time=now
        )
        rendered_cards += [rendered] * copies

    log.info("%d total cards", len(rendered_cards))

    header_path = os.path.join(source_dir, general['header'])
    if os.path.exists(header_path):
        with open(header_path) as f:
            custom_header = f.read()
    else:
        custom_header = None

    with open(general['template']) as tf:
        global_template = jinja2.Template(tf.read())

    with open(os.path.join(source_dir, general['output']), "w") as of:
        of.write(
            global_template.render(
                rendered_cards=rendered_cards,
                stylesheet=general['stylesheet'],
                custom_header=custom_header
            )
        )
    return source_dir, general['output']


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
        server = livereload.Server()
        server.watch(
            f'{source}/*',
            lambda: render_from_yaml(args.path),
            ignore=lambda path: path.endswith('.html')
        )
        server.serve(root=source, port=args.port, host=args.host)


if __name__ == "__main__":
    main()
